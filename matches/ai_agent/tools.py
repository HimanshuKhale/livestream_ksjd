import requests
from typing import Dict, Any, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from matches.models import Match, Innings, Player
from matches.sprint2_payloads import build_student1_sprint2_payload
from matches.ai_agent.schemas import AgentToolResult


def _post_json(url: str, payload: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
    response = requests.post(
        url,
        json=payload,
        timeout=timeout or getattr(settings, "EXTERNAL_ANALYTICS_API_TIMEOUT", 25),
    )
    response.raise_for_status()
    return response.json()


def get_current_scorecard(match: Match, innings: Optional[Innings]) -> AgentToolResult:
    if not innings:
        return AgentToolResult(False, "get_current_scorecard", error="No innings found.")

    from matches.services import innings_summary

    return AgentToolResult(
        ok=True,
        tool_name="get_current_scorecard",
        data=innings_summary(innings),
    )


def call_student1_batting_dashboard(innings: Innings, player: Player) -> AgentToolResult:
    try:
        payload = build_student1_sprint2_payload(innings, player)
        url = f"{settings.STUDENT1_SPRINT2_API_BASE_URL}/api/v1/cards/batting-dashboard"
        data = _post_json(url, payload)

        return AgentToolResult(
            ok=True,
            tool_name="call_student1_batting_dashboard",
            data={
                "payload_sent": payload,
                "api_response": data,
            },
        )
    except Exception as exc:
        return AgentToolResult(
            ok=False,
            tool_name="call_student1_batting_dashboard",
            error=str(exc),
        )


def call_student1_consistency_index(innings: Innings, player: Player) -> AgentToolResult:
    try:
        payload = build_student1_sprint2_payload(innings, player)
        url = f"{settings.STUDENT1_SPRINT2_API_BASE_URL}/api/v1/batting/consistency-index"
        data = _post_json(url, payload)

        return AgentToolResult(
            ok=True,
            tool_name="call_student1_consistency_index",
            data={
                "payload_sent": payload,
                "api_response": data,
            },
        )
    except Exception as exc:
        return AgentToolResult(False, "call_student1_consistency_index", error=str(exc))


def call_student1_pressure_performance(innings: Innings, player: Player) -> AgentToolResult:
    try:
        payload = build_student1_sprint2_payload(innings, player)
        url = f"{settings.STUDENT1_SPRINT2_API_BASE_URL}/api/v1/batting/pressure-performance"
        data = _post_json(url, payload)

        return AgentToolResult(
            ok=True,
            tool_name="call_student1_pressure_performance",
            data={
                "payload_sent": payload,
                "api_response": data,
            },
        )
    except Exception as exc:
        return AgentToolResult(False, "call_student1_pressure_performance", error=str(exc))


def call_student1_shot_risk_efficiency(innings: Innings, player: Player) -> AgentToolResult:
    try:
        payload = build_student1_sprint2_payload(innings, player)
        url = f"{settings.STUDENT1_SPRINT2_API_BASE_URL}/api/v1/batting/shot-risk-efficiency"
        data = _post_json(url, payload)

        return AgentToolResult(
            ok=True,
            tool_name="call_student1_shot_risk_efficiency",
            data={
                "payload_sent": payload,
                "api_response": data,
            },
        )
    except Exception as exc:
        return AgentToolResult(False, "call_student1_shot_risk_efficiency", error=str(exc))


def call_phase1_api(api_name: str, payload: Dict[str, Any]) -> AgentToolResult:
    endpoints = getattr(settings, "PHASE1_API_ENDPOINTS", {})
    url = endpoints.get(api_name)

    if not url:
        return AgentToolResult(
            ok=False,
            tool_name="call_phase1_api",
            error=f"No endpoint configured for Phase 1 API: {api_name}",
        )

    try:
        data = _post_json(url, payload)
        return AgentToolResult(
            ok=True,
            tool_name="call_phase1_api",
            data={
                "api_name": api_name,
                "payload_sent": payload,
                "api_response": data,
            },
        )
    except Exception as exc:
        return AgentToolResult(False, "call_phase1_api", error=str(exc))


def create_agent_banner(
    innings: Innings,
    player: Player,
    metric_type: str,
    title: str,
    text: str,
    display_area: str = "between_balls",
    raw_data: Optional[Dict[str, Any]] = None,
) -> AgentToolResult:
    try:
        card_data = {
            "source": "khel_ai_agent",
            "metric_name": metric_type,
            "score": None,
            "grade": "AI Insight",
            "summary": text,
            "card": {
                "title": title,
                "value": "AI",
                "label": "Insight",
                "insight": text,
                "display_priority": display_area,
                "color_hint": "blue",
                "trend": "stable",
                "confidence": 0.85,
            },
            "raw_data": raw_data or {},
            "created_at": timezone.now().isoformat(),
        }

        return create_temporary_live_banner(
            innings=innings,
            player=player,
            metric_type=metric_type,
            display_area=display_area,
            card_data=card_data,
        )

    except Exception as exc:
        return AgentToolResult(False, "create_agent_banner", error=str(exc))


def create_temporary_live_banner(
    innings: Innings,
    player: Player,
    metric_type: str,
    display_area: str,
    card_data: Dict[str, Any],
) -> AgentToolResult:
    try:
        metric_labels = {
            "batting_dashboard": "Full Batting Dashboard",
            "consistency_index": "Batting Consistency Index",
            "pressure_performance": "Pressure Performance Index",
            "shot_risk_efficiency": "Shot Risk Efficiency",
            "agent_insight": "Khel AI Insight",
        }
        banner_payload = {
            "id": f"temp-banner-{innings.id}",
            "player_name": player.name,
            "metric_type": metric_type,
            "metric_label": metric_labels.get(metric_type, metric_type.replace("_", " ").title()),
            "display_area": display_area,
            "card_data": card_data,
        }

        cache.set(
            f"live_infographic_banner:innings:{innings.id}",
            banner_payload,
            timeout=getattr(settings, "LIVE_INFOGRAPHIC_TTL_SECONDS", 20),
        )

        return AgentToolResult(
            ok=True,
            tool_name="create_temporary_live_banner",
            data={
                "created_banner": True,
                "card_id": None,
                "banner": banner_payload,
            },
        )

    except Exception as exc:
        return AgentToolResult(False, "create_temporary_live_banner", error=str(exc))


def create_api_result_banner(
    innings: Innings,
    player: Player,
    metric_type: str,
    display_area: str,
    tool_result: AgentToolResult,
) -> AgentToolResult:
    if not tool_result.ok:
        return tool_result

    api_response = tool_result.data.get("api_response", {})

    card_data = api_response.get("data", api_response)

    try:
        return create_temporary_live_banner(
            innings=innings,
            player=player,
            metric_type=metric_type,
            display_area=display_area,
            card_data=card_data,
        )

    except Exception as exc:
        return AgentToolResult(False, "create_api_result_banner", error=str(exc))
