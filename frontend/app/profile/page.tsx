"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/store/useAppStore";
import { runOptimization } from "@/lib/api";
import { DEFAULT_OPTIMIZE_CONSTRAINTS } from "@/lib/optimizationDefaults";
import type { ProfileLabel } from "@/types";

// Per-profile visual config
const PROFILE_CONFIG: Record<
  ProfileLabel,
  { gradient: string; badge: string; icon: string; desc: string }
> = {
  Conservative: {
    gradient: "from-emerald-600 to-teal-600",
    badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
    icon: "🛡️",
    desc: "Capital preservation is paramount. Low-risk, stable income-generating assets dominate your allocation.",
  },
  "Moderately Conservative": {
    gradient: "from-cyan-600 to-blue-600",
    badge: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
    icon: "⚓",
    desc: "Modest growth with strong downside protection. Balanced tilt toward fixed income with selective equity exposure.",
  },
  Moderate: {
    gradient: "from-blue-600 to-violet-600",
    badge: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    icon: "⚖️",
    desc: "Balanced risk-return profile. Equal weight to growth assets and defensive positions.",
  },
  "Moderately Aggressive": {
    gradient: "from-violet-600 to-purple-600",
    badge: "bg-violet-500/20 text-violet-300 border-violet-500/30",
    icon: "🚀",
    desc: "Growth-oriented with tactical defensive overlay. Higher equity allocation, accepting short-term volatility.",
  },
  Aggressive: {
    gradient: "from-amber-600 to-rose-600",
    badge: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    icon: "⚡",
    desc: "Maximum return pursuit. Concentrated equity and high-yield exposure. High volatility tolerance.",
  },
};

const DIMENSION_LABELS: Record<string, string> = {
  horizon: "Investment Horizon",
  drawdown: "Drawdown Tolerance",
  loss_reaction: "Loss Reaction",
  income_stability: "Income Stability",
  experience: "Experience Level",
};

export default function ProfilePage() {
  const router = useRouter();
  const { setOptimizationResult } = useAppStore();
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [optError, setOptError] = useState<string | null>(null);

  const riskProfile = useAppStore((s) => s.riskProfile);

  // Guard: redirect back if no profile
  useEffect(() => {
    if (!riskProfile) {
      router.replace("/assess");
    }
  }, [riskProfile, router]);

  if (!riskProfile) return null;

  const config = PROFILE_CONFIG[riskProfile.profile_label];
  const A = riskProfile.risk_aversion_coefficient;

  // Utility = E(r_p) - 0.5 * A * σ²; displayed conceptually for this investor
  const handleProceed = async () => {
    setIsOptimizing(true);
    setOptError(null);
    try {
      // Always read the latest profile from the store at click time (avoids stale render).
      const live = useAppStore.getState().riskProfile;
      if (!live) {
        setOptError("No risk profile in session. Return to the assessment.");
        return;
      }
      const aRun = Number(live.risk_aversion_coefficient);
      const result = await runOptimization({
        risk_aversion_coefficient: aRun,
        constraints: { ...DEFAULT_OPTIMIZE_CONSTRAINTS },
      });
      setOptimizationResult(result);
      router.push("/frontier");
    } catch (err) {
      setOptError(
        err instanceof Error
          ? err.message
          : "Optimization server unreachable. Ensure FastAPI backend is running."
      );
    } finally {
      setIsOptimizing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 px-4 py-12">
      <div className="mx-auto max-w-3xl">
        {/* Title */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-white mb-2">
            Your Risk Profile
          </h1>
          <p className="text-slate-400">
            Based on your {riskProfile.conversation_turns}-turn assessment
          </p>
        </div>

        {/* Hero card */}
        <div
          className={`mb-6 rounded-2xl bg-gradient-to-br ${config.gradient} p-8 text-white shadow-2xl`}
        >
          <div className="flex items-start justify-between mb-4">
            <div>
              <span className="text-6xl">{config.icon}</span>
            </div>
            <div className="text-right">
              <div className="text-5xl font-extrabold">{A.toFixed(2)}</div>
              <div className="text-sm opacity-75 mt-0.5">
                Risk Aversion Coefficient A
              </div>
            </div>
          </div>
          <h2 className="text-3xl font-bold mb-3">{riskProfile.profile_label}</h2>
          <p className="text-white/80 leading-relaxed">{config.desc}</p>
        </div>

        {/* Formula showcase */}
        <div className="mb-6 rounded-2xl border border-slate-700 bg-slate-800/60 p-6">
          <h3 className="text-sm font-medium text-slate-400 mb-4 uppercase tracking-wider">
            Utility Function Parameters
          </h3>
          <div className="rounded-xl bg-slate-900/60 p-4 font-mono text-sm text-slate-300 mb-3">
            <span className="text-blue-400">U(w)</span> ={" "}
            <span className="text-emerald-400">E(rₚ)</span> −{" "}
            <span className="text-amber-400">½ · {A.toFixed(2)}</span> ·{" "}
            <span className="text-violet-400">σₚ²</span>
          </div>
          <p className="text-xs text-slate-500">
            The optimizer maximises this utility over the{" "}
            <span className="text-slate-400">long-only constrained</span> weight
            space w ∈ ℝ¹⁰. Higher A penalises variance more heavily.
          </p>
        </div>

        {/* Dimension scores */}
        <div className="mb-6 rounded-2xl border border-slate-700 bg-slate-800/60 p-6">
          <h3 className="text-sm font-medium text-slate-400 mb-4 uppercase tracking-wider">
            Dimension Scores
          </h3>
          <div className="space-y-3">
            {Object.entries(riskProfile.dimension_scores).map(([key, score]) => (
              <div key={key} className="flex items-center gap-3">
                <span className="w-40 text-sm text-slate-300 flex-shrink-0">
                  {DIMENSION_LABELS[key] ?? key}
                </span>
                <div className="flex-1 h-2 rounded-full bg-slate-700">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-violet-500 transition-all duration-700"
                    style={{ width: `${(score / 5) * 100}%` }}
                  />
                </div>
                <span className="w-8 text-right text-sm font-medium text-slate-200">
                  {score}/5
                </span>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-slate-700 flex justify-between text-sm">
            <span className="text-slate-400">Composite Score C</span>
            <span className="font-semibold text-white">
              {riskProfile.composite_score.toFixed(2)} / 5.00
            </span>
          </div>
        </div>

        {/* A-score scale */}
        <div className="mb-8 rounded-2xl border border-slate-700 bg-slate-800/60 p-6">
          <h3 className="text-sm font-medium text-slate-400 mb-4 uppercase tracking-wider">
            Risk Aversion Scale
          </h3>
          <div className="relative h-4 rounded-full bg-gradient-to-r from-amber-500 via-blue-500 to-emerald-500">
            {/* Pointer */}
            <div
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-6 w-6 rounded-full border-2 border-white bg-white shadow-lg"
              style={{ left: `${((A - 0.5) / 9.5) * 100}%` }}
            >
              <div className="absolute -top-7 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs font-bold text-white">
                {A.toFixed(1)}
              </div>
            </div>
          </div>
          <div className="mt-2 flex justify-between text-xs text-slate-500">
            <span>0.5 — Aggressive</span>
            <span>10.0 — Conservative</span>
          </div>
        </div>

        {/* Error */}
        {optError && (
          <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            ⚠ {optError}
          </div>
        )}

        {/* CTA */}
        <div className="flex gap-4">
          <button
            onClick={() => router.push("/assess")}
            className="flex-1 rounded-xl border border-slate-600 bg-slate-800 px-6 py-4 text-slate-300 font-semibold hover:bg-slate-700 transition-colors"
          >
            ← Redo Assessment
          </button>
          <button
            onClick={handleProceed}
            disabled={isOptimizing}
            className="flex-[2] rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-6 py-4 font-semibold text-white transition-all hover:from-blue-500 hover:to-violet-500 hover:shadow-lg hover:shadow-blue-500/20 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isOptimizing ? (
              <span className="flex items-center justify-center gap-2">
                <span className="animate-spin inline-block h-4 w-4 border-2 border-white/30 border-t-white rounded-full" />
                Optimising Portfolio…
              </span>
            ) : (
              "Compute Optimal Portfolio →"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
