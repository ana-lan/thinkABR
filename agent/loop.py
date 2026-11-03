"""Phase 2.5: the triage agent loop.

One case = one conversation with Glimmer. Each model call is one "step". The reasoning
level for each step comes from a policy function, so Phase 4's router plugs in here
without touching the loop. Fixed-level runs use fixed_policy("high") etc.

Everything Phases 3 to 5 need is logged per step.
"""
import json
import re
import time
import urllib.request
from pathlib import Path

from openai import BadRequestError, OpenAI

from agent.tools import TOOL_SCHEMAS, CaseTools, parse_submission

BASE_URL = "http://localhost:8000"
MODEL = "muse-glimmer"
MAX_MODEL_LEN = 16384
MAX_STEPS = 14
WARN_STEPS = 3     # start warning this many steps before the cap
MAX_OUT = 3072          # per-step completion cap (reasoning + tool call)
MIN_OUT = 256           # below this much room left, stop with context_overflow

SYSTEM_BASE = """You are the on-call data engineer for a nightly batch pipeline (DuckDB SQL jobs over three raw CSV files: orders.csv, customers.csv, products.csv). A run just failed. Investigate with the tools, then call submit_diagnosis exactly once.

Failure types:
- missing_file: a raw input file is absent
- renamed_column: a column a job reads now has a different name
- type_mismatch: a numeric column contains non-numeric values
- date_format_change: a date or timestamp column switched format
- duplicate_keys: a dimension file has duplicate key rows, so the join fans out
- null_explosion: a column is mostly blank or NULL
- bad_join_key: a key column changed format, so the join matches nothing
- unit_change: a numeric column changed units or scale

Rules:
- The root cause is always in one raw file. Report that file and the column at fault (column "none" only for missing_file).
- Use the original column name the pipeline expects, not a new upstream name.
- Be efficient: stop investigating as soon as you are confident."""


def system_prompt(level):
    # Level line goes LAST so the cacheable prefix is as long as possible.
    return f"{SYSTEM_BASE}\n\nReasoning strength: {level}"


def fixed_policy(level):
    return lambda step, messages, steps: level


# ---------- vLLM side endpoints (best effort, never fatal) ----------
def _post(path, payload, base=BASE_URL, timeout=30):
    req = urllib.request.Request(base + path, json.dumps(payload).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def count_tokens(text, base=BASE_URL):
    if not text:
        return 0
    try:
        return _post("/tokenize", {"model": MODEL, "prompt": text, "add_special_tokens": False},
                     base)["count"]
    except Exception:
        return None


_METRIC_RE = re.compile(r"^(vllm:prefix_cache_(?:hits|queries)_total)\{[^}]*\}\s+([0-9.eE+]+)", re.M)


def prefix_cache_counters(base=BASE_URL):
    try:
        with urllib.request.urlopen(base + "/metrics", timeout=10) as r:
            text = r.read().decode()
        vals = {}
        for name, v in _METRIC_RE.findall(text):
            vals[name] = vals.get(name, 0.0) + float(v)
        return vals.get("vllm:prefix_cache_hits_total"), vals.get("vllm:prefix_cache_queries_total")
    except Exception:
        return None, None


# ---------- the loop ----------
def _get_reasoning(msg):
    for attr in ("reasoning", "reasoning_content"):
        v = getattr(msg, attr, None)
        if v:
            return v
    extra = getattr(msg, "model_extra", None) or {}
    return extra.get("reasoning") or extra.get("reasoning_content")


def run_case(case_dir, policy, client=None, keep_reasoning=True, base=BASE_URL, verbose=False):
    case_dir = Path(case_dir)
    client = client or OpenAI(base_url=f"{base}/v1", api_key="none", timeout=600)
    tools = CaseTools(case_dir)

    hits0, queries0 = prefix_cache_counters(base)
    t_case = time.time()
    messages = [{"role": "system", "content": None},
                {"role": "user", "content": (case_dir / "alert.txt").read_text()}]
    steps, prediction, status, nudged = [], None, "max_steps", False
    est_prompt = 0

    for step in range(MAX_STEPS):
        level = policy(step, messages, steps)
        messages[0]["content"] = system_prompt(level)

        room = MAX_MODEL_LEN - est_prompt - 512
        if step > 0 and room < MIN_OUT:
            status = "context_overflow"
            break
        max_tokens = MAX_OUT if step == 0 else min(MAX_OUT, room)

        last = step == MAX_STEPS - 1
        choice = {"type": "function", "function": {"name": "submit_diagnosis"}} if last else "auto"

        t0 = time.time()
        try:
            r = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOL_SCHEMAS,
                                               tool_choice=choice, max_tokens=max_tokens)
        except BadRequestError as e:
            if "context" in str(e).lower() or "maximum" in str(e).lower() or "too long" in str(e).lower():
                status = "context_overflow"
                break
            raise
        latency = time.time() - t0

        msg, u = r.choices[0].message, r.usage
        reasoning = _get_reasoning(msg) or ""
        details = getattr(u, "prompt_tokens_details", None)
        rec = {
            "step": step, "level": level, "finish": r.choices[0].finish_reason,
            "prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens,
            "cached_tokens": getattr(details, "cached_tokens", None) if details else None,
            "reasoning_tokens": count_tokens(reasoning, base), "reasoning_chars": len(reasoning),
            "latency_s": round(latency, 3), "forced_submit": last, "tools": [],
        }
        steps.append(rec)

        asst = {"role": "assistant", "content": msg.content or ""}
        if keep_reasoning and reasoning:
            asst["reasoning"] = reasoning          # NOT reasoning_content: that one is silently dropped
        if msg.tool_calls:
            asst["tool_calls"] = [{"id": tc.id, "type": "function",
                                   "function": {"name": tc.function.name,
                                                "arguments": tc.function.arguments}}
                                  for tc in msg.tool_calls]
        messages.append(asst)
        est_prompt = u.prompt_tokens + u.completion_tokens

        if verbose:
            calls = ", ".join(f"{tc.function.name}({tc.function.arguments[:80]})" for tc in msg.tool_calls or [])
            print(f"  step {step} [{level}] {latency:5.1f}s  prompt={u.prompt_tokens} out={u.completion_tokens} "
                  f"reason_tok={rec['reasoning_tokens']}  -> {calls or (msg.content or '')[:120]!r}")

        if r.choices[0].finish_reason == "length":
            status = "truncated_output"
            break

        if not msg.tool_calls:
            if nudged:
                status = "no_submission"
                break
            nudged = True
            messages.append({"role": "user", "content": "Call submit_diagnosis now with your best answer."})
            est_prompt += 20
            continue

        done = False
        for tc in msg.tool_calls:
            name, args = tc.function.name, tc.function.arguments
            if name == "submit_diagnosis":
                prediction = parse_submission(args)
                rec["tools"].append({"name": name, "args": args})
                status = ("submitted_forced" if last else "submitted") if prediction else "bad_submission"
                done = True
                break
            out = tools.call(name, args)
            left = MAX_STEPS - 1 - step
            if left <= WARN_STEPS:
                out += (f"\n[budget: {left} step(s) left. Call submit_diagnosis with your best answer "
                        f"{'now' if left <= 1 else 'soon'}.]")
            rec["tools"].append({"name": name, "args": args, "out_chars": len(out)})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
            est_prompt += len(out) // 3 + 16   # rough until the next call reports the real number
        if done:
            break

    # Rescue: forced submit sometimes returns no tool call. One extra forced call, same level.
    if prediction is None and status in ("max_steps", "no_submission"):
        messages[0]["content"] = system_prompt(level)
        messages.append({"role": "user", "content": "Step budget used up. Call submit_diagnosis now with your best answer."})
        t0 = time.time()
        try:
            r = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOL_SCHEMAS,
                tool_choice={"type": "function", "function": {"name": "submit_diagnosis"}}, max_tokens=1024)
            msg, u = r.choices[0].message, r.usage
            for tc in msg.tool_calls or []:
                if tc.function.name == "submit_diagnosis":
                    prediction = parse_submission(tc.function.arguments)
            if prediction is None and msg.content:
                try:
                    prediction = parse_submission(msg.content)
                except Exception:
                    prediction = None
            reasoning = _get_reasoning(msg) or ""
            steps.append({"step": len(steps), "level": level, "finish": r.choices[0].finish_reason,
                          "prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens,
                          "cached_tokens": None, "reasoning_tokens": count_tokens(reasoning, base),
                          "reasoning_chars": len(reasoning), "latency_s": round(time.time() - t0, 3),
                          "forced_submit": True, "rescue": True, "tools": []})
            status = "submitted_rescue" if prediction else "rescue_failed"
        except BadRequestError:
            status = "rescue_failed"

    hits1, queries1 = prefix_cache_counters(base)
    cache = None
    if None not in (hits0, queries0, hits1, queries1) and queries1 > queries0:
        cache = round((hits1 - hits0) / (queries1 - queries0), 4)

    totals = {k: sum((s.get(k) or 0) for s in steps)
              for k in ("prompt_tokens", "completion_tokens", "cached_tokens", "reasoning_tokens")}
    return {
        "case_id": case_dir.name, "status": status, "prediction": prediction,
        "n_steps": len(steps), "n_tool_calls": sum(len(s["tools"]) for s in steps),
        "wall_s": round(time.time() - t_case, 2), "prefix_cache_hit_rate": cache,
        "keep_reasoning": keep_reasoning, **{f"total_{k}": v for k, v in totals.items()},
        "steps": steps,
    }
