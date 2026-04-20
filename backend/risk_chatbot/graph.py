"""
Psychographic risk assessment — **multi-turn HTTP stepper**.

The earlier design compiled a LangGraph `StateGraph` and called `invoke()`, which
**runs the entire graph until END in one shot**. Each collection node would
then incorrectly re-use the *same* latest user message to score every remaining
dimension in a single request — producing instant completion after one answer.

The public API is unchanged: `step_graph()` advances **exactly one user turn**
per HTTP request:

  * If there is no user message → emit the next elicitation question (Phase A).
  * If there is a user message → score **only** the active `pending_dimension`
    (or infer it from the last assistant `__dim:…__` tag), then either ask for a
    follow-up, emit the **next** dimension's question, or run terminal classification.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any

# If this module is imported without going through main.py, still load .env.
try:
    from dotenv import load_dotenv

    _backend = Path(__file__).resolve().parent.parent
    _root = _backend.parent
    load_dotenv(_root / ".env")
    load_dotenv(_backend / ".env")
except ImportError:
    pass

from langchain_core.messages import HumanMessage, SystemMessage

from .scoring import (
    DIMENSION_KEYS,
    SCORING_RUBRIC,
    all_dimensions_scored,
    score_to_risk_profile,
)
from .state import AssistantMessage, DimensionScore, RiskProfileState

# ---------------------------------------------------------------------------
# LLM factory  (supports both OpenAI and Ollama backends)
# ---------------------------------------------------------------------------


def _build_llm() -> Any:
    """
    Construct a LangChain chat model instance.

    Reads CHATBOT_BACKEND, CHATBOT_MODEL, OPENAI_API_KEY, OLLAMA_BASE_URL from
    the environment.  Falls back to OpenAI gpt-4o with temperature=0.
    """
    backend = os.getenv("CHATBOT_BACKEND", "openai").lower()
    if backend == "ollama":
        from langchain_ollama import ChatOllama  # type: ignore

        model_name = os.getenv("CHATBOT_MODEL", "llama3")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ChatOllama(model=model_name, base_url=base_url, temperature=0)

    from langchain_openai import ChatOpenAI  # type: ignore

    model_name = os.getenv("CHATBOT_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o")
    return ChatOpenAI(model=model_name, temperature=0)


# ---------------------------------------------------------------------------
# System prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PREAMBLE = (
    "You are a professional robo-adviser conducting a psychographic risk assessment. "
    "Your goal is to determine the investor's risk tolerance across five dimensions. "
    "Be conversational, empathetic, and concise. Do NOT give financial advice or "
    "mention specific investments. Ask exactly one focused question per turn."
)

_ELICITATION_PROMPTS: dict[str, str] = {
    "horizon": (
        "Ask the user how many years they plan to keep their investments before "
        "they need to access the funds. Focus on their specific investment goal "
        "(e.g. retirement, house purchase)."
    ),
    "drawdown": (
        "Ask the user the maximum percentage decline in their portfolio value they "
        "would be comfortable with before they would want to withdraw or restructure "
        "their investments."
    ),
    "loss_reaction": (
        "Present a scenario: their portfolio has dropped 20% in value over three months. "
        "Ask how they would emotionally and practically respond. Give concrete options "
        "as a loose guide (sell, hold, buy more) but let them answer freely."
    ),
    "income_stability": (
        "Ask about the stability and reliability of their current income, and whether "
        "they have an emergency fund. Probe whether they might need to liquidate "
        "investments within the next 12 months due to life circumstances."
    ),
    "experience": (
        "Ask about their prior experience with investing — whether they have traded "
        "equities, funds, bonds, or more complex instruments before, and for how long."
    ),
}

_SCORING_INSTRUCTIONS: dict[str, str] = {
    k: (
        f"The user has responded to a question about their **{k.replace('_', ' ')}**. "
        f"Score their answer on a 1–5 scale using this rubric:\n"
        + "\n".join(f"  {s}: {desc}" for s, desc in SCORING_RUBRIC[k].items())
        + "\n\nIf the answer is ambiguous or evasive, set follow_up_needed=true "
        "and provide a clarifying follow-up question in the 'reasoning' field."
    )
    for k in DIMENSION_KEYS
}

_DIM_SENTINEL_RE = re.compile(r"^__dim:(?P<dim>[\w]+)__\s*")


def _strip_sentinel(content: str) -> str:
    return _DIM_SENTINEL_RE.sub("", content or "").strip()


def _tagged_assistant(dimension: str, body: str) -> dict[str, str]:
    return {"role": "assistant", "content": f"__dim:{dimension}__ {body.strip()}"}


# ---------------------------------------------------------------------------
# Elicitation & scoring (single-dimension, one HTTP step)
# ---------------------------------------------------------------------------


def _run_elicitation(dimension: str) -> str:
    """Return the raw assistant question text (no sentinel)."""
    llm = _build_llm()
    prompt_llm = llm.with_structured_output(AssistantMessage)
    elicit_result: AssistantMessage = prompt_llm.invoke(
        [
            SystemMessage(content=_SYSTEM_PREAMBLE),
            SystemMessage(content=_ELICITATION_PROMPTS[dimension]),
        ]
    )
    return elicit_result.message


def _run_scoring(dimension: str, user_text: str) -> DimensionScore:
    llm = _build_llm()
    score_llm = llm.with_structured_output(DimensionScore)
    return score_llm.invoke(
        [
            SystemMessage(content=_SYSTEM_PREAMBLE),
            SystemMessage(content=_SCORING_INSTRUCTIONS[dimension]),
            HumanMessage(content=user_text),
        ]
    )


def _infer_pending_dimension_from_messages(messages: list[dict]) -> str | None:
    """
    Return the dimension the user is answering: the `__dim:X__` tag on the assistant
    message immediately before the **last** user message.
    """
    if not messages:
        return None
    last_user_i: int | None = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_i = i
            break
    if last_user_i is None:
        return None
    for j in range(last_user_i - 1, -1, -1):
        if messages[j].get("role") != "assistant":
            continue
        m = _DIM_SENTINEL_RE.match(messages[j].get("content") or "")
        if not m:
            continue
        dim = m.group("dim")
        if dim == "terminal":
            return None
        if dim in DIMENSION_KEYS:
            return dim
    return None


def _first_unanswered_dimension(scores: dict[str, Any]) -> str | None:
    for k in DIMENSION_KEYS:
        s = scores.get(k)
        if s not in range(1, 6):
            return k
    return None


def _score_and_classify(state: dict[str, Any]) -> dict:
    """
    Terminal node: aggregate the five dimension scores into A and profile label.
    """
    scores = dict(state.get("dimension_scores") or {})
    session_id = state.get("session_id") or str(uuid.uuid4())
    turns = state.get("conversation_turns", 0)

    profile_dict = score_to_risk_profile(
        dimension_scores={k: scores[k] for k in DIMENSION_KEYS},
        session_id=session_id,
        conversation_turns=turns,
    )
    validated_profile = RiskProfileState(**profile_dict)

    a = validated_profile.risk_aversion_coefficient
    label = validated_profile.profile_label

    summary_message = (
        f"__dim:terminal__ Thank you for completing the assessment. "
        f"Based on your answers, your risk profile is **{label}** "
        f"(Risk Aversion Score: {a:.2f}). "
        "This profile will now guide your personalised portfolio optimisation."
    )

    return {
        "messages": [{"role": "assistant", "content": summary_message}],
        "is_terminal": True,
        "_terminal_profile": validated_profile.model_dump(),
    }


# ---------------------------------------------------------------------------
# Public API: one HTTP request = one step (never invoke a full graph to END)
# ---------------------------------------------------------------------------


def step_graph(
    session_id: str,
    user_message: str | None,
    current_state: dict | None,
) -> dict:
    """
    Advance the assessment by **one** logical step (one client HTTP round-trip).

    Parameters mirror the previous implementation; ``updated_state`` is again an
    opaque dict the client must post back as ``current_state``.
    """
    if current_state is None:
        state: dict = {
            "session_id": session_id,
            "messages": [],
            "dimension_scores": {},
            "conversation_turns": 0,
            "current_node": "collect_horizon",
            "is_terminal": False,
            "pending_dimension": None,
        }
    else:
        state = dict(current_state)
        if "pending_dimension" not in state:
            state["pending_dimension"] = None
        if "messages" not in state:
            state["messages"] = []
        else:
            state["messages"] = list(state["messages"])
        if "dimension_scores" not in state:
            state["dimension_scores"] = {}
        state.setdefault("conversation_turns", 0)
        state.setdefault("is_terminal", False)

    if state.get("is_terminal"):
        # Idempotent: re-return the last assistant message
        msgs = state.get("messages", [])
        last_a = next(
            (m["content"] for m in reversed(msgs) if m.get("role") == "assistant"),
            "Assessment already completed.",
        )
        clean = _strip_sentinel(last_a)
        rp = state.get("_terminal_profile")
        return {
            "assistant_message": clean,
            "updated_state": state,
            "is_terminal": True,
            "risk_profile": rp,
        }

    scores: dict[str, int] = dict(state.get("dimension_scores") or {})

    # ----- Branch: user sent a message -> score at most ONE dimension this turn -----
    if user_message is not None and str(user_message).strip() != "":
        user_message = str(user_message).strip()
        state["messages"].append({"role": "user", "content": user_message})
        state["conversation_turns"] = int(state.get("conversation_turns", 0)) + 1

        pending = state.get("pending_dimension")
        if pending not in DIMENSION_KEYS:
            pending = _infer_pending_dimension_from_messages(state["messages"])
        if pending is None:
            # First reply in a session where the UI showed a canned welcome (no
            # `__dim:horizon__` in persisted state) — treat as **horizon**.
            pending = "horizon"

        ds = _run_scoring(pending, user_message)

        if ds.follow_up_needed:
            follow_body = ds.reasoning.strip()
            state["messages"].append(_tagged_assistant(pending, follow_body))
            state["pending_dimension"] = pending
            state["current_node"] = f"collect_{pending}"
            last_assistant = state["messages"][-1]["content"]
            return {
                "assistant_message": _strip_sentinel(last_assistant),
                "updated_state": state,
                "is_terminal": False,
                "risk_profile": None,
            }

        scores[pending] = ds.score
        state["dimension_scores"] = scores
        state["pending_dimension"] = None

        if all_dimensions_scored(scores):
            terminal_update = _score_and_classify(state)
            state["messages"].extend(terminal_update["messages"])  # type: ignore[assignment]
            state["is_terminal"] = True
            state["_terminal_profile"] = terminal_update["_terminal_profile"]
            state["current_node"] = "score_and_classify"
            last_assistant = state["messages"][-1]["content"]
            return {
                "assistant_message": _strip_sentinel(last_assistant),
                "updated_state": state,
                "is_terminal": True,
                "risk_profile": state.get("_terminal_profile"),
            }

        nxt = _first_unanswered_dimension(scores)
        assert nxt is not None
        q = _run_elicitation(nxt)
        state["messages"].append(_tagged_assistant(nxt, q))
        state["pending_dimension"] = nxt
        state["current_node"] = f"collect_{nxt}"
        last_assistant = state["messages"][-1]["content"]
        return {
            "assistant_message": _strip_sentinel(last_assistant),
            "updated_state": state,
            "is_terminal": False,
            "risk_profile": None,
        }

    # ----- No user message: open with the first unanswered elicitation -----
    nxt = _first_unanswered_dimension(scores)
    if nxt is None and not scores:
        nxt = "horizon"
    if nxt is None:
        # Already complete but not terminal? Run classifier once.
        terminal_update = _score_and_classify(state)
        state["messages"].extend(terminal_update["messages"])  # type: ignore[assignment]
        state["is_terminal"] = True
        state["_terminal_profile"] = terminal_update["_terminal_profile"]
        last_assistant = state["messages"][-1]["content"]
        return {
            "assistant_message": _strip_sentinel(last_assistant),
            "updated_state": state,
            "is_terminal": True,
            "risk_profile": state.get("_terminal_profile"),
        }

    q = _run_elicitation(nxt)
    state["messages"].append(_tagged_assistant(nxt, q))
    state["pending_dimension"] = nxt
    state["current_node"] = f"collect_{nxt}"
    last_assistant = state["messages"][-1]["content"]
    return {
        "assistant_message": _strip_sentinel(last_assistant),
        "updated_state": state,
        "is_terminal": False,
        "risk_profile": None,
    }


def sanitise_langgraph_state(state: dict) -> dict:
    """
    Convert a raw session dict into a JSON-safe plain dict for API responses.

    Strips internal keys prefixed with ``_`` (e.g. ``_terminal_profile``), which
    are surfaced separately as ``risk_profile`` on the HTTP response.
    """
    sanitised: dict[str, Any] = {}
    for key, value in state.items():
        if key.startswith("_"):
            continue
        if hasattr(value, "model_dump"):
            sanitised[key] = value.model_dump()
        elif isinstance(value, list):
            sanitised[key] = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in value
            ]
        else:
            sanitised[key] = value
    return sanitised


