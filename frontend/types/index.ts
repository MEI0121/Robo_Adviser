// ============================================================
// Shared TypeScript type definitions for the Robo-Adviser Platform
// Mirrors the API contracts defined in the PRD (Section 2)
// ============================================================

// ---- Risk Assessment (POST /api/v1/chat/assess) ----

export type ProfileLabel =
  | "Conservative"
  | "Moderately Conservative"
  | "Moderate"
  | "Moderately Aggressive"
  | "Aggressive";

export interface DimensionScores {
  horizon: number;
  drawdown: number;
  loss_reaction: number;
  income_stability: number;
  experience: number;
}

export interface RiskProfile {
  risk_aversion_coefficient: number; // A ∈ [0.5, 10.0]
  profile_label: ProfileLabel;
  dimension_scores: DimensionScores;
}

export interface RiskProfileState {
  session_id: string;
  risk_aversion_coefficient: number;
  profile_label: ProfileLabel;
  dimension_scores: DimensionScores;
  composite_score: number;
  conversation_turns: number;
  is_terminal: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export interface ChatAssessRequest {
  session_id: string;
  user_message: string;
  current_state: Record<string, unknown>;
}

export interface ChatAssessResponse {
  session_id: string;
  assistant_message: string;
  updated_state: Record<string, unknown>;
  is_terminal: boolean;
  risk_profile?: RiskProfile;
}

// ---- Optimization (POST /api/v1/optimize) ----

export interface OptimizeRequest {
  risk_aversion_coefficient: number;
  constraints: {
    allow_short_selling: boolean;
    max_single_weight: number;
  };
}

export interface PortfolioStats {
  weights: number[]; // length 10
  fund_codes: string[];
  expected_annual_return: number; // E(r_p) = w^T * mu
  annual_volatility: number; // σ_p = sqrt(w^T Σ w)
  sharpe_ratio: number; // (E(r_p) - r_f) / σ_p
  utility_score?: number; // U = E(r_p) - 0.5 * A * σ_p^2
}

export interface FrontierPoint {
  expected_return: number;
  volatility: number;
  sharpe_ratio: number;
  weights: number[];
}

export interface OptimizationMetadata {
  risk_aversion_coefficient: number;
  risk_free_rate: number;
  num_assets: number;
  data_start_date: string;
  data_end_date: string;
  optimization_method: string;
  computation_time_ms: number;
}

export interface TangencyStats extends PortfolioStats {
  /** "primary" | "fallback" from compute_tangency_portfolio; null for non-tangency portfolios. */
  solver_path?: string | null;
}

export interface OptimizationResponse {
  status: "success" | "error";
  optimal_portfolio: PortfolioStats;
  gmvp: PortfolioStats;
  efficient_frontier: FrontierPoint[];
  /** GMVP computed with w ∈ [-1, 2] (PRD Part 1 relaxed constraints). */
  gmvp_short_allowed: PortfolioStats;
  /** Max-Sharpe portfolio under the request's max_weight, long-only. Anchor for CML. */
  tangency: TangencyStats;
  /** Max-Sharpe portfolio with w ∈ [-1, 2]. */
  tangency_short_allowed: TangencyStats;
  /** Parallel 100-point frontier with w ∈ [-1, 2]. */
  efficient_frontier_short_allowed: FrontierPoint[];
  /** Naive 1/n benchmark. Computed server-side; replaces the old frontend averaging hack. */
  equal_weight: PortfolioStats;
  metadata: OptimizationMetadata;
}

// ---- Fund Universe (GET /api/v1/funds) ----

export type AssetClass =
  | "Equity-Global"
  | "Equity-Regional"
  | "Fixed-Income"
  | "Multi-Asset"
  | "Commodity"
  | "REIT";

export interface Fund {
  /** FSMOne fund identifier — the display-layer code users transact in. */
  fund_code: string;
  /** FSMOne fund name shown to users on the landing page, portfolio table, and chart hovers. */
  fund_name: string;
  /** ETF ticker used to estimate μ and σ for this fund (Yahoo Finance proxy). */
  proxy_ticker: string;
  /** Upstream price-series provider for the proxy ticker. */
  proxy_provider: string;
  asset_class: AssetClass;
  currency: string;
  annualized_return: number;
  annualized_volatility: number;
  sharpe_ratio: number;
  nav_history_years: number;
}

export interface FundsResponse {
  funds: Fund[];
  covariance_matrix: number[][];
}

// ---- API Error ----

export interface ApiError {
  status: "error";
  error_code: string;
  message: string;
  details?: Record<string, unknown>;
}
