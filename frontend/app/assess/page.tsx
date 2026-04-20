"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/store/useAppStore";
import axios from "axios";
import { sendChatMessage } from "@/lib/api";
import type { ChatMessage, RiskProfileState } from "@/types";

// The 5 psychographic dimensions and their display labels
const DIMENSIONS = [
  { key: "horizon", label: "Investment Horizon" },
  { key: "drawdown", label: "Drawdown Tolerance" },
  { key: "loss_reaction", label: "Loss Reaction" },
  { key: "income_stability", label: "Income Stability" },
  { key: "experience", label: "Experience Level" },
];

const INITIAL_MESSAGE: ChatMessage = {
  role: "assistant",
  content:
    "Hello! I'm your AI risk assessment adviser. I'll ask you 5 questions to determine your investment risk profile and compute a personalised risk aversion coefficient.\n\nLet's start — **how long do you plan to keep this investment before you need the money?** (e.g. 2 years, 10 years, 20+ years)",
  timestamp: Date.now(),
};

export default function AssessPage() {
  const router = useRouter();
  const {
    sessionId,
    messages,
    currentChatState,
    completedDimensions,
    addMessage,
    setCurrentChatState,
    setRiskProfile,
    setCompletedDimensionsFromScores,
  } = useAppStore();

  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isTerminal, setIsTerminal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Seed welcome once: read fresh store (avoids stale closure + Strict Mode double-add).
  useEffect(() => {
    const { messages: storeMessages, addMessage: push } = useAppStore.getState();
    if (storeMessages.length === 0) {
      push(INITIAL_MESSAGE);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const progressPct = Math.round(
    (completedDimensions.size / DIMENSIONS.length) * 100
  );

  // Which rubric dimension we are on (from API); before first reply, treat Q1 as active.
  const pendingFromApi = currentChatState?.pending_dimension as string | undefined;
  const activeDimensionKey =
    !isTerminal && completedDimensions.size === 0 && !pendingFromApi
      ? "horizon"
      : pendingFromApi ?? null;

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading || isTerminal) return;

    const userMsg: ChatMessage = {
      role: "user",
      content: trimmed,
      timestamp: Date.now(),
    };
    addMessage(userMsg);
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const resp = await sendChatMessage({
        session_id: sessionId,
        user_message: trimmed,
        current_state: currentChatState,
      });

      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: resp.assistant_message,
        timestamp: Date.now(),
      };
      addMessage(assistantMsg);
      setCurrentChatState(resp.updated_state);

      // Progress: server nests scores under `dimension_scores`, not top-level keys.
      const ds = resp.updated_state?.dimension_scores as
        | Record<string, number>
        | undefined;
      setCompletedDimensionsFromScores(ds);

      if (resp.is_terminal && resp.risk_profile) {
        setIsTerminal(true);
        // Build a RiskProfileState from the terminal response
        const profile: RiskProfileState = {
          session_id: sessionId,
          risk_aversion_coefficient: resp.risk_profile.risk_aversion_coefficient,
          profile_label: resp.risk_profile.profile_label,
          dimension_scores: resp.risk_profile.dimension_scores as unknown as RiskProfileState["dimension_scores"],
          composite_score:
            Object.values(resp.risk_profile.dimension_scores as unknown as Record<string, number>).reduce(
              (a, b) => a + b,
              0
            ) / 5,
          conversation_turns: messages.length / 2 + 1,
          is_terminal: true,
        };
        setRiskProfile(profile);
      }
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const detail =
          typeof err.response?.data === "object" && err.response?.data !== null
            ? JSON.stringify(err.response.data)
            : err.response?.data;
        const msg =
          err.code === "ERR_NETWORK" || err.message === "Network Error"
            ? "Network Error — check that uvicorn is running on port 8000 and restart Next.js after changing next.config (API is proxied via /api/v1)."
            : err.message;
        setError(
          detail
            ? `${msg} — ${detail}`
            : msg
        );
      } else {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to reach the assessment server. Is the backend running on port 8000?"
        );
      }
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }, [
    input,
    isLoading,
    isTerminal,
    sessionId,
    currentChatState,
    messages.length,
    addMessage,
    setCurrentChatState,
    setRiskProfile,
    setCompletedDimensionsFromScores,
  ]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-4xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Risk Assessment</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            5-dimension psychographic profiling · Session:{" "}
            <code className="text-slate-500 text-xs">{sessionId.slice(0, 8)}…</code>
          </p>
        </div>
        {/* Progress badge */}
        <div className="text-right">
          <span className="text-2xl font-bold text-blue-400">{progressPct}%</span>
          <p className="text-xs text-slate-500">Complete</p>
        </div>
      </div>

      {/* Dimension progress bar */}
      <div className="mb-5 rounded-xl border border-slate-700 bg-slate-800/60 p-4">
        <div className="mb-2 flex justify-between text-xs text-slate-400">
          <span>Assessment Progress</span>
          <span>
            {completedDimensions.size} / {DIMENSIONS.length} dimensions
          </span>
        </div>
        {/* Segmented bar */}
        <div className="flex gap-1.5">
          {DIMENSIONS.map((dim) => {
            const done = completedDimensions.has(dim.key);
            const active =
              !done &&
              activeDimensionKey === dim.key;
            return (
            <div key={dim.key} className="flex-1">
              <div
                className={`h-2 rounded-full transition-all duration-500 ${
                  done
                    ? "bg-gradient-to-r from-blue-500 to-violet-500"
                    : active
                      ? "bg-amber-500/90 ring-1 ring-amber-400/50"
                      : "bg-slate-700"
                }`}
              />
              <p
                className={`mt-1 text-center text-[10px] leading-none ${
                  done
                    ? "text-blue-400"
                    : active
                      ? "text-amber-400"
                      : "text-slate-600"
                }`}
              >
                {dim.label.split(" ")[0]}
              </p>
            </div>
            );
          })}
        </div>
      </div>

      {/* Chat thread */}
      <div className="flex-1 overflow-y-auto rounded-2xl border border-slate-700 bg-slate-800/40 p-4 space-y-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="mr-2 mt-1 flex-shrink-0 h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold">
                AI
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "rounded-tr-sm bg-blue-600 text-white"
                  : "rounded-tl-sm bg-slate-700 text-slate-100"
              }`}
            >
              {/* Render newlines and **bold** */}
              {msg.content.split("\n").map((line, li) => {
                const parts = line.split(/\*\*(.*?)\*\*/g);
                return (
                  <p key={li} className={li > 0 ? "mt-1" : ""}>
                    {parts.map((part, pi) =>
                      pi % 2 === 1 ? (
                        <strong key={pi}>{part}</strong>
                      ) : (
                        <span key={pi}>{part}</span>
                      )
                    )}
                  </p>
                );
              })}
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="mr-2 mt-1 flex-shrink-0 h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold">
              AI
            </div>
            <div className="rounded-2xl rounded-tl-sm bg-slate-700 px-4 py-3">
              <div className="flex gap-1 items-center">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="h-2 w-2 rounded-full bg-slate-400 animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Error banner */}
      {error && (
        <div className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          ⚠ {error}
        </div>
      )}

      {/* Input area */}
      <div className="mt-4 flex gap-3">
        {isTerminal ? (
          <button
            onClick={() => router.push("/profile")}
            className="flex-1 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-6 py-3 font-semibold text-white transition-all hover:from-blue-500 hover:to-violet-500 hover:shadow-lg hover:shadow-blue-500/20"
          >
            View My Risk Profile →
          </button>
        ) : (
          <>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              placeholder="Type your answer…"
              className="flex-1 rounded-xl border border-slate-600 bg-slate-800 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 outline-none transition-colors focus:border-blue-500 disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="rounded-xl bg-blue-600 px-5 py-3 font-semibold text-white transition-all hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <span className="animate-spin inline-block">⟳</span>
              ) : (
                "Send"
              )}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
