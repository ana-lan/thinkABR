import json, math

PRICES = {  # per 1M tokens: in, cached in, out. Checked Nov 3 2026.
    "doubleword":       {"in": 0.11, "cached": 0.01, "out": 0.32},
    "deepinfra":        {"in": 0.30, "cached": 0.04, "out": 1.20},
    "together_nocache": {"in": 0.35, "cached": 0.35, "out": 1.50},
}
GPU = {"spot": 0.423, "on_demand": 0.707}  # g2-standard-4 us-central1, $/hr, GCP console Nov 3
LEVELS = ["low", "medium", "high", "xhigh"]
UTILS = [0.25, 0.5, 0.75, 1.0]

summ = json.load(open("runs/fixed_summary_v2.json"))
bench = [json.loads(l) for l in open("runs/bench.jsonl")]
peak = [b for b in bench if b["tag"] == "prefix_on" and b["conc"] == 8][0]
low_t = summ["fixed_low_v2"]["overall"]["wall_s_per_success"]

out = {"prices": PRICES, "gpu_hourly": GPU, "levels": {}, "bench": bench}
for lv in LEVELS:
    o = summ[f"fixed_{lv}_v2"]["overall"]
    tin, hit, tout = o["in_tok_per_success"], o["cache_hit"], o["out_tok_per_success"]
    cap_hr = peak["tasks_per_hr"] * low_t / o["wall_s_per_success"]
    cap_day = cap_hr * 24
    api = {p: (tin*(1-hit)*v["in"] + tin*hit*v["cached"] + tout*v["out"]) / 1e6
           for p, v in PRICES.items()}
    self_host = {}
    for g, hr in GPU.items():
        gday = hr * 24
        self_host[g] = {
            "gpu_per_day": gday,
            "per_task_by_util": {str(u): gday / (cap_day * u) for u in UTILS},
            "breakeven": {p: {"tasks_per_day": gday / c,
                              "util_needed": gday / c / cap_day,
                              "one_gpu_wins": gday / c <= cap_day}
                          for p, c in api.items()},
        }
    curve = []
    for n in range(0, int(cap_day * 3) + 1, 100):
        gpus = max(1, math.ceil(n / cap_day))
        row = {"tasks_per_day": n, "gpus": gpus}
        for g, hr in GPU.items():
            row[f"self_{g}"] = gpus * hr * 24
        for p, c in api.items():
            row[f"api_{p}"] = n * c
        curve.append(row)
    out["levels"][lv] = {
        "success_rate": o["success_rate"], "steps": o["steps"],
        "in_tok": tin, "cache_hit": hit, "out_tok": tout,
        "reason_tok": o["reason_tok"], "s_per_success": o["wall_s_per_success"],
        "cap_per_hr": cap_hr, "cap_per_day": cap_day,
        "cap_measured": lv == "low",
        "api_cost_per_task": api, "self_host": self_host, "curve": curve,
    }

json.dump(out, open("runs/cost_model.json", "w"), indent=1)

for lv, d in out["levels"].items():
    tag = "" if d["cap_measured"] else " (est)"
    print(f"\n{lv}: cap {d['cap_per_day']:.0f}/day{tag}, in {d['in_tok']:.0f}, out {d['out_tok']:.0f}")
    for p, c in d["api_cost_per_task"].items():
        s = d["self_host"]["spot"]["breakeven"][p]
        od = d["self_host"]["on_demand"]["breakeven"][p]
        print(f"  {p:17s} ${c:.5f}/task  N* spot {s['tasks_per_day']:7.0f} ({s['util_needed']:.0%})"
              f"  od {od['tasks_per_day']:7.0f} ({od['util_needed']:.0%})")
