import json, sys, grade
labels = grade.load_labels(sys.argv[1])
for lvl in ["low", "medium", "high", "xhigh"]:
    for l in open(f"runs/fixed_{lvl}_v2.jsonl"):
        r = json.loads(l)
        lab = labels[r["case_id"]]
        g = grade.grade_case(r, lab)
        if not g["success"]:
            print("==", lvl, r["case_id"], r["status"], g)
            print("LABEL:", lab["failure_type"], lab["file"], lab["column"], lab["accepted_columns"])
            print("FIX:", lab["fix"])
            print("PRED:", json.dumps(r["prediction"])[:700])
