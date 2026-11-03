import json, os, sys
from agent.loop import run_case
from agent.router import router_policy
labels_path, out = sys.argv[1], sys.argv[2]
only = sys.argv[3].split(",") if len(sys.argv) > 3 else None
root = os.path.dirname(labels_path)
ids = sorted(json.loads(l)["case_id"] for l in open(labels_path))
done = {json.loads(l)["case_id"] for l in open(out)} if os.path.exists(out) else set()
for cid in ids:
    if (only and cid not in only) or cid in done:
        continue
    pol = router_policy()
    rec = run_case(os.path.join(root, cid), pol)
    rec["policy"] = "router"
    rec["router_events"] = pol.events
    with open(out, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(cid, rec["status"], rec["n_steps"], pol.events, flush=True)
