/**
 * Shared frontend constants.
 *
 * Values that must stay in sync with the backend (e.g. risk-free rate) are
 * centralised here so components don't each hardcode their own. At runtime,
 * prefer `response.metadata.risk_free_rate` from the API when available —
 * these are only fallbacks for pre-fetch renders.
 */

/** Annualized USD short-rate. Mirrors backend/config.py:RISK_FREE_RATE. */
export const RISK_FREE_RATE = 0.03;
