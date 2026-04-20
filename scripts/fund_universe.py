"""
fund_universe.py
================
Single source of truth for the 10 investable assets used by:
  - download_yfinance_data.py  (Yahoo Finance tickers)
  - data_pipeline.py           (fund_code = ticker symbol)

`fund_code` in JSON/API is the Yahoo ticker string (e.g. "SPY").
PRD asset_class values must match Section 2 / Appendix A enums.
"""

from __future__ import annotations

# Order is fixed: covariance rows/columns and weights follow this sequence.
YAHOO_TICKERS: list[str] = [
    "URTH",
    "AOA",
    "XLV",
    "SPY",
    "VNQ",
    "QQQ",
    "EMB",
    "BNDX",
    "AAXJ",
    "VT",
]

# Alias for pipeline code readability
FUND_CODES: list[str] = YAHOO_TICKERS.copy()

# Display names and PRD asset_class labels (ETF proxies for each sleeve)
FUND_METADATA: list[dict] = [
    {
        "fund_code": "URTH",
        "fund_name": "iShares MSCI World ETF",
        "asset_class": "Equity-Global",
        "currency": "USD",
    },
    {
        "fund_code": "AOA",
        "fund_name": "iShares Core Aggressive Allocation ETF",
        "asset_class": "Multi-Asset",
        "currency": "USD",
    },
    {
        "fund_code": "XLV",
        "fund_name": "Health Care Select Sector SPDR Fund",
        "asset_class": "Equity-Regional",
        "currency": "USD",
    },
    {
        "fund_code": "SPY",
        "fund_name": "SPDR S&P 500 ETF Trust",
        "asset_class": "Equity-Global",
        "currency": "USD",
    },
    {
        "fund_code": "VNQ",
        "fund_name": "Vanguard Real Estate ETF",
        "asset_class": "REIT",
        "currency": "USD",
    },
    {
        "fund_code": "QQQ",
        "fund_name": "Invesco QQQ Trust",
        "asset_class": "Equity-Regional",
        "currency": "USD",
    },
    {
        "fund_code": "EMB",
        "fund_name": "iShares J.P. Morgan USD Emerging Markets Bond ETF",
        "asset_class": "Fixed-Income",
        "currency": "USD",
    },
    {
        "fund_code": "BNDX",
        "fund_name": "Vanguard Total International Bond ETF",
        "asset_class": "Fixed-Income",
        "currency": "USD",
    },
    {
        "fund_code": "AAXJ",
        "fund_name": "iShares MSCI All Country Asia ex Japan ETF",
        "asset_class": "Equity-Regional",
        "currency": "USD",
    },
    {
        "fund_code": "VT",
        "fund_name": "Vanguard Total World Stock ETF",
        "asset_class": "Equity-Global",
        "currency": "USD",
    },
]
