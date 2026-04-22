"""
Tests for the FSMOne display-layer remap.

Pins the shape of the split between:
  - Display layer: fund_code, fund_name (FSMOne identifiers).
  - Estimation layer: proxy_ticker (ETF price-series source for μ and Σ).

What this test guards against
-----------------------------
  1. /api/v1/funds forgetting to expose ``proxy_ticker`` / ``proxy_provider``.
  2. fund_metadata.json drifting out of order against mu_vector.json's
     internal data-row ordering. If someone reshuffles the metadata but
     leaves mu_vector unchanged (or vice versa), the weight vector that
     the API returns for each FSMOne fund will silently point at the
     wrong asset's μ/σ. This test catches that class of bug at CI time.
  3. The proxy-ticker set matching the raw data vocabulary exactly (the
     10 ETF tickers loaded from mu_vector.json).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parent.parent
_PROCESSED = _ROOT / "data" / "processed"
_DATA_PRESENT = (_PROCESSED / "mu_vector.json").exists()

pytestmark = pytest.mark.skipif(
    not _DATA_PRESENT, reason="Market data required for FSMOne remap tests"
)


_REQUIRED_NEW_FIELDS = {"proxy_ticker", "proxy_provider"}


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_fund_metadata() -> list[dict]:
    with open(_PROCESSED / "fund_metadata.json", encoding="utf-8") as fh:
        return json.load(fh)


def _load_mu_vector_payload() -> dict:
    with open(_PROCESSED / "mu_vector.json", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# 1. /api/v1/funds exposes proxy_ticker and proxy_provider on every fund
# ---------------------------------------------------------------------------


class TestFundsEndpointProxyFields:
    async def test_all_funds_carry_proxy_ticker_and_provider(self, client):
        response = await client.get("/api/v1/funds")
        assert response.status_code == 200, response.text
        body = response.json()

        for i, fund in enumerate(body["funds"]):
            missing = _REQUIRED_NEW_FIELDS - set(fund.keys())
            assert not missing, (
                f"/api/v1/funds fund[{i}] missing required proxy fields: "
                f"{missing}. Full entry: {fund}"
            )
            assert isinstance(fund["proxy_ticker"], str) and fund["proxy_ticker"], (
                f"fund[{i}] proxy_ticker is empty"
            )
            assert isinstance(fund["proxy_provider"], str) and fund["proxy_provider"], (
                f"fund[{i}] proxy_provider is empty"
            )

    async def test_fund_code_is_fsmone_not_etf_ticker(self, client):
        """fund_code should have flipped to FSMOne-style IDs, not the ETF tickers."""
        response = await client.get("/api/v1/funds")
        etfs = {"URTH", "AOA", "XLV", "SPY", "VNQ", "QQQ", "EMB", "BNDX", "AAXJ", "VT"}
        for fund in response.json()["funds"]:
            assert fund["fund_code"] not in etfs, (
                f"fund_code still looks like an ETF ticker: {fund['fund_code']}. "
                "The FSMOne remap expects FSMOne identifiers in fund_code and "
                "the ETF ticker in proxy_ticker."
            )

    async def test_fund_name_is_fsmone_display_name(self, client):
        """fund_name should be the FSMOne display name (no 'iShares'/'SPDR'/'Vanguard' ETF names)."""
        response = await client.get("/api/v1/funds")
        for fund in response.json()["funds"]:
            assert "ETF" not in fund["fund_name"], (
                f"fund_name still looks like an ETF product name: "
                f"{fund['fund_name']!r}"
            )


# ---------------------------------------------------------------------------
# 2. fund_metadata.proxy_ticker ordering matches mu_vector fund_codes
# ---------------------------------------------------------------------------


class TestProxyOrderingMatchesDataRows:
    def test_proxy_tickers_equal_mu_vector_fund_codes_in_order(self):
        """
        mu_vector.json's `fund_codes` array labels the data rows of the
        μ vector (and therefore, by alignment, of the covariance matrix).
        fund_metadata.json's `proxy_ticker` for entry i must equal
        fund_codes[i] exactly, or the API's returned weight vector
        points a given FSMOne fund at the wrong asset's stats.
        """
        metadata = _load_fund_metadata()
        mu_payload = _load_mu_vector_payload()

        expected = mu_payload["fund_codes"]
        actual = [entry["proxy_ticker"] for entry in metadata]

        assert actual == expected, (
            "fund_metadata.proxy_ticker ordering does not match "
            "mu_vector.fund_codes ordering.\n"
            f"  mu_vector:     {expected}\n"
            f"  fund_metadata: {actual}\n"
            "Re-order fund_metadata.json to match mu_vector.json's row order."
        )

    def test_ten_entries_in_metadata(self):
        assert len(_load_fund_metadata()) == 10

    def test_proxy_provider_is_yahoo_finance(self):
        """
        Current pipeline sources all price series from Yahoo Finance via
        ``scripts/download_yfinance_data.py``. Pin that in the metadata
        so a future provider swap has to update this test alongside the
        downloader.
        """
        for entry in _load_fund_metadata():
            assert entry["proxy_provider"] == "Yahoo Finance", (
                f"Unexpected proxy_provider in {entry['fund_code']!r}: "
                f"{entry['proxy_provider']!r}"
            )


# ---------------------------------------------------------------------------
# 3. Cross-check: /api/v1/funds and /api/v1/optimize return the same fund_code set
# ---------------------------------------------------------------------------


class TestFundCodeConsistencyAcrossEndpoints:
    async def test_funds_and_optimize_return_same_fsmone_codes(self, client):
        funds_resp = await client.get("/api/v1/funds")
        opt_resp = await client.post(
            "/api/v1/optimize",
            json={"risk_aversion_coefficient": 3.5},
        )
        assert funds_resp.status_code == 200
        assert opt_resp.status_code == 200

        funds_codes = [f["fund_code"] for f in funds_resp.json()["funds"]]
        opt_codes = opt_resp.json()["optimal_portfolio"]["fund_codes"]
        assert funds_codes == opt_codes, (
            f"fund_code order mismatch between endpoints.\n"
            f"  /funds:    {funds_codes}\n"
            f"  /optimize: {opt_codes}\n"
            "Both should be the FSMOne identifiers, in data-row order."
        )

    async def test_optimize_fund_codes_are_short_identifiers(self, client):
        """
        Post-remap (real FSMOne codes via the FSMOne lookup PR), codes may
        be short 5–12 char alphanumeric strings (e.g. ACM177, BGF002,
        HEHGPE) or the legacy ``FSMONE_*`` synthetic placeholder for any
        fund whose FSMOne share class could not be confirmed. Both are
        acceptable; what matters is that codes are neither ETF tickers
        nor empty. The ETF-ticker check is enforced separately by
        ``test_fund_code_is_fsmone_not_etf_ticker``.
        """
        opt_resp = await client.post(
            "/api/v1/optimize",
            json={"risk_aversion_coefficient": 3.5},
        )
        for code in opt_resp.json()["optimal_portfolio"]["fund_codes"]:
            assert isinstance(code, str) and len(code) >= 3, (
                f"optimize response returned a malformed fund_code: {code!r}"
            )
