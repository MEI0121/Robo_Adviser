"use client";

import { useState } from "react";

/**
 * Non-blocking, expandable methodology note for fund-listing pages.
 * Placed on the landing page Fund Universe section and on /portfolio.
 *
 * The note explains that FSMOne fund names (the display layer) are the
 * transactable universe, while μ and σ are estimated from ETF proxies
 * priced via Yahoo Finance. This split exists because FSMOne does not
 * expose 10-year daily historical data via API.
 *
 * Design constraints: must not interrupt the user flow — rendered as a
 * collapsed info strip with a text "?" toggle. Not a modal, not an
 * interstitial.
 */
export function MethodologyNote({
  className = "",
}: {
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div
      className={`rounded-xl border border-slate-700/80 bg-slate-800/40 text-sm ${className}`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-slate-300 hover:text-white"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2">
          <span
            aria-hidden
            className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-500 text-xs font-semibold text-slate-400"
          >
            ?
          </span>
          Methodology: FSMOne funds with ETF-proxy estimation
        </span>
        <span
          aria-hidden
          className={`text-slate-500 transition-transform ${
            open ? "rotate-180" : ""
          }`}
        >
          ▾
        </span>
      </button>
      {open && (
        <div className="border-t border-slate-700/60 px-4 py-3 text-slate-400 leading-relaxed">
          Expected returns and risk for each FSMOne fund are estimated from a
          liquid ETF proxy listed in the same asset class (shown as{" "}
          <code className="rounded bg-slate-900 px-1 py-0.5 text-slate-300">
            proxy: TICKER
          </code>
          ). This approach is used because FSMOne does not expose 10-year
          daily historical data; the ETF-proxy methodology enables a uniform
          data window across the universe. Recommended allocations should be
          executed in the FSMOne funds themselves.
        </div>
      )}
    </div>
  );
}
