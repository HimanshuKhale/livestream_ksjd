from typing import Optional

from matches.models import Match, Innings


def save_agent_interaction(
    match: Match,
    innings: Optional[Innings],
    user_message: str,
    assistant_answer: str,
    metadata=None,
):
    """
    First version: no database memory required.

    Later, create AgentConversation and AgentMessage models here.
    """
    return {
        "saved": False,
        "reason": "Database memory not enabled in this first version.",
        "metadata": metadata or {},
    }