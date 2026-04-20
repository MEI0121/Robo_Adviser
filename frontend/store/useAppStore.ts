// ============================================================
// Zustand global store — persists RiskProfileState and
// OptimizationResponse across all pages for the session.
// Never re-fetches unless the session changes.
// ============================================================

import { create } from "zustand";
import type {
  RiskProfileState,
  OptimizationResponse,
  ChatMessage,
  Fund,
} from "@/types";

interface AppState {
  // ---- Session ----
  sessionId: string;

  // ---- Chat / Risk Assessment ----
  messages: ChatMessage[];
  currentChatState: Record<string, unknown>;
  riskProfile: RiskProfileState | null;
  completedDimensions: Set<string>;

  // ---- Optimization Results ----
  optimizationResult: OptimizationResponse | null;

  // ---- Fund Universe ----
  funds: Fund[];
  covarianceMatrix: number[][];

  // ---- Actions ----
  setSessionId: (id: string) => void;
  addMessage: (msg: ChatMessage) => void;
  setCurrentChatState: (state: Record<string, unknown>) => void;
  setRiskProfile: (profile: RiskProfileState) => void;
  markDimensionComplete: (dim: string) => void;
  /** Replace progress from API `dimension_scores` (1–5 = completed for that dimension). */
  setCompletedDimensionsFromScores: (scores: Record<string, number> | undefined | null) => void;
  setOptimizationResult: (result: OptimizationResponse) => void;
  setFunds: (funds: Fund[], cov: number[][]) => void;
  resetSession: () => void;
}

const DIMENSION_KEYS = [
  "horizon",
  "drawdown",
  "loss_reaction",
  "income_stability",
  "experience",
] as const;

const generateSessionId = (): string =>
  typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;

export const useAppStore = create<AppState>((set) => ({
  sessionId: generateSessionId(),
  messages: [],
  currentChatState: {},
  riskProfile: null,
  completedDimensions: new Set(),
  optimizationResult: null,
  funds: [],
  covarianceMatrix: [],

  setSessionId: (id) => set({ sessionId: id }),

  // Ignore duplicate role+content (e.g. React Strict Mode double-invoked welcome effect).
  addMessage: (msg) =>
    set((state) => {
      const duplicate = state.messages.some(
        (m) => m.role === msg.role && m.content === msg.content
      );
      if (duplicate) return state;
      return { messages: [...state.messages, msg] };
    }),

  setCurrentChatState: (chatState) => set({ currentChatState: chatState }),

  // New terminal profile ⇒ drop cached weights (different A / session than prior run).
  setRiskProfile: (profile) =>
    set({ riskProfile: profile, optimizationResult: null }),

  markDimensionComplete: (dim) =>
    set((state) => {
      const next = new Set(state.completedDimensions);
      next.add(dim);
      return { completedDimensions: next };
    }),

  setCompletedDimensionsFromScores: (scores) =>
    set(() => {
      const next = new Set<string>();
      if (!scores) return { completedDimensions: next };
      for (const k of DIMENSION_KEYS) {
        const v = scores[k];
        if (typeof v === "number" && v >= 1 && v <= 5) next.add(k);
      }
      return { completedDimensions: next };
    }),

  setOptimizationResult: (result) => set({ optimizationResult: result }),

  setFunds: (funds, cov) =>
    set({ funds, covarianceMatrix: cov }),

  resetSession: () =>
    set({
      sessionId: generateSessionId(),
      messages: [],
      currentChatState: {},
      riskProfile: null,
      completedDimensions: new Set(),
      optimizationResult: null,
    }),
}));
