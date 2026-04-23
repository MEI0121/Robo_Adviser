"use client";

import { computeAMapping } from "./aMappingMath";

interface Props {
  /** Composite score C = arithmetic mean of the five dimension scores, in [1, 5]. */
  composite_score: number;
  /** Risk aversion coefficient A from the backend, post-clamp. In [0.5, 10.0]. */
  risk_aversion_coefficient: number;
}

/**
 * "How your A was computed" — shows the canonical linear formula with
 * the user's own composite score substituted in, labels whether clamping
 * fired, and explains the formula in plain English.
 *
 * Styled to match the "Utility Function Parameters" card on /profile.
 * Uses plain HTML/CSS (no KaTeX / MathJax); the formula is simple enough
 * that the monospace rendering reads cleanly.
 */
export function AMappingCard({
  composite_score,
  risk_aversion_coefficient,
}: Props) {
  const { raw, clamped, wasClamped } = computeAMapping(composite_score);

  return (
    <div className="mb-6 rounded-2xl border border-slate-700 bg-slate-800/60 p-6">
      <h3 className="text-sm font-medium text-slate-400 mb-1 uppercase tracking-wider">
        How your A was computed
      </h3>
      <p className="text-xs text-slate-500 mb-4">
        Your answers mapped to a risk aversion coefficient via the linear
        formula below.
      </p>

      {/* Canonical formula */}
      <div className="rounded-xl bg-slate-900/60 p-4 font-mono text-sm text-slate-300 mb-3">
        <span className="text-blue-400">A</span> ={" "}
        <span className="text-slate-400">clamp</span>(
        <span className="text-amber-400">10.5</span> −{" "}
        <span className="text-amber-400">2.375</span> ·{" "}
        <span className="text-emerald-400">C</span>,{" "}
        <span className="text-violet-400">0.5</span>,{" "}
        <span className="text-violet-400">10.0</span>)
      </div>

      {/* Worked calculation */}
      <div className="rounded-xl bg-slate-900/60 p-4 font-mono text-xs text-slate-300 mb-3 space-y-1.5 leading-relaxed">
        <p className="text-slate-500 uppercase tracking-wider text-[10px] mb-1">
          Your calculation
        </p>
        <div>
          <span className="text-emerald-400">C</span>{" "}
          <span className="text-slate-500">=</span>{" "}
          {composite_score.toFixed(3)}
        </div>
        <div>
          <span className="text-slate-400">raw A</span>{" "}
          <span className="text-slate-500">=</span> 10.5 − 2.375 ×{" "}
          {composite_score.toFixed(3)}
        </div>
        <div className="pl-[4.6rem]">
          <span className="text-slate-500">=</span>{" "}
          <span className="text-slate-100">{raw.toFixed(3)}</span>
        </div>
        <div>
          <span className="text-blue-400">A</span>{" "}
          <span className="text-slate-500">=</span> clamp({raw.toFixed(3)},
          0.5, 10.0){" "}
          <span className="text-slate-500">=</span>{" "}
          <span className="text-white font-bold">{clamped.toFixed(2)}</span>
        </div>
      </div>

      {/* Clamp indicator — amber if clamping fired, grey otherwise */}
      {wasClamped ? (
        <p className="text-xs text-amber-400 mb-3">
          Your raw A would have been {raw.toFixed(3)}, but is clamped to the
          [0.5, 10.0] valid range.
        </p>
      ) : (
        <p className="text-xs text-slate-500 mb-3">
          No clamping applied; raw A is within the valid [0.5, 10.0] range.
        </p>
      )}

      {/* Plain-language explanation */}
      <p className="text-xs text-slate-500 leading-relaxed">
        The formula weights each of your five psychographic dimensions equally
        via their arithmetic mean <span className="text-emerald-400">C</span>,
        then translates <span className="text-emerald-400">C</span> to the
        risk aversion coefficient <span className="text-blue-400">A</span>{" "}
        used by the Markowitz optimizer. Lower{" "}
        <span className="text-emerald-400">C</span> values (more conservative
        answers) produce higher <span className="text-blue-400">A</span>{" "}
        (more variance penalty); higher{" "}
        <span className="text-emerald-400">C</span> values produce lower{" "}
        <span className="text-blue-400">A</span> (less variance penalty). The
        formula's slope of 2.375 and intercept of 10.5 are calibrated so that
        typical answers produce <span className="text-blue-400">A</span>{" "}
        values well within the [0.5, 10.0] operational range.
      </p>

      {/* Sanity note if backend's A diverges from our recomputed clamp */}
      {Math.abs(clamped - risk_aversion_coefficient) > 1e-6 && (
        <p className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          Diagnostic: backend-reported A ={" "}
          {risk_aversion_coefficient.toFixed(4)} differs from the formula's
          result {clamped.toFixed(4)}. This should never happen — please
          report.
        </p>
      )}
    </div>
  );
}
