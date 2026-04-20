/**
 * Shared constraints for POST /api/v1/optimize.
 *
 * Without a cap on single-asset weight, long-only mean–variance optimization
 * often concentrates 100% in the highest-mu asset (e.g. a tech-heavy ETF), which
 * looks "wrong" in a diversified robo-adviser demo. PRD allows max_single_weight
 * in [0.1, 1.0]; we default to 40% so allocations spread across the universe.
 */
export const DEFAULT_OPTIMIZE_CONSTRAINTS = {
  allow_short_selling: false,
  max_single_weight: 0.4,
} as const;
