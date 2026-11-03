import re
ERR = re.compile(r"(error|exception|not found|does not exist)", re.I)
ERR_TOOLS = {"run_sql", "sample_rows", "get_schema"}

def _get(m, k):
    return m.get(k) if isinstance(m, dict) else getattr(m, k, None)

def last_tool_outputs(messages):
    outs = []
    for m in reversed(messages):
        if _get(m, "role") != "tool":
            break
        outs.append(str(_get(m, "content") or ""))
    return list(reversed(outs))

def router_policy(start="low", up="high", max_errors=2, budget_step=99):
    st = {"level": start, "errors": 0, "seen": set()}
    events = []
    def pol(step, messages, steps):
        if st["level"] == start and steps:
            tools = steps[-1].get("tools") or []
            outs = last_tool_outputs(messages)
            reason = None
            for i, t in enumerate(tools):
                key = (t["name"], t["args"])
                if key in st["seen"] and not reason:
                    reason = "repeat:" + t["name"]
                st["seen"].add(key)
                out = outs[i] if i < len(outs) else ""
                if t["name"] in ERR_TOOLS and ERR.search(out[:300]):
                    st["errors"] += 1
            if not reason and st["errors"] >= max_errors:
                reason = "errors:%d" % st["errors"]
            if not reason and step >= budget_step:
                reason = "budget:%d" % step
            if reason:
                st["level"] = up
                events.append({"step": step, "reason": reason})
        return st["level"]
    pol.events = events
    return pol
