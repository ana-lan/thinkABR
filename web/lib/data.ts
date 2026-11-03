import costJson from "@/public/data/cost_model.json";
import routerJson from "@/public/data/router_summary.json";
import fixedJson from "@/public/data/fixed_summary_v2.json";
import benchJson from "@/public/data/bench.json";

export type Provider = "doubleword" | "deepinfra" | "together_nocache";
export type Gpu = "spot" | "on_demand";
export type Level = "low" | "medium" | "high" | "xhigh";

export interface LevelCost {
  success_rate: number;
  steps: number;
  in_tok: number;
  out_tok: number;
  reason_tok: number;
  cache_hit: number;
  s_per_success: number;
  cap_per_day: number;
  cap_measured: boolean;
  api_cost_per_task: Record<Provider, number>;
}

export interface CostModel {
  prices: Record<Provider, { in: number; cached: number; out: number }>;
  gpu_hourly: Record<Gpu, number>;
  levels: Record<Level, LevelCost>;
}

export interface FixedStats {
  cases: number;
  success: number;
  steps: number;
  reason_tok: number;
  out_tok_per_success: number;
  wall_s_per_success: number;
  cache_hit: number;
  forced: number;
}

export interface RouterRow {
  n: number;
  success: number;
  steps: number;
  reasoning_tok: number;
  out_tok_per_success: number;
  s_per_success: number;
  cache_hit: number;
  status: Record<string, number>;
  escalated_cases: number;
}

export interface BenchRow {
  tag: string;
  conc: number;
  n: number;
  success: number;
  tasks_per_hr: number;
  case_lat_mean: number;
  gen_tok_per_s: number;
  kv_peak: number;
  preemptions: number;
}

export const cost = costJson as unknown as CostModel;
export const fixed = fixedJson as unknown as Record<string, { overall: FixedStats }>;
export const router = routerJson as unknown as Record<"router" | "fixed_low" | "fixed_high", RouterRow>;
export const bench = benchJson as unknown as BenchRow[];

export const LEVELS: Level[] = ["low", "medium", "high", "xhigh"];

export const PROVIDERS: { key: Provider; label: string }[] = [
  { key: "doubleword", label: "Doubleword" },
  { key: "deepinfra", label: "DeepInfra" },
  { key: "together_nocache", label: "No-cache" },
];

// Rescue submits per level (Phase 4 notes). fixed_summary_v2 only counts forced.
export const RESCUE: Record<Level, number> = { low: 0, medium: 2, high: 3, xhigh: 3 };

export const REPO_URL = "https://github.com/ana-lan/thinkABR";
export const LINKEDIN_URL = "https://www.linkedin.com/in/anagha-langhe/";