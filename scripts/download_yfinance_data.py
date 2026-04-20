"""
download_yfinance_data.py
=========================
Download monthly adjusted-close prices from Yahoo Finance and write
`/data/raw/{TICKER}.csv` files in the PRD schema:

    date,nav,fund_code

`nav` uses the ETF's **adjusted monthly close** as a NAV proxy (standard for ETFs).

Usage (from project root):

    pip install yfinance pandas
    python scripts/download_yfinance_data.py

Requires `scripts/fund_universe.py` (YAHOO_TICKERS list).
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pandas as pd

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from fund_universe import YAHOO_TICKERS

try:
    import yfinance as yf
except ImportError as e:
    raise SystemExit(
        "Missing dependency: yfinance. Install with:\n"
        "  pip install yfinance\n"
    ) from e


def _strip_tz(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if getattr(index, "tz", None) is not None:
        return index.tz_convert("UTC").tz_localize(None)
    return index


def download_monthly_series(ticker: str) -> pd.DataFrame:
    """
    Return DataFrame with columns: date (datetime64), nav (float), fund_code (str).
    """
    t = yf.Ticker(ticker)
    hist = t.history(period="max", interval="1mo", auto_adjust=True)
    if hist is None or hist.empty:
        raise ValueError(f"No Yahoo Finance data returned for {ticker!r}")

    if "Close" not in hist.columns:
        raise ValueError(f"Unexpected columns for {ticker}: {list(hist.columns)}")

    s = hist["Close"].dropna()
    if s.empty:
        raise ValueError(f"All Close prices are NaN for {ticker}")

    dates = _strip_tz(pd.DatetimeIndex(s.index))
    out = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "nav": s.values.astype("float64").round(4),
            "fund_code": ticker,
        }
    )
    return out


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    raw_dir = root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Download monthly prices from Yahoo Finance")
    print(f"Tickers ({len(YAHOO_TICKERS)}): {', '.join(YAHOO_TICKERS)}")
    print(f"Output: {raw_dir}")
    print("=" * 60)

    for ticker in YAHOO_TICKERS:
        df = download_monthly_series(ticker)
        path = raw_dir / f"{ticker}.csv"
        df.to_csv(path, index=False)
        print(f"  [OK] {ticker}: {len(df)} rows -> {path.name}  "
              f"({df['date'].iloc[0]} .. {df['date'].iloc[-1]})")

    print("\nNext step:")
    print("  python scripts/data_pipeline.py")


if __name__ == "__main__":
    main()
