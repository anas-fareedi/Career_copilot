"""
Notification Agent — Agent 5 in the Career Copilot pipeline.

STATUS: STUBBED for MVP.

This agent notifies the user of application outcomes. In stub mode it:
  - Logs what notifications it *would* send
  - Returns a list of notification summary strings

Real implementation will integrate with:
  - SendGrid / SMTP for email notifications
  - In-app notification table (push via WebSockets or polling)
  - Optional: Slack / Telegram webhook support
"""

import logging

from APP.agents.state import AgentState

logger = logging.getLogger(__name__)


def notify_user_node(state: AgentState) -> dict:
    """
    Agent 5: Notify the user of application status updates (STUBBED).

    Input  state keys: application_results, user_id
    Output state keys: notifications_sent
    """
    logger.info("[Notification Agent] Processing notifications for user %s", state.get("user_id"))

    application_results: list[dict] = state.get("application_results") or []
    user_id: str = state.get("user_id", "unknown")
    notifications_sent: list[str] = []

    if not application_results:
        logger.info("[Notification Agent] No application results — nothing to notify.")
        return {"current_step": "notification_agent", "notifications_sent": []}

    submitted = [r for r in application_results if "submitted" in r.get("status", "")]
    pending = [r for r in application_results if r.get("status") == "pending_review"]

    # ── Real implementation would send emails here ─────────────────────────
    # from sendgrid import SendGridAPIClient
    # from sendgrid.helpers.mail import Mail
    # client = SendGridAPIClient(settings.SENDGRID_API_KEY)
    # client.send(Mail(...))
    # ───────────────────────────────────────────────────────────────────────

    for app in submitted:
        msg = (
            f"[STUB] Email to user {user_id}: "
            f"Application submitted for {app['job_title']} at {app['company']}."
        )
        logger.info("[Notification Agent] %s", msg)
        notifications_sent.append(msg)

    if pending:
        msg = (
            f"[STUB] Email to user {user_id}: "
            f"{len(pending)} application(s) are ready for your review. "
            "Log in to Career Copilot to approve and submit."
        )
        logger.info("[Notification Agent] %s", msg)
        notifications_sent.append(msg)

    logger.info("[Notification Agent] %d notifications dispatched.", len(notifications_sent))
    return {"current_step": "notification_agent", "notifications_sent": notifications_sent}
