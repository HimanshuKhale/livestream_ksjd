import requests
from typing import Dict, Any, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from matches.models import Match, Innings, Player
from matches.sprint2_payloads import build_student1_sprint2_payload
from matches.ai_agent.schemas import AgentToolResult

from matches.student2_sprint2_payloads import build_student2_sprint2_payloads
from matches.student3_sprint2_payloads import build_student3_sprint2_payloads

from matches.api_clients import (
    call_student2_bowling_economy_deviation,
    call_student2_wicket_probability_model,
    call_student2_control_entropy_model,
    call_student2_full_bowling_analysis,
    call_student3_weighted_contribution_index,
    call_student3_correlation_analysis,
    call_student3_performance_variance_model,
    call_student3_full_all_rounder_analysis,
)



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
            "bowling_economy_deviation": "Bowling Economy Deviation",
            "wicket_probability_model": "Wicket Probability Model",
            "control_entropy_model": "Control Entropy Model",
            "full_bowling_analysis": "Full Bowling Analysis",
            "agent_insight": "Khel AI Insight",
            "weighted_contribution_index": "Weighted Contribution Index",
            "correlation_analysis": "All-Rounder Correlation Analysis",
            "performance_variance_model": "Performance Variance Model",
            "full_all_rounder_analysis": "Full All-Rounder Analysis",
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

    api_response = tool_result.data.get("api_response", {}) if tool_result.data else {}

    title = metric_type.replace("_", " ").title()
    value = "N/A"
    label = "Analysis"
    insight = "API analysis generated successfully."
    color_hint = "teal"

    # ---------- STUDENT 2 ----------
    if metric_type == "bowling_economy_deviation":
        title = "Bowling Economy Deviation"
        value = api_response.get("normalized_score", "N/A")
        label = api_response.get("rating", "Economy Analysis")
        actual = api_response.get("actual_economy")
        expected = api_response.get("expected_economy")
        deviation = api_response.get("economy_deviation")
        insight = (
            f"Score: {value} | {label} | "
            f"Actual Econ: {actual} | Expected Econ: {expected} | Deviation: {deviation}"
        )

    elif metric_type == "wicket_probability_model":
        title = "Wicket Probability Model"
        value = api_response.get("probability_score", "N/A")
        label = api_response.get("rating", "Wicket Probability")
        probability = api_response.get("wicket_probability")
        dot_rate = api_response.get("dot_ball_rate")
        leakage = api_response.get("boundary_leakage")
        insight = (
            f"Wicket Threat: {value} | {label} | "
            f"Probability: {probability} | Dot Rate: {dot_rate} | Boundary Leakage: {leakage}"
        )

    elif metric_type == "control_entropy_model":
        title = "Control Entropy Model"
        value = api_response.get("control_score", "N/A")
        label = api_response.get("rating", "Control Analysis")
        entropy = api_response.get("entropy")
        good_zone_rate = api_response.get("good_zone_rate")
        insight = (
            f"Control Score: {value} | {label} | "
            f"Entropy: {entropy} | Good Zone Rate: {good_zone_rate}"
        )

    elif metric_type == "full_bowling_analysis":
        title = "Full Bowling Analysis"
        value = api_response.get("final_bowling_intelligence_score", "N/A")
        label = api_response.get("final_rating", "Bowling Analysis")

        economy = api_response.get("economy_analysis", {}).get("normalized_score")
        wicket = api_response.get("wicket_probability_analysis", {}).get("probability_score")
        control = api_response.get("control_entropy_analysis", {}).get("control_score")

        insight = (
            f"Bowling Intelligence: {value} | {label} | "
            f"Economy: {economy} | Wicket Threat: {wicket} | Control: {control}"
        )

    # ---------- STUDENT 3 ----------
    elif metric_type == "weighted_contribution_index":
        title = "Weighted Contribution Index"
        value = api_response.get("weighted_contribution_index", "N/A")
        label = api_response.get("rating", "All-Round Value")

        batting = api_response.get("batting_component")
        bowling = api_response.get("bowling_component")
        fielding = api_response.get("fielding_component")

        insight = (
            f"Contribution: {value} | {label} | "
            f"Batting: {batting} | Bowling: {bowling} | Fielding: {fielding}"
        )

    elif metric_type == "correlation_analysis":
        title = "All-Rounder Correlation"
        value = api_response.get("correlation_coefficient", "N/A")
        label = api_response.get("relationship_label", "Correlation Analysis")
        confidence = api_response.get("confidence_score")
        strength = api_response.get("relationship_strength_score")

        insight = (
            f"Correlation: {value} | {label} | "
            f"Strength: {strength} | Confidence: {confidence}"
        )

    elif metric_type == "performance_variance_model":
        title = "Performance Variance Model"
        value = api_response.get("reliability_score", "N/A")
        label = api_response.get("reliability_label", "Reliability Analysis")

        batting_cv = api_response.get("batting_coefficient_of_variation")
        bowling_cv = api_response.get("bowling_coefficient_of_variation")

        insight = (
            f"Reliability: {value} | {label} | "
            f"Batting CV: {batting_cv} | Bowling CV: {bowling_cv}"
        )

    elif metric_type == "full_all_rounder_analysis":
        title = "Full All-Rounder Analysis"
        value = api_response.get("final_all_rounder_score", "N/A")
        label = api_response.get("final_rating", "All-Rounder Analysis")

        contribution = api_response.get("weighted_contribution_analysis", {}).get("weighted_contribution_index")
        correlation = api_response.get("correlation_analysis", {}).get("correlation_coefficient")
        reliability = api_response.get("performance_variance_analysis", {}).get("reliability_score")

        insight = (
            f"All-Rounder Score: {value} | {label} | "
            f"Contribution: {contribution} | Correlation: {correlation} | Reliability: {reliability}"
        )

    card_data = {
        "source": "external_api",
        "metric_name": metric_type,
        "score": value,
        "grade": label,
        "summary": insight,
        "card": {
            "title": title,
            "value": value,
            "label": label,
            "insight": insight,
            "display_priority": display_area,
            "color_hint": color_hint,
            "trend": "stable",
            "confidence": 0.90,
        },
        "raw_data": api_response,
        "payload_sent": tool_result.data.get("payload_sent", {}),
        "created_at": timezone.now().isoformat(),
    }

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

        
def call_student2_bowling_economy_tool(innings: Innings, player: Player) -> AgentToolResult:
    try:
        payloads = build_student2_sprint2_payloads(innings, player)

        if payloads is None:
            return AgentToolResult(
                ok=False,
                tool_name="call_student2_bowling_economy_tool",
                error="No ball events found for this bowler.",
            )

        data = call_student2_bowling_economy_deviation(payloads["economy_data"])

        return AgentToolResult(
            ok=True,
            tool_name="call_student2_bowling_economy_tool",
            data={
                "payload_sent": payloads["economy_data"],
                "api_response": data,
            },
        )

    except Exception as exc:
        return AgentToolResult(
            ok=False,
            tool_name="call_student2_bowling_economy_tool",
            error=str(exc),
        )


def call_student2_wicket_probability_tool(innings: Innings, player: Player) -> AgentToolResult:
    try:
        payloads = build_student2_sprint2_payloads(innings, player)

        if payloads is None:
            return AgentToolResult(
                ok=False,
                tool_name="call_student2_wicket_probability_tool",
                error="No ball events found for this bowler.",
            )

        data = call_student2_wicket_probability_model(payloads["wicket_data"])

        return AgentToolResult(
            ok=True,
            tool_name="call_student2_wicket_probability_tool",
            data={
                "payload_sent": payloads["wicket_data"],
                "api_response": data,
            },
        )

    except Exception as exc:
        return AgentToolResult(
            ok=False,
            tool_name="call_student2_wicket_probability_tool",
            error=str(exc),
        )


def call_student2_control_entropy_tool(innings: Innings, player: Player) -> AgentToolResult:
    try:
        payloads = build_student2_sprint2_payloads(innings, player)

        if payloads is None:
            return AgentToolResult(
                ok=False,
                tool_name="call_student2_control_entropy_tool",
                error="No ball events found for this bowler.",
            )

        data = call_student2_control_entropy_model(payloads["control_data"])

        return AgentToolResult(
            ok=True,
            tool_name="call_student2_control_entropy_tool",
            data={
                "payload_sent": payloads["control_data"],
                "api_response": data,
            },
        )

    except Exception as exc:
        return AgentToolResult(
            ok=False,
            tool_name="call_student2_control_entropy_tool",
            error=str(exc),
        )


def call_student2_full_bowling_analysis_tool(innings: Innings, player: Player) -> AgentToolResult:
    try:
        payloads = build_student2_sprint2_payloads(innings, player)

        if payloads is None:
            return AgentToolResult(
                ok=False,
                tool_name="call_student2_full_bowling_analysis_tool",
                error="No ball events found for this bowler.",
            )

        data = call_student2_full_bowling_analysis(payloads["full_analysis_data"])

        return AgentToolResult(
            ok=True,
            tool_name="call_student2_full_bowling_analysis_tool",
            data={
                "payload_sent": payloads["full_analysis_data"],
                "api_response": data,
            },
        )

    except Exception as exc:
        return AgentToolResult(
            ok=False,
            tool_name="call_student2_full_bowling_analysis_tool",
            error=str(exc),
        )

def call_student3_weighted_contribution_tool(innings: Innings, player: Player) -> AgentToolResult:
    try:
        payloads = build_student3_sprint2_payloads(innings, player)

        data = call_student3_weighted_contribution_index(
            payloads["weighted_contribution_data"]
        )

        return AgentToolResult(
            ok=True,
            tool_name="call_student3_weighted_contribution_tool",
            data={"payload_sent": payloads["weighted_contribution_data"], "api_response": data},
        )
    except Exception as exc:
        return AgentToolResult(
            ok=False,
            tool_name="call_student3_weighted_contribution_tool",
            error=str(exc),
        )


def call_student3_correlation_analysis_tool(innings: Innings, player: Player) -> AgentToolResult:
    try:
        payloads = build_student3_sprint2_payloads(innings, player)

        data = call_student3_correlation_analysis(payloads["correlation_data"])

        return AgentToolResult(
            ok=True,
            tool_name="call_student3_correlation_analysis_tool",
            data={"payload_sent": payloads["correlation_data"], "api_response": data},
        )
    except Exception as exc:
        return AgentToolResult(
            ok=False,
            tool_name="call_student3_correlation_analysis_tool",
            error=str(exc),
        )


def call_student3_performance_variance_tool(innings: Innings, player: Player) -> AgentToolResult:
    try:
        payloads = build_student3_sprint2_payloads(innings, player)

        data = call_student3_performance_variance_model(payloads["variance_data"])

        return AgentToolResult(
            ok=True,
            tool_name="call_student3_performance_variance_tool",
            data={"payload_sent": payloads["variance_data"], "api_response": data},
        )
    except Exception as exc:
        return AgentToolResult(
            ok=False,
            tool_name="call_student3_performance_variance_tool",
            error=str(exc),
        )


def call_student3_full_all_rounder_analysis_tool(innings: Innings, player: Player) -> AgentToolResult:
    try:
        payloads = build_student3_sprint2_payloads(innings, player)

        data = call_student3_full_all_rounder_analysis(payloads["full_analysis_data"])

        return AgentToolResult(
            ok=True,
            tool_name="call_student3_full_all_rounder_analysis_tool",
            data={"payload_sent": payloads["full_analysis_data"], "api_response": data},
        )
    except Exception as exc:
        return AgentToolResult(
            ok=False,
            tool_name="call_student3_full_all_rounder_analysis_tool",
            error=str(exc),
        )