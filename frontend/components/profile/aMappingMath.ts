/**
 * Pure math for the C-to-A mapping displayed on /profile.
 *
 * Mirrors backend/risk_chatbot/scoring.py:compute_a_score exactly:
 *
 *     A = clamp(10.5 − 2.375 · C, 0.5, 10.0)
 *
 * Split out into its own module so the component file stays thin and the
 * math is trivially reviewable. The Python-side consistency test in
 * tests/test_a_mapping_consistency.py verifies that the backend formula
 * produces identical numbers for the four canonical cases enumerated in
 * the JSDoc examples below — this is the shared contract between layers.
 *
 * Examples (these are the four component test cases from the spec):
 *   computeAMapping(3.00) → { raw: 3.375,  clamped: 3.375, wasClamped: false }
 *   computeAMapping(1.00) → { raw: 8.125,  clamped: 8.125, wasClamped: false }
 *   computeAMapping(5.00) → { raw: -1.375, clamped: 0.5,   wasClamped: true  }
 *   computeAMapping(1.40) → { raw: 7.175,  clamped: 7.175, wasClamped: false }
 */

export const A_INTERCEPT = 10.5;
export const A_SLOPE = 2.375;
export const A_MIN = 0.5;
export const A_MAX = 10.0;

export interface AMappingResult {
  /** Raw pre-clamp A value: intercept − slope · C. */
  raw: number;
  /** Final A value after clamping to [A_MIN, A_MAX]. */
  clamped: number;
  /** True iff the raw value fell outside [A_MIN, A_MAX] and was clamped. */
  wasClamped: boolean;
}

export function computeAMapping(compositeScore: number): AMappingResult {
  const raw = A_INTERCEPT - A_SLOPE * compositeScore;
  let clamped = raw;
  let wasClamped = false;
  if (raw < A_MIN) {
    clamped = A_MIN;
    wasClamped = true;
  } else if (raw > A_MAX) {
    clamped = A_MAX;
    wasClamped = true;
  }
  return { raw, clamped, wasClamped };
}
