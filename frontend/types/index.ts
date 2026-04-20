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

export interface OptimizationResponse {
  status: "success" | "error";
  optimal_portfolio: PortfolioStats;
  gmvp: PortfolioStats;
  efficient_frontier: FrontierPoint[];
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
  fund_code: string;
  fund_name: string;
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
