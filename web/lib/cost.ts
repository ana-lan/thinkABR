import { cost, type Gpu, type Level, type Provider } from "./data";

export const gpuPerDay = (g: Gpu) => cost.gpu_hourly[g] * 24;
export const capPerDay = (l: Level) => cost.levels[l].cap_per_day;
export const apiPerTask = (l: Level, p: Provider) => cost.levels[l].api_cost_per_task[p];

// L4 cost per successful task at utilization u (0..1)
export const selfPerTask = (l: Level, g: Gpu, u: number) =>
  gpuPerDay(g) / (Math.max(u, 0.001) * capPerDay(l));

// Utilization at which one L4 matches the API per task (>1 means one L4 never wins)
export const breakEvenUtil = (l: Level, g: Gpu, p: Provider) =>
  gpuPerDay(g) / (apiPerTask(l, p) * capPerDay(l));

export const usd = (x: number) => "$" + (x >= 0.01 ? x.toFixed(3) : x.toFixed(4));
export const pct = (x: number) => `${Math.round(x * 100)}%`;
export const int = (x: number) => Math.round(x).toLocaleString("en-US");