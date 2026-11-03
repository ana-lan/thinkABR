import json, urllib.request
from openai import OpenAI
c = OpenAI(base_url="http://localhost:8000/v1", api_key="x")

tools = [{"type": "function", "function": {
    "name": "read_error_log",
    "description": "Read the error log of a failed pipeline job",
    "parameters": {"type": "object",
        "properties": {"job_id": {"type": "string"}},
        "required": ["job_id"]}}}]
user = "Job daily_orders failed last night. Find the root cause. Start by checking its error log."

print("== Test A: tool call + tokens per reasoning level ==")
for lvl in ["low", "medium", "high", "xhigh"]:
    sys_p = f"You are a data pipeline triage agent.\nReasoning strength: {lvl}"
    r = c.chat.completions.create(model="muse-glimmer", tools=tools, max_tokens=4096,
        messages=[{"role": "system", "content": sys_p}, {"role": "user", "content": user}])
    m, u = r.choices[0].message, r.usage
    reasoning = getattr(m, "reasoning_content", None) or getattr(m, "reasoning", None) or ""
    det = getattr(u, "completion_tokens_details", None)
    print(f"{lvl:7} finish={r.choices[0].finish_reason:10} "
          f"tool={m.tool_calls[0].function.name + m.tool_calls[0].function.arguments if m.tool_calls else None} "
          f"completion_tok={u.completion_tokens} reasoning_chars={len(reasoning)} "
          f"reasoning_tok={getattr(det, 'reasoning_tokens', None) if det else None}")

print("\n== Test B: is past reasoning kept in history? ==")
def ntok(msgs):
    req = urllib.request.Request("http://localhost:8000/tokenize",
        data=json.dumps({"model": "muse-glimmer", "messages": msgs}).encode(),
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))["count"]
filler = "Let me think step by step about the failure. " * 50
base = [{"role": "system", "content": "Reasoning strength: high"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hello!"},
        {"role": "user", "content": "next question"}]
for field in ["reasoning_content", "reasoning"]:
    withr = json.loads(json.dumps(base)); withr[2][field] = filler
    print(f"field={field:18} without={ntok(base)} with={ntok(withr)}")
