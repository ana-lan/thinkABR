import json, collections, grade
labels = grade.load_labels("/home/Asus/thinkabr/cases/labels.jsonl")
for lvl in ["low", "medium", "high", "xhigh"]:
    rows = [json.loads(l) for l in open(f"runs/fixed_{lvl}_v2.jsonl")]
    st = collections.Counter(r.get("status") for r in rows)
    print(lvl, len(rows), dict(st))
r0 = rows[0]
print("REC KEYS:", list(r0.keys()))
print("LABELS TYPE:", type(labels).__name__, len(labels))
sample = labels[0] if isinstance(labels, list) else next(iter(labels.items()))
print("LABEL SAMPLE:", str(sample)[:400])
