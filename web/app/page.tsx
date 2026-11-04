import { TopBar } from "@/components/TopBar";
import { Explorer } from "@/components/Explorer";
import { Note, Section, Stat } from "@/components/Ui";
import { bench, cost, fixed, LEVELS, LINKEDIN_URL, REPO_URL, RESCUE, router } from "@/lib/data";
import { int, pct, usd } from "@/lib/cost";

const steps = [
  { n: "01", t: "Serve", d: "Glimmer 30B INT4 on vLLM, prefix caching, one L4" },
  { n: "02", t: "Run", d: "40 graded data pipeline triage cases" },
  { n: "03", t: "Route", d: "Low reasoning, escalate only when stuck" },
  { n: "04", t: "Price", d: "Cost per task vs three API price lists" },
];

const td = "px-3 py-2.5 border-b border-line whitespace-nowrap tabular-nums";
const th = "text-left px-3 py-2.5 text-[11px] uppercase tracking-wider font-normal text-subtle whitespace-nowrap";
const m = (x: number) => `$${x.toFixed(2)}`;

export default function Page() {
  const r = router.router;
  const on = bench.filter((b) => b.tag === "prefix_on" || (b.tag === "seqs16" && b.conc === 16)).sort((a, b) => a.conc - b.conc);
  const on4 = on.find((b) => b.conc === 4)!;
  const off = bench.find((b) => b.tag === "prefix_off")!;
  const maxTph = Math.max(...on.map((b) => b.tasks_per_hr));
  const speedup = on4.tasks_per_hr / off.tasks_per_hr;
  const latCut = 1 - on4.case_lat_mean / off.case_lat_mean;
  const p = cost.prices;

  return (
    <>
      <TopBar />
      <main id="top" className="max-w-5xl mx-auto px-4 sm:px-6 pb-16">
        <div className="pt-12 pb-10">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-accent mb-3">
            Inference economics · Meta Muse Glimmer
          </p>
          <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-heading max-w-3xl">
            When does owning a GPU beat paying per token?
          </h1>
          <p className="mt-4 text-muted max-w-2xl leading-relaxed">
            Meta&apos;s open-weights Muse Glimmer 30B, self-hosted on one ${cost.gpu_hourly.spot}/hr L4, running a 40-case
            data pipeline triage agent. Same cases, measured tokens, three API price lists.
          </p>
          <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-3">
            {steps.map((s) => (
              <div key={s.n} className="rounded-lg border border-line bg-panel p-4">
                <p className="font-mono text-[11px] text-accent">{s.n}</p>
                <p className="mt-1 text-sm font-semibold text-heading">{s.t}</p>
                <p className="mt-0.5 text-xs text-subtle leading-relaxed">{s.d}</p>
              </div>
            ))}
          </div>
        </div>

        <Section id="explorer" eyebrow="01 · Break-even" title="How busy does the L4 have to be?">
          <p className="text-muted mb-6 max-w-2xl leading-relaxed">
            An API costs the same per task at any volume. The L4 costs the same per day, so it only gets cheap when it
            stays busy. Drag the load and switch providers.
          </p>
          <Explorer />
          <Note>
            For agents, the cache price matters more than the GPU. Prefix caching hit about 93% of input tokens, so
            providers that discount cached input are very hard to beat with one card.
          </Note>
        </Section>

        <Section id="reasoning" eyebrow="02 · Reasoning levels" title="Meta recommends high reasoning for agents. Low did just as well.">
          <div className="grid gap-3 sm:grid-cols-3 mb-6">
            <Stat value="39 / 40" label="solved at every level" />
            <Stat value="about 30%" label="fewer output tokens and less time, low vs high" accent />
            <Stat value={`${r.escalated_cases} of ${r.n}`} label="cases the router escalated" />
          </div>
          <div className="overflow-x-auto rounded-xl border border-line bg-panel">
            <table className="w-full text-xs sm:text-sm font-mono">
              <thead>
                <tr className="border-b border-line">
                  {["Level", "Success", "Steps", "Reasoning tok", "Out tok / task", "Sec / task", "Forced + rescue", "DeepInfra / task"].map((h) => (
                    <th key={h} className={th}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {LEVELS.map((l) => {
                  const o = fixed[`fixed_${l}_v2`].overall;
                  const low = l === "low";
                  return (
                    <tr key={l} className={low ? "text-accent" : "text-muted"}>
                      <td className={`${td} ${low ? "text-accent" : "text-heading"}`}>{l}</td>
                      <td className={td}>
                        {o.success}/{o.cases}
                      </td>
                      <td className={td}>{o.steps.toFixed(1)}</td>
                      <td className={td}>{int(o.reason_tok)}</td>
                      <td className={td}>{int(o.out_tok_per_success)}</td>
                      <td className={td}>{int(o.wall_s_per_success)}</td>
                      <td className={td}>{o.forced + RESCUE[l]}</td>
                      <td className={td}>{usd(cost.levels[l].api_cost_per_task.deepinfra)}</td>
                    </tr>
                  );
                })}
                <tr className="text-muted">
                  <td className={`${td} text-heading`}>router</td>
                  <td className={td}>
                    {r.success}/{r.n}
                  </td>
                  <td className={td}>{r.steps.toFixed(1)}</td>
                  <td className={td}>{int(r.reasoning_tok)}</td>
                  <td className={td}>{int(r.out_tok_per_success)}</td>
                  <td className={td}>{int(r.s_per_success)}</td>
                  <td className={td}>{(r.status.submitted_forced ?? 0) + (r.status.submitted_rescue ?? 0)}</td>
                  <td className={td}>= low</td>
                </tr>
              </tbody>
            </table>
          </div>
          <Note>
            Higher levels weren&apos;t wrong, just slower. They took about two extra steps per case, so under a 14-step
            budget they had to be forced to submit more often.
          </Note>
          <Note>
            The router runs low by default and escalates to high only on a repeated tool call or two tool errors. It
            matched fixed low exactly, so treat it as a cheap safety net. Escalating when the agent merely looked slow
            (step 10) backfired in a smoke test: about 1.5× the tokens and time, because higher reasoning is slower.
          </Note>
        </Section>

        <Section id="serving" eyebrow="03 · Serving" title="What one 24 GB L4 can carry">
          <div className="grid gap-4 md:grid-cols-[1.4fr_1fr]">
            <div className="rounded-xl border border-line bg-panel p-5">
              <p className="font-mono text-[11px] text-subtle mb-4">concurrent agents · reasoning low</p>
              <div className="space-y-5">
                {on.map((b) => (
                  <div key={b.conc}>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted">
                        {b.conc} {b.conc === 1 ? "agent" : "agents"}
                      </span>
                      <span className="font-mono tabular-nums text-heading">{Math.round(b.tasks_per_hr)} tasks/hr</span>
                    </div>
                    <div className="mt-1.5 h-2 rounded-full bg-card">
                      <div className="h-full rounded-full bg-accent" style={{ width: `${(b.tasks_per_hr / maxTph) * 100}%` }} />
                    </div>
                    <p className="mt-1 font-mono text-[11px] text-subtle">
                      {Math.round(b.case_lat_mean)} s per task · {b.gen_tok_per_s} tok/s · KV peak {pct(b.kv_peak)} ·{" "}
                      {b.success}/{b.n} correct
                    </p>
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-4">
              <div className="rounded-xl border border-line bg-panel p-5">
                <p className="font-mono text-[11px] text-subtle mb-4">prefix caching · 4 agents</p>
                {[
                  { k: "on", b: on4 },
                  { k: "off", b: off },
                ].map(({ k, b }) => (
                  <div key={k} className="mb-4 last:mb-0">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted">cache {k}</span>
                      <span className="font-mono tabular-nums text-heading">{Math.round(b.tasks_per_hr)} tasks/hr</span>
                    </div>
                    <div className="mt-1.5 h-2 rounded-full bg-card">
                      <div
                        className={`h-full rounded-full ${k === "on" ? "bg-accent" : "bg-api"}`}
                        style={{ width: `${(b.tasks_per_hr / on4.tasks_per_hr) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
                <p className="mt-3 text-xs text-subtle">
                  {speedup.toFixed(1)}× throughput, {pct(latCut)} lower latency.
                </p>
              </div>
              <Stat value="didn't fit" label="Speculative decoding: Meta's 4.8 GB drafter next to 17 GB of INT4 weights" />
            </div>
          </div>
          <Note>
            These are expected effects: decode is memory-bound, so 4-bit weights, batching and prefix caching all help.
            The cap at 8 agents is the server&apos;s max-num-seqs setting, not memory. KV usage peaked at {pct(on[on.length - 1].kv_peak)}.
          </Note>
        </Section>

        <Section id="method" eyebrow="04 · Method" title="How the numbers are made">
          <pre className="rounded-xl border border-line bg-panel p-5 text-xs sm:text-sm font-mono text-heading overflow-x-auto leading-relaxed">
{`API cost per task  = (uncached_in × p_in + cached_in × p_cached + out × p_out) / 1e6
L4 cost per task   = hourly × 24 / successful tasks per day
Break-even load    = GPU cost per day / (API cost per task × capacity per day)`}
          </pre>
          <ul className="mt-6 space-y-2.5 text-sm text-muted leading-relaxed max-w-3xl list-disc pl-5 marker:text-accent">
            <li>Everything is per successful task. Tokens are measured on the L4; API cost is list price × those tokens. No paid API run.</li>
            <li>Cached input share is our own prefix cache hit rate (93 to 94%). Providers cache differently, so API cost is a close estimate.</li>
            <li>
              {`Prices per 1M tokens (in / cached / out): Doubleword ${m(p.doubleword.in)} / ${m(p.doubleword.cached)} / ${m(p.doubleword.out)}, DeepInfra ${m(p.deepinfra.in)} / ${m(p.deepinfra.cached)} / ${m(p.deepinfra.out)}. No-cache uses Together's list price, ${m(p.together_nocache.in)} in / ${m(p.together_nocache.out)} out, with no cache discount.`}
            </li>
            <li>L4 capacity is measured at low (333 tasks/hr at 16 agents, 15 of 16 correct, so ~312 successful). Other levels are scaled by time per success.</li>
            <li>Excludes engineering time, storage, egress and spot interruptions. One run per level, so read differences as &quot;about&quot;.</li>
            <li>
              The one miss at every level (case_009) is ambiguous: a type-mismatch injector adds a unit-like &quot; pcs&quot; suffix, and every level
              called it a unit change with the right file, column and fix. The label was kept as is.
            </li>
          </ul>
          <div className="mt-6 flex flex-wrap gap-2">
            {["Muse Glimmer 30B", "vLLM", "INT4 GPTQ", "NVIDIA L4", "GCP spot", "DuckDB", "Python", "Next.js"].map((t) => (
              <span key={t} className="font-mono text-[11px] rounded-md border border-line px-2 py-1 text-muted">
                {t}
              </span>
            ))}
          </div>
        </Section>
      </main>

      <footer className="border-t border-line">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between text-xs text-subtle">
          <p>ThinkABR · Built by Anagha for the Meta Global AI Developer Hackathon · Numbers are measured, raw data in runs/</p>
          <div className="flex gap-4">
            <a href={REPO_URL} target="_blank" rel="noreferrer" className="hover:text-heading">
              GitHub
            </a>
            <a href={LINKEDIN_URL} target="_blank" rel="noreferrer" className="hover:text-heading">
              LinkedIn
            </a>
          </div>
        </div>
      </footer>
    </>
  );
}