"use client";

import dynamic from "next/dynamic";
import type {
  FrontierPoint,
  PortfolioStats,
  TangencyStats,
  Fund,
} from "@/types";
import { RISK_FREE_RATE } from "@/lib/constants";

// Plotly must be loaded client-side only (no SSR)
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface Props {
  /** Long-only efficient frontier (existing Sharpe-colored trace). */
  frontier: FrontierPoint[];
  /** Short-allowed efficient frontier (w ∈ [-1, 2]), dashed line trace. */
  frontierShortAllowed: FrontierPoint[];
  /** Long-only GMVP (filled teal diamond). */
  gmvp: PortfolioStats;
  /** Short-allowed GMVP (hollow teal diamond). */
  gmvpShortAllowed: PortfolioStats;
  /** Long-only tangency — CML anchor (filled gold star). */
  tangency: TangencyStats;
  /** Short-allowed tangency (hollow gold star). */
  tangencyShortAllowed: TangencyStats;
  /** User's utility-maximizing portfolio (existing amber star). */
  optimal: PortfolioStats;
  /** True equal-weight benchmark from the backend (replaces prior averaging hack). */
  equalWeight: PortfolioStats;
  /** Per-fund metadata for individual-fund scatter dots and hover tooltips. */
  funds: Fund[];
  /** Defaults to RISK_FREE_RATE from shared constants. */
  riskFreeRate?: number;
  /** Bump on each new /optimize response — react-plotly often skips prop updates without this. */
  chartRevision?: number;
}

// ---------------------------------------------------------------------------
// Palette — kept explicit so Tangency ≠ Optimal in both color AND shape.
// ---------------------------------------------------------------------------
const COLOR = {
  frontierShortAllowed: "#6B9EF5", // muted blue dashed line
  fundDot: "#9ca3af",              // slate-400
  gmvpFilled: "#14b8a6",           // teal-500
  gmvpHollow: "#5eead4",           // teal-300 outline
  tangencyFilled: "#eab308",       // yellow-500 (gold)
  tangencyHollow: "#facc15",       // yellow-400 outline
  optimalFilled: "#f59e0b",        // amber-500 (existing; distinct from gold)
  optimalOutline: "#fde68a",
  equalWeight: "#6b7280",          // gray-500 (existing)
  cml: "#94a3b8",                  // slate-400 dashed
} as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function shortName(fund: Fund | undefined, fallback: string): string {
  return fund?.fund_name?.split(" ").slice(0, 3).join(" ") ?? fallback;
}

function top3WeightsHover(weights: number[], funds: Fund[]): string {
  return weights
    .map((w, i) => ({ w, name: shortName(funds[i], `Fund ${i + 1}`) }))
    .sort((a, b) => b.w - a.w)
    .slice(0, 3)
    .map((t) => `${t.name}: ${(t.w * 100).toFixed(1)}%`)
    .join("<br>");
}

/** Hover text for frontier scatter points (includes top-3 holdings). */
function frontierHover(p: FrontierPoint, funds: Fund[]): string {
  return (
    `E(rp): ${(p.expected_return * 100).toFixed(2)}%<br>` +
    `σp: ${(p.volatility * 100).toFixed(2)}%<br>` +
    `Sharpe: ${p.sharpe_ratio.toFixed(4)}<br>` +
    `─── Top 3 Holdings ───<br>` +
    top3WeightsHover(p.weights, funds)
  );
}

/** Hover template for a special-point marker (GMVPs, tangencies, optimal, EW). */
function specialPointHover(opts: {
  title: string;
  er: number;
  vol: number;
  sharpe: number;
  regime?: "long-only" | "w ∈ [-1, 2]";
  topHoldings?: string;
  solverPath?: string | null;
}): string {
  const { title, er, vol, sharpe, regime, topHoldings, solverPath } = opts;
  const lines = [
    `<b>${title}</b>`,
    `E(rp): ${(er * 100).toFixed(2)}%`,
    `σp: ${(vol * 100).toFixed(2)}%`,
    `Sharpe: ${sharpe.toFixed(4)}`,
  ];
  if (regime) lines.push(`Constraints: ${regime}`);
  if (solverPath) lines.push(`solver: ${solverPath}`);
  if (topHoldings) lines.push(`─── Top 3 Holdings ───`, topHoldings);
  return lines.join("<br>") + "<extra></extra>";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function EfficientFrontierChart({
  frontier,
  frontierShortAllowed,
  gmvp,
  gmvpShortAllowed,
  tangency,
  tangencyShortAllowed,
  optimal,
  equalWeight,
  funds,
  riskFreeRate = RISK_FREE_RATE,
  chartRevision = 0,
}: Props) {
  // ------------------------------------------------------------------------
  // GROUP 1: Frontiers (long-only EF, short-allowed EF, fund dots, CML)
  // ------------------------------------------------------------------------

  // Long-only efficient frontier — existing Sharpe-colored scatter, relabel only.
  const xFrontier = frontier.map((p) => p.volatility * 100);
  const yFrontier = frontier.map((p) => p.expected_return * 100);
  const sharpeValues = frontier.map((p) => p.sharpe_ratio);
  const frontierHoverTexts = frontier.map((p) => frontierHover(p, funds));

  const frontierTrace: Plotly.Data = {
    type: "scatter",
    mode: "markers",
    name: "EF (long-only, w ≥ 0)",
    legendgroup: "frontiers",
    legendgrouptitle: { text: "Frontiers" },
    x: xFrontier,
    y: yFrontier,
    text: frontierHoverTexts,
    hovertemplate: "%{text}<extra></extra>",
    marker: {
      size: 7,
      color: sharpeValues,
      colorscale: "RdYlGn",
      showscale: true,
      colorbar: {
        title: { text: "Sharpe Ratio" } as Plotly.ColorBarTitle,
        thickness: 14,
        tickfont: { color: "#94a3b8", size: 11 },
        bgcolor: "rgba(0,0,0,0)",
        bordercolor: "#334155",
      },
      line: { width: 0 },
    },
  };

  // Short-allowed frontier — dashed line, no colormap.
  const xFrontierShort = frontierShortAllowed.map((p) => p.volatility * 100);
  const yFrontierShort = frontierShortAllowed.map((p) => p.expected_return * 100);
  const frontierShortHoverTexts = frontierShortAllowed.map((p) =>
    frontierHover(p, funds),
  );

  const frontierShortTrace: Plotly.Data = {
    type: "scatter",
    mode: "lines",
    name: "EF (w ∈ [−1, 2])",
    legendgroup: "frontiers",
    x: xFrontierShort,
    y: yFrontierShort,
    text: frontierShortHoverTexts,
    hovertemplate: "%{text}<extra></extra>",
    line: { color: COLOR.frontierShortAllowed, dash: "dash", width: 1.8 },
  };

  // Individual fund scatter — σ, E[r] directly from fund metadata (already annualized).
  // Labels use `proxy_ticker` (short, readable) instead of the FSMOne
  // `fund_code` which is too long for inline chart annotation. Hover text
  // shows the full FSMOne fund_name.
  const xFunds = funds.map((f) => f.annualized_volatility * 100);
  const yFunds = funds.map((f) => f.annualized_return * 100);
  const fundLabels = funds.map((f) => f.proxy_ticker);
  const fundHoverTexts = funds.map(
    (f) =>
      `<b>${f.fund_name}</b><br>` +
      `Proxy: ${f.proxy_ticker} (${f.proxy_provider})<br>` +
      `E(rp): ${(f.annualized_return * 100).toFixed(2)}%<br>` +
      `σp: ${(f.annualized_volatility * 100).toFixed(2)}%<br>` +
      `Sharpe: ${f.sharpe_ratio.toFixed(4)}<extra></extra>`,
  );

  const fundDotsTrace: Plotly.Data = {
    type: "scatter",
    mode: "markers+text" as Plotly.ScatterData["mode"],
    name: "Individual funds",
    legendgroup: "frontiers",
    x: xFunds,
    y: yFunds,
    text: fundLabels,
    textposition: "middle right",
    textfont: { color: COLOR.fundDot, size: 10 },
    hovertemplate: fundHoverTexts,
    marker: {
      size: 8,
      symbol: "circle",
      color: COLOR.fundDot,
      line: { color: "#4b5563", width: 1 },
    },
  };

  // Capital Market Line — anchored on the PROPER tangency (not max-Sharpe sample).
  const tangencyXpct = tangency.annual_volatility * 100;
  const tangencyYpct = tangency.expected_annual_return * 100;
  const rfPct = riskFreeRate * 100;
  const cmlSlope =
    tangencyXpct > 1e-9 ? (tangencyYpct - rfPct) / tangencyXpct : 0;
  // Extend to a little past the rightmost point on either frontier
  const cmlXEnd =
    Math.max(
      ...xFrontier,
      ...(xFrontierShort.length > 0 ? xFrontierShort : [0]),
    ) * 1.05;

  const cmlTrace: Plotly.Data = {
    type: "scatter",
    mode: "lines",
    name: "CML",
    legendgroup: "frontiers",
    x: [0, cmlXEnd],
    y: [rfPct, rfPct + cmlSlope * cmlXEnd],
    line: { color: COLOR.cml, dash: "dash", width: 1.5 },
    hoverinfo: "skip",
  };

  // ------------------------------------------------------------------------
  // GROUP 2: Special points (GMVPs, tangencies, Equal Weight)
  // ------------------------------------------------------------------------

  const gmvpTrace: Plotly.Data = {
    type: "scatter",
    mode: "text+markers" as Plotly.ScatterData["mode"],
    name: "GMVP+",
    legendgroup: "special",
    legendgrouptitle: { text: "Special points" },
    x: [gmvp.annual_volatility * 100],
    y: [gmvp.expected_annual_return * 100],
    text: ["GMVP+"],
    textposition: "top center",
    textfont: { color: COLOR.gmvpFilled, size: 11 },
    hovertemplate: specialPointHover({
      title: "GMVP (long-only)",
      er: gmvp.expected_annual_return,
      vol: gmvp.annual_volatility,
      sharpe: gmvp.sharpe_ratio,
      regime: "long-only",
      topHoldings: top3WeightsHover(gmvp.weights, funds),
    }),
    marker: {
      size: 16,
      symbol: "diamond",
      color: COLOR.gmvpFilled,
      line: { color: "#ccfbf1", width: 2 },
    },
  };

  const gmvpShortTrace: Plotly.Data = {
    type: "scatter",
    mode: "text+markers" as Plotly.ScatterData["mode"],
    name: "GMVP (w ∈ [−1, 2])",
    legendgroup: "special",
    x: [gmvpShortAllowed.annual_volatility * 100],
    y: [gmvpShortAllowed.expected_annual_return * 100],
    text: ["GMVP"],
    textposition: "top center",
    textfont: { color: COLOR.gmvpHollow, size: 10 },
    hovertemplate: specialPointHover({
      title: "GMVP (w ∈ [−1, 2])",
      er: gmvpShortAllowed.expected_annual_return,
      vol: gmvpShortAllowed.annual_volatility,
      sharpe: gmvpShortAllowed.sharpe_ratio,
      regime: "w ∈ [-1, 2]",
      topHoldings: top3WeightsHover(gmvpShortAllowed.weights, funds),
    }),
    marker: {
      size: 14,
      symbol: "diamond-open",
      color: COLOR.gmvpHollow,
      line: { color: COLOR.gmvpHollow, width: 2 },
    },
  };

  const tangencyTrace: Plotly.Data = {
    type: "scatter",
    mode: "text+markers" as Plotly.ScatterData["mode"],
    name: "Tangency (long-only)",
    legendgroup: "special",
    x: [tangency.annual_volatility * 100],
    y: [tangency.expected_annual_return * 100],
    text: ["Tangency (MktPf+)"],
    textposition: "top center",
    textfont: { color: COLOR.tangencyFilled, size: 11 },
    hovertemplate: specialPointHover({
      title: "Tangency (long-only)",
      er: tangency.expected_annual_return,
      vol: tangency.annual_volatility,
      sharpe: tangency.sharpe_ratio,
      regime: "long-only",
      solverPath: tangency.solver_path,
      topHoldings: top3WeightsHover(tangency.weights, funds),
    }),
    marker: {
      size: 18,
      symbol: "star",
      color: COLOR.tangencyFilled,
      line: { color: "#fef3c7", width: 2 },
    },
  };

  // Short-allowed tangency sits near the upper endpoint of the
  // short-allowed frontier on this dataset — give it a thin dark outline
  // so it reads as "on top of" the frontier endpoint, not "inside" it.
  const tangencyShortTrace: Plotly.Data = {
    type: "scatter",
    mode: "text+markers" as Plotly.ScatterData["mode"],
    name: "Tangency (w ∈ [−1, 2])",
    legendgroup: "special",
    x: [tangencyShortAllowed.annual_volatility * 100],
    y: [tangencyShortAllowed.expected_annual_return * 100],
    text: ["Tangency"],
    textposition: "top center",
    textfont: { color: COLOR.tangencyHollow, size: 10 },
    hovertemplate: specialPointHover({
      title: "Tangency (w ∈ [−1, 2])",
      er: tangencyShortAllowed.expected_annual_return,
      vol: tangencyShortAllowed.annual_volatility,
      sharpe: tangencyShortAllowed.sharpe_ratio,
      regime: "w ∈ [-1, 2]",
      solverPath: tangencyShortAllowed.solver_path,
      topHoldings: top3WeightsHover(tangencyShortAllowed.weights, funds),
    }),
    marker: {
      size: 14,
      symbol: "star-open",
      color: COLOR.tangencyHollow,
      line: { color: "#0f172a", width: 1.5 },
    },
  };

  // Equal-weight benchmark — REWIRED to backend-computed stats (was: averaging hack).
  const n = funds.length || 10;
  const equalWeightTrace: Plotly.Data = {
    type: "scatter",
    mode: "text+markers" as Plotly.ScatterData["mode"],
    name: `Equal Weight (1/${n})`,
    legendgroup: "special",
    x: [equalWeight.annual_volatility * 100],
    y: [equalWeight.expected_annual_return * 100],
    text: ["1/N"],
    textposition: "bottom center",
    textfont: { color: "#94a3b8", size: 10 },
    hovertemplate: specialPointHover({
      title: `Equal-Weight Portfolio (1/${n})`,
      er: equalWeight.expected_annual_return,
      vol: equalWeight.annual_volatility,
      sharpe: equalWeight.sharpe_ratio,
    }),
    marker: {
      size: 12,
      symbol: "circle",
      color: COLOR.equalWeight,
      line: { color: "#9ca3af", width: 2 },
    },
  };

  // ------------------------------------------------------------------------
  // GROUP 3: Your portfolio (Optimal)
  // ------------------------------------------------------------------------

  const optimalTrace: Plotly.Data = {
    type: "scatter",
    mode: "text+markers" as Plotly.ScatterData["mode"],
    name: "Optimal",
    legendgroup: "yours",
    legendgrouptitle: { text: "Your portfolio" },
    x: [optimal.annual_volatility * 100],
    y: [optimal.expected_annual_return * 100],
    text: ["Optimal"],
    textposition: "top center",
    textfont: { color: COLOR.optimalFilled, size: 11 },
    hovertemplate: specialPointHover({
      title: "Optimal Portfolio (Utility-Maximised)",
      er: optimal.expected_annual_return,
      vol: optimal.annual_volatility,
      sharpe: optimal.sharpe_ratio,
      topHoldings: top3WeightsHover(optimal.weights, funds),
    }),
    marker: {
      size: 18,
      symbol: "star",
      color: COLOR.optimalFilled,
      line: { color: COLOR.optimalOutline, width: 2 },
    },
  };

  // ------------------------------------------------------------------------
  // Layout + config
  // ------------------------------------------------------------------------

  const layout: Partial<Plotly.Layout> = {
    datarevision: chartRevision,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(15,23,42,0.6)",
    font: { family: "Inter, sans-serif", color: "#94a3b8" },
    xaxis: {
      title: { text: "Annual Volatility (%)", font: { size: 13 } },
      gridcolor: "#1e293b",
      zerolinecolor: "#334155",
      ticksuffix: "%",
      tickfont: { size: 11 },
    },
    yaxis: {
      title: { text: "Annual Expected Return (%)", font: { size: 13 } },
      gridcolor: "#1e293b",
      zerolinecolor: "#334155",
      ticksuffix: "%",
      tickfont: { size: 11 },
    },
    legend: {
      bgcolor: "rgba(30,41,59,0.8)",
      bordercolor: "#334155",
      borderwidth: 1,
      font: { size: 11, color: "#cbd5e1" },
      groupclick: "toggleitem",
      x: 0.02,
      y: 0.98,
    },
    margin: { l: 60, r: 20, t: 20, b: 60 },
    hovermode: "closest",
    hoverlabel: {
      bgcolor: "#1e293b",
      bordercolor: "#475569",
      font: { color: "#e2e8f0", size: 12, family: "Inter, monospace" },
    },
  };

  const config: Partial<Plotly.Config> = {
    responsive: true,
    displayModeBar: true,
    modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
    displaylogo: false,
    toImageButtonOptions: {
      format: "png",
      filename: "efficient_frontier",
      height: 600,
      width: 1000,
      scale: 2,
    },
  };

  // Stacking order (bottom → top): CML, short-allowed EF, long-only EF,
  // fund dots, GMVP+, GMVP hollow, tangency filled, tangency hollow,
  // equal weight, optimal (top so user's marker is never occluded).
  const data: Plotly.Data[] = [
    cmlTrace,
    frontierShortTrace,
    frontierTrace,
    fundDotsTrace,
    gmvpTrace,
    gmvpShortTrace,
    tangencyTrace,
    tangencyShortTrace,
    equalWeightTrace,
    optimalTrace,
  ];

  return (
    <div className="w-full h-full" key={chartRevision}>
      <Plot
        data={data}
        layout={layout}
        config={config}
        style={{ width: "100%", height: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
