"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useAppStore } from "@/store/useAppStore";
import { fetchFunds, runOptimization } from "@/lib/api";
import { DEFAULT_OPTIMIZE_CONSTRAINTS } from "@/lib/optimizationDefaults";
import { shouldRefreshOptimization } from "@/lib/optimizationRefresh";
import type { Fund } from "@/types";

// WCAG AA compliant 10-color palette
const COLORS = [
  "#3b82f6", // blue-500
  "#8b5cf6", // violet-500
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#ef4444", // red-500
  "#06b6d4", // cyan-500
  "#f97316", // orange-500
  "#84cc16", // lime-500
  "#ec4899", // pink-500
  "#a78bfa", // violet-400
];

const ASSET_CLASS_BADGE: Record<string, string> = {
  "Equity-Global": "bg-blue-500/20 text-blue-300",
  "Equity-Regional": "bg-violet-500/20 text-violet-300",
  "Fixed-Income": "bg-emerald-500/20 text-emerald-300",
  "Multi-Asset": "bg-amber-500/20 text-amber-300",
  REIT: "bg-rose-500/20 text-rose-300",
  Commodity: "bg-yellow-500/20 text-yellow-300",
};

interface PieEntry {
  name: string;
  shortName: string;
  fund_code: string;
  asset_class: string;
  weight: number; // 0-1
  weightPct: number; // 0-100
  expectedContribution: number; // weight × fund annualized return
  color: string;
}

type SortKey = "weightPct" | "fund_name" | "asset_class" | "expectedContribution";

// Custom Recharts tooltip
function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: PieEntry }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-xl border border-slate-600 bg-slate-800 p-3 shadow-xl text-sm min-w-[200px]">
      <p className="font-semibold text-white mb-1">{d.name}</p>
      <p className="text-slate-400 text-xs mb-2">{d.asset_class}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-slate-400">Weight</span>
          <span className="font-medium text-white">{d.weightPct.toFixed(2)}%</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-slate-400">Expected Contribution</span>
          <span className="font-medium text-emerald-300">
            {(d.expectedContribution * 100).toFixed(3)}%
          </span>
        </div>
      </div>
    </div>
  );
}

// Custom pie label (only shows if weight > 3%)
function renderCustomLabel({
  cx,
  cy,
  midAngle,
  innerRadius,
  outerRadius,
  weightPct,
}: {
  cx: number;
  cy: number;
  midAngle: number;
  innerRadius: number;
  outerRadius: number;
  weightPct: number;
}) {
  if (weightPct < 3) return null;
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      fontSize={11}
      fontWeight="600"
    >
      {weightPct.toFixed(1)}%
    </text>
  );
}

export default function PortfolioPage() {
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
  const [sortKey, setSortKey] = useState<SortKey>("weightPct");
  const [sortAsc, setSortAsc] = useState(false);

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
            err instanceof Error ? err.message : "Backend unreachable on port 8000."
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

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-slate-400">
          <div className="animate-spin h-10 w-10 border-2 border-blue-500/30 border-t-blue-500 rounded-full" />
          <p>Loading portfolio…</p>
        </div>
      </div>
    );
  }

  // Full length-10 weight vector from backend (same order as fund_codes / mu, Sigma)
  const weights = optimizationResult?.optimal_portfolio?.weights ?? [];
  const fundCodes = optimizationResult?.optimal_portfolio?.fund_codes ?? [];

  const allHoldings: PieEntry[] = weights.map((w, i) => {
    const code = fundCodes[i] ?? "";
    const fund: Fund | undefined = funds.find((f) => f.fund_code === code) ??
      funds[i];
    return {
      name: fund?.fund_name ?? `Fund ${i + 1}`,
      shortName: (fund?.fund_name ?? `Fund ${i + 1}`)
        .split(" ")
        .slice(0, 3)
        .join(" "),
      fund_code: code,
      asset_class: fund?.asset_class ?? "Unknown",
      weight: w,
      weightPct: w * 100,
      expectedContribution: w * (fund?.annualized_return ?? 0),
      color: COLORS[i % COLORS.length],
    };
  });

  // Pie: positive weights only (Recharts); table below always shows all 10
  const pieSlices = allHoldings.filter((e) => e.weight > 1e-4);

  const activeCount = allHoldings.filter((e) => e.weight > 1e-4).length;

  // Sort table
  const sortedData = [...allHoldings].sort((a, b) => {
    let diff = 0;
    if (sortKey === "weightPct") diff = a.weightPct - b.weightPct;
    else if (sortKey === "fund_name") diff = a.name.localeCompare(b.name);
    else if (sortKey === "asset_class") diff = a.asset_class.localeCompare(b.asset_class);
    else if (sortKey === "expectedContribution")
      diff = a.expectedContribution - b.expectedContribution;
    return sortAsc ? diff : -diff;
  });

  const totalWeight = allHoldings.reduce((s, e) => s + e.weightPct, 0);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else { setSortKey(key); setSortAsc(false); }
  };

  const SortIcon = ({ col }: { col: SortKey }) =>
    sortKey === col ? (
      <span className="ml-1">{sortAsc ? "↑" : "↓"}</span>
    ) : (
      <span className="ml-1 opacity-30">↕</span>
    );

  return (
    <div className="min-h-screen bg-slate-900 px-4 py-8">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-bold text-white">Portfolio Allocation</h1>
            <p className="text-slate-400 mt-1">
              Optimal weights from last{" "}
              <code className="text-slate-500 text-xs">POST /optimize</code>
              {riskProfile ? (
                <>
                  {" "}
                  — profile{" "}
                  <span className="text-blue-400 font-medium">
                    {riskProfile.profile_label}
                  </span>
                  , optimisation A ={" "}
                  <span className="text-emerald-400 font-mono text-sm">
                    {optimizationResult?.metadata.risk_aversion_coefficient != null
                      ? optimizationResult.metadata.risk_aversion_coefficient.toFixed(4)
                      : riskProfile.risk_aversion_coefficient.toFixed(2)}
                  </span>
                </>
              ) : (
                <span className="text-slate-400"> (default A = 3.50)</span>
              )}
            </p>
            <p className="text-slate-500 text-sm mt-2 max-w-2xl leading-relaxed">
              The engine solves for a full 10-vector{" "}
              <span className="font-mono text-slate-400">w</span> (long-only, sum 1, each weight
              ≤ 40%). Many coordinates are often exactly{" "}
              <span className="text-slate-400">0</span>: Markowitz utility maximisation typically
              yields a <span className="text-slate-400">sparse</span> optimum — only assets that
              raise U at the margin get weight. Patterns like 40% / 40% / 20% usually mean two
              names hit the cap and a third fills the rest; this mix shifts with A and with μ, Σ.
            </p>
          </div>
          <button
            onClick={() => router.push("/frontier")}
            className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-2 text-sm text-slate-300 hover:bg-slate-700 transition-colors"
          >
            ← Efficient Frontier
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            ⚠ {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Pie Chart */}
          <div className="lg:col-span-2 rounded-2xl border border-slate-700 bg-slate-800/40 p-6">
            <h2 className="text-lg font-semibold text-white mb-1">Asset Allocation</h2>
            <p className="text-xs text-slate-500 mb-2 leading-relaxed">
              Donut shows <span className="text-slate-400">non-zero</span> weights only. Open{" "}
              <span className="text-slate-400">Fund Breakdown</span> for the full 10-fund vector
              (including zeros).
            </p>
            <p className="text-xs text-slate-500 mb-4">
              Total: {totalWeight.toFixed(2)}% · Non-zero positions: {activeCount}/10{" "}
              {Math.abs(totalWeight - 100) < 0.01 ? (
                <span className="text-emerald-400">✓</span>
              ) : (
                <span className="text-amber-400">⚠ rounding</span>
              )}
            </p>

            {pieSlices.length > 0 ? (
              <ResponsiveContainer
                width="100%"
                height={320}
                key={
                  optimizationResult
                    ? `${optimizationResult.metadata.computation_time_ms}-${optimizationResult.metadata.risk_aversion_coefficient}-${optimizationResult.optimal_portfolio.weights[0]?.toFixed(6) ?? ""}`
                    : "no-opt"
                }
              >
                <PieChart>
                  <Pie
                    data={pieSlices}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={120}
                    paddingAngle={2}
                    dataKey="weightPct"
                    labelLine={false}
                    label={renderCustomLabel as React.ComponentProps<typeof Pie>["label"]}
                  >
                    {pieSlices.map((entry, i) => (
                      <Cell key={entry.fund_code || i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                  <Legend
                    formatter={(value: string) => (
                      <span className="text-xs text-slate-300">{value}</span>
                    )}
                    iconType="circle"
                    iconSize={8}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-64 flex items-center justify-center text-slate-500 text-sm">
                No allocation data. Complete risk assessment first.
              </div>
            )}

            {/* Summary stats */}
            {optimizationResult && (
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
                  <p className="text-xs text-slate-400">Expected Return</p>
                  <p className="text-lg font-bold text-emerald-400">
                    {(optimizationResult.optimal_portfolio.expected_annual_return * 100).toFixed(2)}%
                  </p>
                </div>
                <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
                  <p className="text-xs text-slate-400">Volatility</p>
                  <p className="text-lg font-bold text-amber-400">
                    {(optimizationResult.optimal_portfolio.annual_volatility * 100).toFixed(2)}%
                  </p>
                </div>
                <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
                  <p className="text-xs text-slate-400">Sharpe Ratio</p>
                  <p className="text-lg font-bold text-blue-400">
                    {optimizationResult.optimal_portfolio.sharpe_ratio.toFixed(4)}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
                  <p className="text-xs text-slate-400">Non-zero weights</p>
                  <p className="text-lg font-bold text-violet-400">
                    {activeCount} <span className="text-sm font-normal text-slate-500">/ 10</span>
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Table */}
          <div className="lg:col-span-3 rounded-2xl border border-slate-700 bg-slate-800/40 p-6 overflow-x-auto">
            <h2 className="text-lg font-semibold text-white mb-1">Fund Breakdown</h2>
            <p className="text-xs text-slate-500 mb-4">
              All 10 assets in μ / Σ order. Zeros are valid optimal coordinates (KKT inactive constraints).
            </p>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  {(
                    [
                      { key: "fund_name" as SortKey, label: "Fund Name" },
                      { key: "asset_class" as SortKey, label: "Asset Class" },
                      { key: "weightPct" as SortKey, label: "Weight %" },
                      { key: "expectedContribution" as SortKey, label: "Exp. Contribution" },
                    ] as { key: SortKey; label: string }[]
                  ).map((col) => (
                    <th
                      key={col.key}
                      onClick={() => handleSort(col.key)}
                      className="pb-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wide cursor-pointer hover:text-slate-200 transition-colors select-none"
                    >
                      {col.label}
                      <SortIcon col={col.key} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedData.map((entry, i) => (
                  <tr
                    key={entry.fund_code || i}
                    className={`border-b border-slate-700/40 hover:bg-slate-700/20 transition-colors ${
                      entry.weight <= 1e-4 ? "opacity-55" : ""
                    }`}
                  >
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2">
                        <span
                          className="h-3 w-3 rounded-full flex-shrink-0"
                          style={{ backgroundColor: entry.color }}
                        />
                        <div>
                          <p className="text-slate-100 font-medium leading-tight">
                            {entry.shortName}
                          </p>
                          <p className="text-slate-500 text-xs font-mono">
                            {entry.fund_code}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 pr-4">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                          ASSET_CLASS_BADGE[entry.asset_class] ??
                          "bg-slate-700 text-slate-300"
                        }`}
                      >
                        {entry.asset_class}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2">
                        <div className="w-20 h-1.5 rounded-full bg-slate-700">
                          <div
                            className="h-1.5 rounded-full"
                            style={{
                              width: `${entry.weightPct > 0.01 ? Math.min(entry.weightPct, 100) : 0}%`,
                              backgroundColor: entry.color,
                            }}
                          />
                        </div>
                        <span
                          className={`font-semibold w-14 text-right ${
                            entry.weight <= 1e-4 ? "text-slate-500" : "text-white"
                          }`}
                        >
                          {entry.weightPct.toFixed(2)}%
                        </span>
                      </div>
                    </td>
                    <td className="py-3 text-right">
                      <span className="text-emerald-300 font-medium">
                        {(entry.expectedContribution * 100).toFixed(3)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-slate-600">
                  <td colSpan={2} className="pt-3 text-xs text-slate-500">
                    * Expected contribution = weight × annualised fund return
                  </td>
                  <td className="pt-3 text-right text-sm font-bold text-white">
                    {totalWeight.toFixed(2)}%
                  </td>
                  <td className="pt-3 text-right text-sm font-bold text-emerald-300">
                    {(sortedData.reduce((s, e) => s + e.expectedContribution, 0) * 100).toFixed(3)}%
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        {/* Utility formula reminder */}
        {optimizationResult && riskProfile && (
          <div className="mt-6 rounded-2xl border border-slate-700 bg-slate-800/40 p-5">
            <h3 className="text-sm font-medium text-slate-400 mb-3">
              Optimisation Objective
            </h3>
            <div className="font-mono text-sm text-slate-300 bg-slate-900/60 rounded-xl p-4">
              <span className="text-blue-400">max U(w)</span> ={" "}
              <span className="text-emerald-400">
                E(rₚ) = {(optimizationResult.optimal_portfolio.expected_annual_return * 100).toFixed(4)}%
              </span>{" "}
              −{" "}
              <span className="text-amber-400">
                ½ · {riskProfile.risk_aversion_coefficient.toFixed(2)} ·{" "}
                {(optimizationResult.optimal_portfolio.annual_volatility ** 2 * 100).toFixed(4)}%
              </span>{" "}
              ={" "}
              <span className="text-white font-bold">
                {optimizationResult.optimal_portfolio.utility_score !== undefined
                  ? optimizationResult.optimal_portfolio.utility_score.toFixed(6)
                  : (
                      optimizationResult.optimal_portfolio.expected_annual_return -
                      0.5 *
                        riskProfile.risk_aversion_coefficient *
                        optimizationResult.optimal_portfolio.annual_volatility ** 2
                    ).toFixed(6)}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Solved via SLSQP (SciPy) with long-only constraints. Tolerance: ftol=1e-9.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
