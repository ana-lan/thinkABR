"use client";

import { useState } from "react";
import { cost, LEVELS, PROVIDERS, type Gpu, type Level, type Provider } from "@/lib/data";
import { apiPerTask, breakEvenUtil, capPerDay, int, pct, selfPerTask, usd } from "@/lib/cost";

const W = 600;
const H = 260;
const ML = 60;
const MR = 16;
const MT = 14;
const MB = 36;
const PW = W - ML - MR;
const PH = H - MT - MB;

function Seg<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { key: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div>
      <p className="font-mono text-[11px] text-subtle mb-1.5">{label}</p>
      <div
        className="grid rounded-md border border-line overflow-hidden"
        style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
      >
        {options.map((o) => (
          <button
            key={o.key}
            onClick={() => onChange(o.key)}
            className={`px-1.5 py-1.5 text-xs border-l border-line first:border-l-0 transition-colors ${
              o.key === value ? "bg-accent-soft text-accent" : "text-muted hover:text-heading"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function niceMax(v: number) {
  const raw = v / 4;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const m = raw / p;
  const step = (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
  return step * 4;
}

function Chart({ level, gpu, provider, u }: { level: Level; gpu: Gpu; provider: Provider; u: number }) {
  const api = apiPerTask(level, provider);
  const s1 = selfPerTask(level, gpu, 1);
  const be = breakEvenUtil(level, gpu, provider);
  const yMax = niceMax(Math.max(api * 3, s1 * 2));
  const x = (v: number) => ML + v * PW;
  const y = (c: number) => MT + PH - (Math.min(c, yMax) / yMax) * PH;

  const uStart = s1 / yMax;
  const pts: string[] = [];
  for (let i = 0; i <= 80; i++) {
    const v = uStart + ((1 - uStart) * i) / 80;
    pts.push(`${x(v).toFixed(1)},${y(s1 / v).toFixed(1)}`);
  }
  const cur = s1 / Math.max(u, 0.001);
  const beRight = be > 0.7;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="L4 cost per task by utilization vs API cost per task">
      {be <= 1 && <rect x={x(be)} y={MT} width={x(1) - x(be)} height={PH} fill="var(--accent-soft)" />}
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={`y${t}`}>
          <line x1={ML} x2={W - MR} y1={y(yMax * t)} y2={y(yMax * t)} stroke="var(--line)" strokeWidth={0.5} />
          <text x={ML - 8} y={y(yMax * t) + 4} textAnchor="end" className="fill-subtle font-mono" fontSize={10}>
            {usd(yMax * t)}
          </text>
        </g>
      ))}
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <text key={`x${t}`} x={x(t)} y={H - MB + 16} textAnchor="middle" className="fill-subtle font-mono" fontSize={10}>
          {pct(t)}
        </text>
      ))}
      <text x={ML + PW / 2} y={H - 4} textAnchor="middle" className="fill-subtle" fontSize={11}>
        L4 utilization
      </text>

      <line x1={ML} x2={W - MR} y1={y(api)} y2={y(api)} stroke="var(--api)" strokeWidth={1.5} strokeDasharray="5 4" />
      <polyline points={pts.join(" ")} fill="none" stroke="var(--accent)" strokeWidth={2.5} />

      {be <= 1 && (
        <>
          <line x1={x(be)} x2={x(be)} y1={MT} y2={MT + PH} stroke="var(--accent)" strokeWidth={1} strokeDasharray="2 3" />
          <text
            x={beRight ? x(be) - 6 : x(be) + 6}
            y={MT + PH - 8}
            textAnchor={beRight ? "end" : "start"}
            className="fill-accent font-mono"
            fontSize={10}
          >
            break-even {pct(be)}
          </text>
        </>
      )}

      <line x1={x(u)} x2={x(u)} y1={MT} y2={MT + PH} stroke="var(--heading)" strokeWidth={1} opacity={0.3} />
      <circle cx={x(u)} cy={y(cur)} r={5} fill="var(--accent)" stroke="var(--panel)" strokeWidth={2} />
    </svg>
  );
}

export function Explorer() {
  const [provider, setProvider] = useState<Provider>("deepinfra");
  const [gpu, setGpu] = useState<Gpu>("spot");
  const [level, setLevel] = useState<Level>("low");
  const [util, setUtil] = useState(60);

  const u = util / 100;
  const api = apiPerTask(level, provider);
  const self = selfPerTask(level, gpu, u);
  const be = breakEvenUtil(level, gpu, provider);
  const l4Wins = self < api;
  const gap = l4Wins ? (api - self) / api : (self - api) / self;
  const cap = capPerDay(level);
  const lc = cost.levels[level];

  return (
    <div className="rounded-xl border border-line bg-panel p-4 sm:p-6">
      <div className="grid gap-6 md:grid-cols-[240px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Seg label="provider" value={provider} options={PROVIDERS} onChange={setProvider} />
          <Seg
            label="gpu"
            value={gpu}
            options={[
              { key: "spot", label: "spot" },
              { key: "on_demand", label: "on-demand" },
            ]}
            onChange={setGpu}
          />
          <Seg label="reasoning" value={level} options={LEVELS.map((l) => ({ key: l, label: l }))} onChange={setLevel} />
          <div>
            <p className="font-mono text-[11px] text-subtle mb-1.5">
              utilization · <span className="text-heading">{util}%</span>
            </p>
            <input
              type="range"
              min={1}
              max={100}
              step={1}
              value={util}
              onChange={(e) => setUtil(Number(e.target.value))}
              className="w-full"
              style={{ accentColor: "var(--accent)" }}
              aria-label="L4 utilization"
            />
            <p className="font-mono text-[11px] text-subtle mt-1">{int(u * cap)} tasks/day</p>
          </div>
        </div>

        <div>
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <p className="font-mono text-[11px] text-subtle">cost per successful task</p>
            <div className="flex items-center gap-4 font-mono text-[11px] text-muted">
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-0.5 bg-accent" />
                L4 {gpu === "spot" ? "spot" : "on-demand"}
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 border-t-[1.5px] border-dashed border-api" />
                {PROVIDERS.find((p) => p.key === provider)?.label} API
              </span>
            </div>
          </div>
          <Chart level={level} gpu={gpu} provider={provider} u={u} />
          <div className="mt-3 flex flex-wrap items-baseline justify-between gap-2">
            <p className={`text-2xl font-semibold tracking-tight ${l4Wins ? "text-accent" : "text-heading"}`}>
              {l4Wins ? `L4 is ${pct(gap)} cheaper` : `API is ${pct(gap)} cheaper`}
            </p>
            <p className="font-mono text-xs text-muted tabular-nums">
              L4 {usd(self)} · API {usd(api)} per task
            </p>
          </div>
          <p className="mt-1 text-sm text-muted">
            {be <= 1
              ? `Break-even at ${pct(be)} load, about ${int(be * cap)} tasks a day.`
              : `One L4 never wins here. It would need ${pct(be)} load.`}
          </p>
          <p className="mt-3 font-mono text-[11px] text-subtle leading-relaxed">
            glimmer-30b-int4 · 1× L4 {gpu === "spot" ? "spot" : "on-demand"} ${cost.gpu_hourly[gpu]}/hr · capacity{" "}
            {int(cap)}/day {lc.cap_measured ? "(measured)" : "(scaled from low)"} · cache hit {pct(lc.cache_hit)}
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        {PROVIDERS.map((p) => {
          const b = breakEvenUtil(level, gpu, p.key);
          const active = p.key === provider;
          return (
            <button
              key={p.key}
              onClick={() => setProvider(p.key)}
              className={`text-left rounded-lg border p-4 transition-colors ${
                active ? "border-accent-line bg-accent-soft" : "border-line bg-bg hover:border-accent-line"
              }`}
            >
              <p className="font-mono text-[11px] text-subtle">
                {p.label} · {usd(apiPerTask(level, p.key))}/task
              </p>
              <p className={`mt-1 text-xl font-semibold tracking-tight ${b <= 1 ? "text-heading" : "text-accent"}`}>
                {b <= 1 ? `${pct(b)} load` : "never"}
              </p>
              <p className="text-xs text-subtle mt-0.5">
                {b <= 1 ? "to break even on one L4" : `would need ${pct(b)}, more than one L4`}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}