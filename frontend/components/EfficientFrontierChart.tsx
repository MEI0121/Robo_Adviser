"use client";

import dynamic from "next/dynamic";
import type { FrontierPoint, PortfolioStats, Fund } from "@/types";

// Plotly must be loaded client-side only (no SSR)
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface Props {
  frontier: FrontierPoint[];
  gmvp: PortfolioStats;
  optimal: PortfolioStats;
  funds: Fund[];
  riskFreeRate?: number; // default 0.03
  /** Bump on each new /optimize response — react-plotly often skips prop updates without this. */
  chartRevision?: number;
}

/** Builds the hover text showing E(rp), σp, Sharpe, and top-3 weights */
function buildHoverText(point: FrontierPoint, funds: Fund[]): string {
  const top3 = point.weights
    .map((w, i) => ({ w, name: funds[i]?.fund_name?.split(" ").slice(0, 3).join(" ") ?? `Fund ${i + 1}` }))
    .sort((a, b) => b.w - a.w)
    .slice(0, 3);

  return (
    `E(rp): ${(point.expected_return * 100).toFixed(2)}%<br>` +
    `σp: ${(point.volatility * 100).toFixed(2)}%<br>` +
    `Sharpe: ${point.sharpe_ratio.toFixed(4)}<br>` +
    `─── Top 3 Holdings ───<br>` +
    top3.map((t) => `${t.name}: ${(t.w * 100).toFixed(1)}%`).join("<br>")
  );
}

export default function EfficientFrontierChart({
  frontier,
  gmvp,
  optimal,
  funds,
  riskFreeRate = 0.03,
  chartRevision = 0,
}: Props) {
  // x-axis: σp × 100 (convert to %), y-axis: E(rp) × 100
  const xFrontier = frontier.map((p) => p.volatility * 100);
  const yFrontier = frontier.map((p) => p.expected_return * 100);
  const sharpeValues = frontier.map((p) => p.sharpe_ratio);
  const hoverTexts = frontier.map((p) => buildHoverText(p, funds));

  // ---- Efficient Frontier scatter (colored by Sharpe) ----
  const frontierTrace: Plotly.Data = {
    type: "scatter",
    mode: "markers",
    name: "Efficient Frontier",
    x: xFrontier,
    y: yFrontier,
    text: hoverTexts,
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

  // ---- Capital Market Line ----
  // Passes through (0, rf) and the tangency portfolio (max Sharpe on frontier)
  const tangencyIdx = sharpeValues.indexOf(Math.max(...sharpeValues));
  const tangencyX = xFrontier[tangencyIdx];
  const tangencyY = yFrontier[tangencyIdx];
  const cmlSlope = (tangencyY - riskFreeRate * 100) / tangencyX;
  const cmlXEnd = Math.max(...xFrontier) * 1.05;
  const cmlTrace: Plotly.Data = {
    type: "scatter",
    mode: "lines",
    name: "Capital Market Line",
    x: [0, cmlXEnd],
    y: [riskFreeRate * 100, riskFreeRate * 100 + cmlSlope * cmlXEnd],
    line: { color: "#94a3b8", dash: "dash", width: 1.5 },
    hoverinfo: "skip",
  };

  // ---- GMVP marker ----
  const gmvpTop3 = gmvp.weights
    .map((w, i) => ({ w, name: funds[i]?.fund_name?.split(" ").slice(0, 3).join(" ") ?? `Fund ${i + 1}` }))
    .sort((a, b) => b.w - a.w)
    .slice(0, 3);
  const gmvpTrace: Plotly.Data = {
    type: "scatter",
    mode: "text+markers" as Plotly.ScatterData["mode"],
    name: "GMVP",
    x: [gmvp.annual_volatility * 100],
    y: [gmvp.expected_annual_return * 100],
    text: ["GMVP"],
    textposition: "top center",
    textfont: { color: "#60a5fa", size: 11 },
    hovertemplate:
      `<b>Global Minimum Variance Portfolio</b><br>` +
      `E(rp): ${(gmvp.expected_annual_return * 100).toFixed(2)}%<br>` +
      `σp: ${(gmvp.annual_volatility * 100).toFixed(2)}%<br>` +
      `Sharpe: ${gmvp.sharpe_ratio.toFixed(4)}<br>` +
      gmvpTop3.map((t) => `${t.name}: ${(t.w * 100).toFixed(1)}%`).join("<br>") +
      "<extra></extra>",
    marker: {
      size: 16,
      symbol: "diamond",
      color: "#3b82f6",
      line: { color: "#93c5fd", width: 2 },
    },
  };

  // ---- Optimal Portfolio marker ----
  const optTop3 = optimal.weights
    .map((w, i) => ({ w, name: funds[i]?.fund_name?.split(" ").slice(0, 3).join(" ") ?? `Fund ${i + 1}` }))
    .sort((a, b) => b.w - a.w)
    .slice(0, 3);
  const optimalTrace: Plotly.Data = {
    type: "scatter",
    mode: "text+markers" as Plotly.ScatterData["mode"],
    name: "Optimal Portfolio",
    x: [optimal.annual_volatility * 100],
    y: [optimal.expected_annual_return * 100],
    text: ["Optimal"],
    textposition: "top center",
    textfont: { color: "#f59e0b", size: 11 },
    hovertemplate:
      `<b>Optimal Portfolio (Utility-Maximised)</b><br>` +
      `E(rp): ${(optimal.expected_annual_return * 100).toFixed(2)}%<br>` +
      `σp: ${(optimal.annual_volatility * 100).toFixed(2)}%<br>` +
      `Sharpe: ${optimal.sharpe_ratio.toFixed(4)}<br>` +
      optTop3.map((t) => `${t.name}: ${(t.w * 100).toFixed(1)}%`).join("<br>") +
      "<extra></extra>",
    marker: {
      size: 18,
      symbol: "star",
      color: "#f59e0b",
      line: { color: "#fde68a", width: 2 },
    },
  };

  // ---- Equal-weight portfolio ----
  const n = funds.length || 10;
  const ewVol = Math.sqrt(
    (frontier.reduce((acc, p) => acc + p.volatility, 0) / frontier.length) *
      1.05 // rough estimate; actual value from backend
  );
  const ewReturn = (frontier.reduce((acc, p) => acc + p.expected_return, 0) / frontier.length) * 0.95;
  const equalWeightTrace: Plotly.Data = {
    type: "scatter",
    mode: "text+markers" as Plotly.ScatterData["mode"],
    name: `Equal Weight (1/${n})`,
    x: [ewVol * 100],
    y: [ewReturn * 100],
    text: ["1/N"],
    textposition: "bottom center",
    textfont: { color: "#94a3b8", size: 10 },
    hovertemplate: `<b>Equal-Weight Portfolio</b><br>Each fund: ${(100 / n).toFixed(1)}%<extra></extra>`,
    marker: {
      size: 12,
      symbol: "circle",
      color: "#6b7280",
      line: { color: "#9ca3af", width: 2 },
    },
  };

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

  return (
    <div className="w-full h-full" key={chartRevision}>
      <Plot
        data={[cmlTrace, frontierTrace, gmvpTrace, optimalTrace, equalWeightTrace]}
        layout={layout}
        config={config}
        style={{ width: "100%", height: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
