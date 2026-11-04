"""Muse Spark baseline: same cases, tools, loop and grader as Glimmer, via Meta Model API."""
import json, os, sys, time
from pathlib import Path
from openai import OpenAI
import agent.loop as loop
import grade

loop.MODEL = os.environ.get("SPARK_MODEL", "muse-spark-1.3")
loop.system_prompt = lambda level: loop.SYSTEM_BASE   # no Glimmer reasoning line
EFFORT = os.environ.get("SPARK_EFFORT")               # unset = API default

client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"],
                timeout=600, max_retries=5)
_create = client.chat.completions.create
def _create_eff(**kw):
    if EFFORT:
        kw.setdefault("reasoning_effort", EFFORT)
    return _create(**kw)
client.chat.completions.create = _create_eff

lp, out, ids = sys.argv[1], sys.argv[2], sys.argv[3:]
labels = grade.load_labels(lp)
root = Path(lp).parent
done = {json.loads(l)["case_id"] for l in open(out)} if Path(out).exists() else set()

for cid in ids or sorted(labels):
    if cid in done:
        continue
    rec = loop.run_case(root / cid, loop.fixed_policy("spark"), client=client, keep_reasoning=False)
    rec.update(run="spark", policy=f"spark:{EFFORT or 'default'}", model=loop.MODEL, ts=time.time())
    g = grade.grade_case(rec, labels[cid])
    with open(out, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(cid, labels[cid].get("failure_type"), rec["status"], rec["n_steps"], "steps |",
          rec["total_prompt_tokens"], "in", rec["total_cached_tokens"], "cached",
          rec["total_completion_tokens"], "out |", rec["wall_s"], "s |",
          "OK" if g["success"] else "MISS", rec["prediction"], flush=True)
