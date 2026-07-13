"""
Supervisor Agent — Orchestrates the 5-agent Career Copilot pipeline.

Graph structure:
  START
    → profile_agent
    → discovery_agent
    → resume_agent
    → apply_agent      (skipped if error or if pipeline is in dry-run mode)
    → notification_agent
  END

Error handling:
  Each transition checks `state["error"]`. A non-None value routes
  directly to END, skipping all downstream agents.
"""

import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph")

import logging

from langgraph.graph import END, START, StateGraph

from APP.agents.apply_agent import apply_jobs_node
from APP.agents.discovery_agent import find_opportunities_node
from APP.agents.notification_agent import notify_user_node
from APP.agents.profile_agent import extract_profile_node
from APP.agents.resume_agent import tailor_application_node
from APP.agents.state import AgentState

logger = logging.getLogger(__name__)


def _route_after_node(next_node: str):
    """
    Returns a conditional routing function that:
      - Routes to END if `state["error"]` is set
      - Otherwise routes to `next_node`
    """

    def _router(state: AgentState) -> str:
        if state.get("error"):
            logger.warning(
                "Pipeline halted at step '%s' due to error: %s",
                state.get("current_step"),
                state["error"],
            )
            return END
        return next_node

    return _router


def build_supervisor_graph():
    """
    Build and compile the 5-agent LangGraph pipeline.

    Returns the compiled graph ready to be invoked with an AgentState.
    """
    workflow = StateGraph(AgentState)

    # ── Register agent nodes ───────────────────────────────────────────────
    workflow.add_node("profile_agent", extract_profile_node)
    workflow.add_node("discovery_agent", find_opportunities_node)
    workflow.add_node("resume_agent", tailor_application_node)
    workflow.add_node("apply_agent", apply_jobs_node)
    workflow.add_node("notification_agent", notify_user_node)

    # ── Wire edges ─────────────────────────────────────────────────────────
    workflow.add_edge(START, "profile_agent")

    workflow.add_conditional_edges(
        "profile_agent",
        _route_after_node("discovery_agent"),
    )
    workflow.add_conditional_edges(
        "discovery_agent",
        _route_after_node("resume_agent"),
    )
    workflow.add_conditional_edges(
        "resume_agent",
        _route_after_node("apply_agent"),
    )
    workflow.add_conditional_edges(
        "apply_agent",
        _route_after_node("notification_agent"),
    )
    workflow.add_edge("notification_agent", END)

    compiled = workflow.compile()
    logger.info("Supervisor graph compiled successfully.")
    return compiled


# Module-level compiled graph — imported by API routes and Celery tasks
copilot_graph = build_supervisor_graph()
