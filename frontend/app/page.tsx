import Link from "next/link";
import { MethodologyNote } from "@/components/MethodologyNote";

const FEATURES = [
  {
    icon: "🤖",
    title: "AI Risk Profiling",
    desc: "LangGraph-powered multi-turn chatbot precisely quantifies your risk aversion coefficient A ∈ [0.5, 10.0] across 5 psychographic dimensions.",
  },
  {
    icon: "📐",
    title: "Markowitz Optimization",
    desc: "Modern Portfolio Theory engine computes the efficient frontier via constrained mean-variance optimization using NumPy and SciPy SLSQP.",
  },
  {
    icon: "📊",
    title: "Efficient Frontier",
    desc: "Interactive Plotly.js scatter plot maps 100 frontier portfolios with real-time Sharpe-ratio color coding and annotated special points.",
  },
  {
    icon: "🥧",
    title: "Allocation Dashboard",
    desc: "Recharts pie chart and sortable fund table show your optimal allocation across 10 FSMOne funds in five asset-class sleeves (see Fund Universe below).",
  },
];

/**
 * Mirrors `data/processed/fund_metadata.json` — FSMOne display names plus
 * the ETF proxy ticker each uses for μ/σ estimation. Kept hardcoded here
 * (rather than fetched) so the landing page stays static and cheap.
 */
const FUND_UNIVERSE: {
  fund_name: string;
  proxy_ticker: string;
  asset_class: "Equity-Global" | "Equity-Regional" | "Fixed-Income" | "Multi-Asset" | "REIT";
}[] = [
  { fund_name: "AB SICAV I Global Growth Portfolio AX USD",           proxy_ticker: "URTH", asset_class: "Equity-Global" },
  { fund_name: "Blackrock Global Allocation A2 USD",                  proxy_ticker: "AOA",  asset_class: "Multi-Asset" },
  { fund_name: "Fidelity Funds - Global Healthcare Fund A-ACC-USD",   proxy_ticker: "XLV",  asset_class: "Equity-Regional" },
  { fund_name: "FTIF - Franklin US Opportunities A Acc USD",          proxy_ticker: "SPY",  asset_class: "Equity-Regional" },
  { fund_name: "Janus Henderson Horizon Global Property Equities A2 USD", proxy_ticker: "VNQ", asset_class: "REIT" },
  { fund_name: "JPMorgan Funds - America Equity A (acc) USD",         proxy_ticker: "QQQ",  asset_class: "Equity-Regional" },
  { fund_name: "Neuberger Berman Emerging Market Debt Blend A MDis USD", proxy_ticker: "EMB", asset_class: "Fixed-Income" },
  { fund_name: "PIMCO Global Bond Fund Cl E Acc USD",                 proxy_ticker: "BNDX", asset_class: "Fixed-Income" },
  { fund_name: "Schroder ISF Asian Opportunities A Acc USD",          proxy_ticker: "AAXJ", asset_class: "Equity-Regional" },
  { fund_name: "Schroder ISF Global Equity A Acc USD",                proxy_ticker: "VT",   asset_class: "Equity-Global" },
];

const ASSET_CLASS_BADGE: Record<string, string> = {
  "Equity-Global":   "bg-blue-500/20 text-blue-300",
  "Equity-Regional": "bg-violet-500/20 text-violet-300",
  "Fixed-Income":    "bg-emerald-500/20 text-emerald-300",
  "Multi-Asset":     "bg-amber-500/20 text-amber-300",
  REIT:              "bg-rose-500/20 text-rose-300",
};

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-900">
      {/* Hero */}
      <section className="relative overflow-hidden px-4 pt-20 pb-28 sm:pt-28 sm:pb-36">
        {/* Background gradient blobs */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 overflow-hidden"
        >
          <div className="absolute -top-40 -left-40 h-[600px] w-[600px] rounded-full bg-blue-600/20 blur-[120px]" />
          <div className="absolute -bottom-40 -right-40 h-[500px] w-[500px] rounded-full bg-violet-600/20 blur-[120px]" />
        </div>

        <div className="relative mx-auto max-w-5xl text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-4 py-1.5 text-sm text-blue-300">
            <span className="h-2 w-2 rounded-full bg-blue-400 animate-pulse" />
            Powered by Modern Portfolio Theory &amp; LangGraph AI
          </div>

          <h1 className="mb-6 text-5xl font-extrabold tracking-tight text-white sm:text-6xl lg:text-7xl">
            Your Personal{" "}
            <span className="bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">
              AI Robo-Adviser
            </span>
          </h1>

          <p className="mx-auto mb-10 max-w-2xl text-lg text-slate-300 leading-relaxed">
            Complete a 5-dimension psychographic risk assessment, then receive a
            mathematically optimal portfolio tailored to your risk aversion
            coefficient — built on 10 FSMOne funds, with expected returns and
            risk estimated from liquid ETF proxies that have over a decade of
            aligned price history, and reconciliation to 6 decimal places
            where applicable.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/assess"
              className="group relative inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-8 py-4 text-lg font-semibold text-white shadow-lg transition-all hover:from-blue-500 hover:to-violet-500 hover:shadow-blue-500/25 hover:shadow-xl"
            >
              Start Risk Assessment
              <svg className="h-5 w-5 transition-transform group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Link>
            <Link
              href="/frontier"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-600 bg-slate-800/60 px-8 py-4 text-lg font-semibold text-slate-200 transition-all hover:border-slate-500 hover:bg-slate-700/60"
            >
              View Efficient Frontier
            </Link>
          </div>
        </div>
      </section>

      {/* Stats bar */}
      <section className="border-y border-slate-700/60 bg-slate-800/40 px-4 py-8">
        <div className="mx-auto max-w-5xl grid grid-cols-2 gap-8 sm:grid-cols-4">
          {[
            { value: "10", label: "FSMOne funds" },
            { value: "12+ yrs", label: "Price history" },
            { value: "100", label: "Frontier Points" },
            { value: "1e-6", label: "Audit Tolerance" },
          ].map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="text-3xl font-bold text-white">{stat.value}</div>
              <div className="mt-1 text-sm text-slate-400">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="px-4 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-12 text-center text-3xl font-bold text-white">
            Platform Architecture
          </h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="rounded-2xl border border-slate-700/60 bg-slate-800/50 p-6 transition-all hover:border-blue-500/40 hover:bg-slate-800"
              >
                <div className="mb-3 text-4xl">{f.icon}</div>
                <h3 className="mb-2 font-semibold text-white">{f.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Fund Universe */}
      <section className="px-4 py-16 bg-slate-800/30">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-4 text-center text-3xl font-bold text-white">
            Fund Universe
          </h2>
          <p className="mb-8 text-center text-slate-400 max-w-3xl mx-auto leading-relaxed">
            Ten FSMOne funds span global and regional equity, US sector growth,
            Asia ex-Japan equity, emerging and international fixed income, a
            diversified multi-asset allocation, and global real estate. Expected
            returns and risk for each fund are estimated from a liquid ETF
            proxy listed in the same asset class (see Methodology below).
            Ordering matches the API{" "}
            <code className="text-slate-400">fund_codes</code> array.
          </p>

          <div className="grid gap-3 sm:grid-cols-2">
            {FUND_UNIVERSE.map((f) => (
              <div
                key={f.proxy_ticker}
                className="flex items-start justify-between gap-3 rounded-xl border border-slate-700/80 bg-slate-800/50 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-100">
                    {f.fund_name}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    proxy:{" "}
                    <code className="text-slate-400">{f.proxy_ticker}</code>
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                    ASSET_CLASS_BADGE[f.asset_class] ??
                    "bg-slate-700 text-slate-300"
                  }`}
                >
                  {f.asset_class}
                </span>
              </div>
            ))}
          </div>

          <div className="mt-6">
            <MethodologyNote />
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-4 py-20">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="mb-4 text-4xl font-bold text-white">
            Ready to optimize your portfolio?
          </h2>
          <p className="mb-8 text-lg text-slate-400">
            The AI chatbot takes ~3 minutes. Your optimal weights are computed
            in milliseconds.
          </p>
          <Link
            href="/assess"
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-8 py-4 text-lg font-semibold text-white shadow-lg transition-all hover:from-blue-500 hover:to-violet-500"
          >
            Get Started →
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-700/60 px-4 py-8 text-center text-sm text-slate-500">
        <p>Robo-Adviser Platform · Financial Modeling Final Project · 2026</p>
        <p className="mt-1">
          Mathematical audit tolerance: ≤ 1×10⁻⁶ · Risk-free rate: 3% p.a.
        </p>
      </footer>
    </div>
  );
}
