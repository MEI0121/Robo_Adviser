"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/store/useAppStore";
import { fetchFunds, runOptimization } from "@/lib/api";
import { DEFAULT_OPTIMIZE_CONSTRAINTS } from "@/lib/optimizationDefaults";
import { shouldRefreshOptimization } from "@/lib/optimizationRefresh";
import dynamic from "next/dynamic";
import type { OptimizationResponse } from "@/types";

const EfficientFrontierChart = dynamic(
  () => import("@/components/EfficientFrontierChart"),
  { ssr: false, loading: () => <ChartSkeleton /> }
);

function ChartSkeleton() {
  return (
    <div className="w-full h-full flex items-center justify-center bg-slate-900/60 rounded-xl">
      <div className="text-slate-500 flex flex-col items-center gap-3">
        <div className="animate-spin h-8 w-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full" />
        <span className="text-sm">Rendering frontier…</span>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        highlight
          ? "border-amber-500/40 bg-amber-500/10"
          : "border-slate-700 bg-slate-800/60"
      }`}
    >
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={`text-xl font-bold ${highlight ? "text-amber-300" : "text-white"}`}>
        {value}
      </p>
      {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function FrontierPage() {
  const router = useRouter();
  const {
    riskProfile,
    optimizationResult,
    funds,
    setOptimizationResult,
    setFunds,
  } = useAppStore();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const A = riskProfile?.risk_aversion_coefficient ?? 3.5;
    const needFunds = funds.length === 0;
    const needOpt = shouldRefreshOptimization(optimizationResult, A);
    if (!needFunds && !needOpt) return;

    let cancelled = false;

    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        if (needFunds) {
          const fundsData = await fetchFunds();
          if (cancelled) return;
          setFunds(fundsData.funds, fundsData.covariance_matrix);
        }
        const latest = useAppStore.getState().optimizationResult;
        const targetA = useAppStore.getState().riskProfile?.risk_aversion_coefficient ?? 3.5;
        if (!shouldRefreshOptimization(latest, targetA)) return;

        const result = await runOptimization({
          risk_aversion_coefficient: targetA,
          constraints: { ...DEFAULT_OPTIMIZE_CONSTRAINTS },
        });
        if (!cancelled) setOptimizationResult(result);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Backend unreachable. Start FastAPI on port 8000."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadData();
    return () => {
      cancelled = true;
    };
  }, [
    riskProfile?.risk_aversion_coefficient,
    optimizationResult,
    funds.length,
    setFunds,
    setOptimizationResult,
  ]);

  const result: OptimizationResponse | null = optimizationResult;
  const A = riskProfile?.risk_aversion_coefficient ?? 3.5;

  return (
    <div className="min-h-screen bg-slate-900 px-4 py-8">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white">Efficient Frontier</h1>
            <p className="text-slate-400 mt-1">
              100-point frontier sweep · This page uses the last{" "}
              <code className="text-slate-300">/optimize</code> run: A ={" "}
              <span className="text-blue-400 font-semibold">
                {result?.metadata.risk_aversion_coefficient != null
                  ? result.metadata.risk_aversion_coefficient.toFixed(4)
                  : A.toFixed(2)}
              </span>
              {riskProfile && (
                <span className="ml-2 text-xs text-slate-500">
                  ({riskProfile.profile_label})
                </span>
              )}
            </p>
          </div>
          <button
            onClick={() => router.push("/portfolio")}
            disabled={!result}
            className="rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-5 py-2.5 text-sm font-semibold text-white transition-all hover:from-blue-500 hover:to-violet-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            View Allocation →
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            ⚠ {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Chart — takes 3 columns */}
          <div className="lg:col-span-3 rounded-2xl border border-slate-700 bg-slate-800/40 p-4 h-[520px]">
            {loading ? (
              <ChartSkeleton />
            ) : result ? (
              <EfficientFrontierChart
                frontier={result.efficient_frontier}
                gmvp={result.gmvp}
                optimal={result.optimal_portfolio}
                funds={funds}
                riskFreeRate={result.metadata.risk_free_rate}
                chartRevision={
                  result.metadata.computation_time_ms +
                  result.metadata.risk_aversion_coefficient +
                  result.optimal_portfolio.weights[0]
                }
              />
            ) : (
              <div className="h-full flex items-center justify-center text-slate-500">
                No data yet. Complete risk assessment first.
              </div>
            )}
          </div>

          {/* Sidebar stats */}
          <div className="space-y-4">
            {/* Optimal Portfolio */}
            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-amber-400 text-lg">★</span>
                <h3 className="font-semibold text-amber-300 text-sm">Optimal Portfolio</h3>
              </div>
              {result ? (
                <div className="space-y-2">
                  <StatCard
                    label="Expected Return"
                    value={`${(result.optimal_portfolio.expected_annual_return * 100).toFixed(2)}%`}
                    highlight
                  />
                  <StatCard
                    label="Annual Volatility"
                    value={`${(result.optimal_portfolio.annual_volatility * 100).toFixed(2)}%`}
                  />
                  <StatCard
                    label="Sharpe Ratio"
                    value={result.optimal_portfolio.sharpe_ratio.toFixed(4)}
                    sub={`rf = ${((result.metadata.risk_free_rate) * 100).toFixed(1)}%`}
                  />
                  {result.optimal_portfolio.utility_score !== undefined && (
                    <StatCard
                      label="Utility U(w*)"
                      value={result.optimal_portfolio.utility_score.toFixed(4)}
                      sub={`U = E(r)−½·${A.toFixed(1)}·σ²`}
                    />
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="h-16 rounded-xl bg-slate-800 animate-pulse" />
                  ))}
                </div>
              )}
            </div>

            {/* GMVP */}
            <div className="rounded-2xl border border-blue-500/30 bg-blue-500/5 p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-blue-400">◆</span>
                <h3 className="font-semibold text-blue-300 text-sm">
                  Global Minimum Variance
                </h3>
              </div>
              {result ? (
                <div className="space-y-2">
                  <StatCard
                    label="Expected Return"
                    value={`${(result.gmvp.expected_annual_return * 100).toFixed(2)}%`}
                  />
                  <StatCard
                    label="Min Volatility"
                    value={`${(result.gmvp.annual_volatility * 100).toFixed(2)}%`}
                  />
                  <StatCard
                    label="Sharpe Ratio"
                    value={result.gmvp.sharpe_ratio.toFixed(4)}
                  />
                </div>
              ) : (
                <div className="space-y-2">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="h-16 rounded-xl bg-slate-800 animate-pulse" />
                  ))}
                </div>
              )}
            </div>

            {/* Metadata */}
            {result && (
              <div className="rounded-xl border border-slate-700 bg-slate-800/40 p-3 text-xs text-slate-500 space-y-1">
                <p>Method: <span className="text-slate-400">{result.metadata.optimization_method}</span></p>
                <p>Assets: <span className="text-slate-400">{result.metadata.num_assets}</span></p>
                <p>Data: <span className="text-slate-400">{result.metadata.data_start_date} → {result.metadata.data_end_date}</span></p>
                <p>Computed: <span className="text-slate-400">{result.metadata.computation_time_ms}ms</span></p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
