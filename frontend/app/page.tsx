import Link from "next/link";

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
    desc: "Recharts pie chart and sortable fund table show your optimal allocation across 10 liquid US-listed ETFs in five asset-class sleeves (see Fund Universe below).",
  },
];

/** Mirrors `data/processed/fund_metadata.json` — ticker-level ETFs used for μ, Σ. */
const FUND_CLASSES = [
  { label: "Equity-Global", color: "bg-blue-500", count: 3 },
  { label: "Equity-Regional", color: "bg-violet-500", count: 3 },
  { label: "Fixed-Income", color: "bg-emerald-500", count: 2 },
  { label: "Multi-Asset", color: "bg-amber-500", count: 1 },
  { label: "REIT", color: "bg-rose-500", count: 1 },
];

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
            coefficient — built on 10 US-listed ETFs with over a decade of
            aligned price history (see data pipeline) and reconciliation to 6
            decimal places where applicable.
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
            { value: "10", label: "US-listed ETFs" },
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
          <p className="mb-4 text-center text-slate-400 max-w-3xl mx-auto leading-relaxed">
            Ten liquid benchmark ETFs drive the covariance matrix and expected
            returns: global and total-world equity (URTH, SPY, VT), US sector /
            growth / Asia ex-Japan equity (XLV, QQQ, AAXJ), core bonds including
            EM and international (EMB, BNDX), a diversified allocation fund (AOA),
            and US REITs (VNQ). Labels follow the PRD asset-class taxonomy
            (Equity-Global, Equity-Regional, Fixed-Income, Multi-Asset, REIT).
          </p>
          <p className="mb-10 text-center text-sm text-slate-500">
            Five sleeves · USD · same ordering as <code className="text-slate-400">fund_metadata.json</code> / API{" "}
            <code className="text-slate-400">fund_codes</code>
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            {FUND_CLASSES.map((fc) => (
              <div
                key={fc.label}
                className="flex items-center gap-2 rounded-full border border-slate-600 bg-slate-800 px-4 py-2 text-sm text-slate-200"
              >
                <span className={`h-2.5 w-2.5 rounded-full ${fc.color}`} />
                {fc.label}
                <span className="ml-1 rounded-full bg-slate-700 px-1.5 py-0.5 text-xs text-slate-400">
                  ×{fc.count}
                </span>
              </div>
            ))}
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
