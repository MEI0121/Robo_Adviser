import type { OptimizationResponse } from "@/types";

/**
 * True when we must call POST /optimize again: no cache, or cache was produced
 * for a different risk aversion A than the current profile.
 */
export function shouldRefreshOptimization(
  result: OptimizationResponse | null,
  targetA: number
): boolean {
  if (!result?.metadata) return true;
  const cachedA = result.metadata.risk_aversion_coefficient;
  return Math.abs(cachedA - targetA) > 1e-5;
}
