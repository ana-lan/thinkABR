import { trace } from "@/lib/data";
import { int } from "@/lib/cost";

const fmtArgs = (a: Record<string, unknown>) =>
  Object.entries(a)
    .map(([k, v]) => `${k}=${typeof v === "string" ? JSON.stringify(v) : String(v)}`)
    .join(", ");

export function AgentTrace() {
  const t = trace;
  const p = t.prediction;
  const g = t.graded;
  const chips = [
    t.case_id,
    t.failure_type.replaceAll("_", " "),
    "hard",
    "reasoning low",
    `${t.n_steps} steps`,
    `${Math.round(t.wall_s)} s`,
    `${int(t.out_tokens)} out tok`,
  ];
  const checks: [string, boolean, string | null][] = [
    ["failure type", g.type_ok, p.failure_type],
    ["file", g.file_ok, p.file],
    ["column", g.col_ok, p.column],
  ];

  return (
    <div className="rounded-xl border border-line bg-panel p-4 sm:p-6">
      <div className="flex flex-wrap gap-2 mb-5">
        {chips.map((c) => (
          <span key={c} className="font-mono text-[11px] rounded-md border border-line px-2 py-1 text-muted">
            {c}
          </span>
        ))}
      </div>

      <p className="font-mono text-[11px] text-subtle mb-1.5">the alert</p>
      <pre className="rounded-lg border border-line bg-bg p-3 text-xs font-mono text-heading whitespace-pre-wrap leading-relaxed">
        {t.alert.trim()}
      </pre>

      <p className="font-mono text-[11px] text-subtle mt-6 mb-2">what the agent did · click a call to see its output</p>
      <ol className="space-y-3">
        {t.steps.map((s) => (
          <li key={s.step} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3">
            <div className="font-mono text-[11px] text-accent pt-2">{String(s.step + 1).padStart(2, "0")}</div>
            <div className="space-y-1.5">
              {s.calls.length === 0 ? (
                <div className="rounded-md border border-accent-line bg-accent-soft px-3 py-2 font-mono text-xs text-accent">
                  submit_diagnosis(...)
                </div>
              ) : (
                s.calls.map((c, i) => (
                  <details key={i} className="group rounded-md border border-line bg-bg">
                    <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden px-3 py-2 font-mono text-xs text-heading break-all">
                      <span className="text-accent">{c.name}</span>({fmtArgs(c.args)})
                      <span className="text-subtle ml-2 group-open:hidden">▸ output</span>
                    </summary>
                    <pre className="px-3 pb-3 text-[11px] font-mono text-muted whitespace-pre-wrap break-all max-h-56 overflow-y-auto leading-relaxed">
                      {c.out}
                    </pre>
                  </details>
                ))
              )}
              <p className="font-mono text-[10px] text-subtle">
                {s.latency_s.toFixed(1)} s{s.reasoning_tokens ? ` · ${int(s.reasoning_tokens)} reasoning tok` : ""}
              </p>
            </div>
          </li>
        ))}
      </ol>

      <div className="mt-6 rounded-lg border border-accent-line bg-accent-soft p-4">
        <p className="font-mono text-[11px] text-accent">diagnosis · graded {g.success ? "correct" : "wrong"}</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          {checks.map(([k, ok, v]) => (
            <div key={k}>
              <p className="font-mono text-[10px] text-subtle">{k}</p>
              <p className="font-mono text-xs text-heading">
                <span className={ok ? "text-accent" : "text-subtle"}>{ok ? "✓" : "✗"}</span> {v ?? "none"}
              </p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-sm text-heading leading-relaxed">{p.fix}</p>
      </div>
    </div>
  );
}