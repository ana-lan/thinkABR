<div align="center">

# ThinkABR

**Self-host or pay per token?** ThinkABR serves Meta's Muse Glimmer on one cheap cloud GPU, runs a real triage agent on it, and measures exactly when owning the GPU beats the API.

[![model](https://img.shields.io/badge/model-Muse_Glimmer_30B-E5484D)](https://huggingface.co/meta-models/Muse-Glimmer-30B)
[![gpu](https://img.shields.io/badge/GPU-1x_NVIDIA_L4-76B900)](#serving-low-reasoning-l4)
[![serving](https://img.shields.io/badge/serving-vLLM_INT4-30A2FF)](#reproduce)
[![baseline](https://img.shields.io/badge/baseline-Muse_Spark_1.3-0866FF)](#reasoning-level-40-cases-each)
[![dashboard](https://img.shields.io/badge/dashboard-live-brightgreen)](https://thinkabr.vercel.app)

**Live demo:** [thinkabr.vercel.app](https://thinkabr.vercel.app) | **Demo video:** [3-minute walkthrough](https://youtu.be/1W7iQVMgkY0)

</div>

Adaptive bitrate, but for reasoning. Glimmer is the cost floor, Spark is the quality ceiling, and ThinkABR finds where the line between renting tokens and owning a GPU actually falls. A sibling to VisionABR: VisionABR adapts image resolution, ThinkABR adapts reasoning effort.

## The answer

A spot NVIDIA L4 serving Muse Glimmer 30B (4-bit, vLLM, tuned) beats a per-token API **once it's about 51% busy against DeepInfra, and never against the cheapest provider.**

| Hosted Glimmer provider | API $ / task | Spot L4 beats it at | On-demand L4 beats it at |
|---|---|---|---|
| No-cache reference (Together list) | $0.0090 | 15% busy (1,131 tasks/day) | 25% busy |
| DeepInfra | $0.0026 | **51% busy (3,843 tasks/day)** | 86% busy |
| Doubleword | $0.0007 | never (needs 185% of one L4) | never (309%) |

Task = one pipeline failure diagnosed end to end, low reasoning. A fully loaded spot L4 costs $0.0014 per task, which is still twice Doubleword's price. **For agents, the cache price matters more than the GPU:** prompts are long and repetitive (93% prefix cache hits), so a provider that discounts cached input changes the answer more than any serving tweak.

The frontier check: Meta's **Muse Spark 1.3** solved 40/40 cases at $0.0127 per task in about 15 s. Glimmer solved 39/40 at a fifth of the price on DeepInfra, or a ninth of it on a fully loaded L4, but took about 84 s. Spark is the quality ceiling, Glimmer is the cost floor.

## Built during the hackathon

Everything in this repo was built from Oct 29 to Nov 4, 2026, for the Meta Global AI Developer Hackathon (Indie Developer track, Push the Frontier). Nothing existed before:

- Glimmer serving setup on one L4 and every benchmark in `runs/`
- The synthetic data pipeline, 8 failure injectors and 40 graded test cases
- The triage agent, its tools, loop and rule-based grader
- The escalate-on-stuck reasoning router
- The cost model and break-even calculation
- The Muse Spark 1.3 baseline run
- The dashboard in `web/`

## What's in it

**1. Agent workload: data pipeline failure triage.** A small DuckDB pipeline with 8 injected failure types (missing file, type mismatch, date format change, renamed column, duplicate keys, null explosion, bad join key, unit change) and 40 deterministic test cases (15 easy, 5 medium, 20 hard). For each failed run the agent reads the error log and job code, inspects schemas, samples rows, runs SQL, and submits a root cause and fix. A rule-based grader checks failure type, file and column. The same 40 cases are replayed against every setup, and results are reported per completed task, not per token.

**2. Serving on one L4 (24 GB).** `RedHatAI/Muse-Glimmer-30B-INT4` (GPTQ W4A16) on vLLM's `muse-glimmer` image, 16K context, prefix caching, max-num-seqs 16. Speculative decoding with Meta's drafter does not fit: weights take 17.3 GiB of 22 GiB usable, and the drafter is another 4.8 GB.

**3. Reasoning levels and a router.** Glimmer takes a `Reasoning strength: <level>` line in the system prompt (low, medium, high, xhigh). The line sits at the end of the system prompt so switching levels doesn't break the prefix cache. The router runs low by default and escalates once to high when the agent looks stuck (an exact repeated tool call, or 2 tool errors).

**4. Cost model.** Measured tokens, cache hit rate and throughput become cost per successful task for self-hosting (spot and on-demand) and for each API provider. It outputs the break-even in tasks per day and as a share of one L4's capacity.

**5. Dashboard.** Break-even explorer with a utilization slider and provider, GPU and level toggles; a daily-cost staircase past one GPU; a replayed agent trace; reasoning and serving results; method notes.

## Results

### Reasoning level (40 cases each)

| Setup | Solved | Steps | Output tok / success | Time / success |
|---|---|---|---|---|
| Glimmer low | 39/40 | 7.8 | 1,229 | 84 s |
| Glimmer medium | 39/40 | 9.7 | 1,695 | 116 s |
| Glimmer high | 39/40 | 9.8 | 1,808 | 123 s |
| Glimmer xhigh | 39/40 | 9.9 | 1,705 | 116 s |
| Glimmer router (low, escalate when stuck) | 39/40 | 8.4 | 1,228 | 84 s |
| Muse Spark 1.3 (Meta API) | 40/40 | 5.8 | 1,426 | 15 s |

- **Low matched high on accuracy with about 30% fewer tokens and 30% less time**, even though the [Glimmer model card](https://huggingface.co/meta-models/Muse-Glimmer-30B) recommends high or xhigh for agentic tasks.
- Higher levels didn't make the agent wrong, they made it slower: about 2 more steps per case, so they ran into the step budget more often. Forced or rescue submits out of 40: low 0, medium 10, high 7, xhigh 8.
- The router escalated on 2 of 40 cases and landed on low's numbers. Treat it as a cheap safety net, not a win over low. An escalate-when-slow trigger (step 10) backfired in a smoke test, using about 1.5x the tokens and time, because higher reasoning is slower.
- Reasoning level doesn't flip the cost answer. Low makes both the API and the L4 about 30% cheaper per task, so the break-even against DeepInfra stays at 51 to 53% at every level.
- The one Glimmer miss, case_009, is the same at every level. The type mismatch injector adds a " pcs" suffix, and Glimmer called it a unit change with the right file, column and a working fix. Spark got it right, so the label stands.

### Serving (low reasoning, L4)

| Setup | Tasks / hr | Mean latency | KV peak |
|---|---|---|---|
| 1 agent | 52 | 69 s | 9% |
| 4 agents, prefix cache off | 70 | 159 s | |
| 4 agents, prefix cache on | 106 | 100 s | 32% |
| 8 agents, one wave of 8 cases | 182 | 94 s | 42% |
| 8 agents, 16 cases (max-num-seqs 8) | 271 | 88 s | 46% |
| **16 agents, 16 cases (max-num-seqs 16)** | **333** (~312 successful) | 113 s | 78% |

Decode is memory-bound, so 4-bit weights, batching and prefix caching helping is expected (prefix caching: 1.5x throughput at a 94% hit rate). The useful part is how they move the break-even against DeepInfra:

- **88% to about 59%: a measurement fix.** The first bench ran one wave of 8 cases, so the slowest case set the wall time.
- **About 59% to 51%: real tuning.** max-num-seqs 8 to 16 gave 1.23x throughput at about 28% higher latency per case, as Little's law predicts. Still 0 preemptions and 0 queued requests at 16 agents.

Past one GPU, owning wins in bands, not "from then on". At low reasoning on spot against DeepInfra, one L4 wins from 3,843 to 7,497 tasks a day. A second, mostly idle card hands the win back until 7,685, and from there L4s keep winning.

## Use of Meta tooling

- **Muse Glimmer 30B (open weights, self-hosted).** The core model: every agent run, benchmark and cost number. Served on my own rented GPU, not through an API.
- **Muse Spark 1.3 (Meta Model API).** A frontier baseline on the same 40 cases, tools, loop and grader. It was the only paid run, at $0.51.

## Method and honesty notes

- **Prices (Nov 3, 2026).** Doubleword realtime $0.11 in / $0.01 cached / $0.32 out per 1M tokens. DeepInfra $0.30 / $0.04 / $1.20. No-cache reference $0.35 / $0.35 / $1.50. Muse Spark 1.3 $1.25 / $0.15 / $4.25. GCP g2-standard-4 (1 L4, us-central1) $0.423/hr spot, $0.707/hr on-demand. Doubleword's async tier is excluded because agents can't wait for batch.
- **API cost for Glimmer is list price times measured tokens.** There was no paid Glimmer API run. The cached share comes from my own prefix cache hit rate, so providers that cache differently will land close but not exact. Spark is the only paid run.
- **What the cost model leaves out.** It excludes engineering time, storage, egress and spot interruptions. It assumes steady load around the clock; bursty traffic needs headroom and raises the real break-even. For production, quote the on-demand number (86%), since spot was preempted many times during this project.
- **Sampling.** There is one run per level and one wave per bench point, so read the percentages as "about".
- **Capacity.** Medium, high and xhigh capacity is estimated by scaling low by token count.
- **Harness bugs.** Two bugs found in the first sweep (a forced submit returning nothing, and context overflow from a bad token estimate) were fixed. Only the affected runs were rerun.

## Repo layout

```
pipeline/       synthetic DuckDB pipeline, failure injectors, case generator
agent/          tools, agent loop, reasoning router
run_agent.py    fixed-level runs        run_router.py   router runs
run_spark.py    Muse Spark baseline     grade.py        rule-based grader
bench.py        concurrency benchmark   cost_model.py   break-even model
serve_16.sh     vLLM launch (final)     make_trace.py   dashboard agent trace
runs/           all raw results and summaries
web/            dashboard (Next.js static export, Vercel)
```

## Reproduce

```bash
bash serve_16.sh                                   # vLLM on one L4
python -m pipeline.make_cases                      # 40 cases into cases/
LP=./cases/labels.jsonl
bash sweep.sh                                      # fixed levels
python run_router.py $LP runs/router.jsonl         # router
python bench.py --level low --conc 8,16 --per_type 2 --tag seqs16
python cost_model.py                               # writes runs/cost_model.json
python run_spark.py $LP runs/spark.jsonl           # needs MODEL_API_KEY
cd web && npm install && npm run build             # dashboard
```

Pinned versions:
- Image: `vllm/vllm-openai@sha256:413c8fbecb1204a218117c77a4ea4b3a211d5686ff99c31d82ba6dd0cec8c5a6`
- Weights: `RedHatAI/Muse-Glimmer-30B-INT4` @ `397b1ee1eb83f09b9675e66e49d5ec3a522c509a`

## Prior work

This is not a new technique. Difficulty-based reasoning routing (Ares, DART), load-aware reasoning budgets (LASER, ACER) and agent KV cache work (Continuum) exist in research. What's new here:

- the first published Glimmer numbers on a cheap cloud GPU
- the first self-host vs API cost crossover for Glimmer on an agent workload
- reasoning cost measured per agent task
- a same-harness Glimmer vs Spark comparison