import json
from typing import Dict, Any, Optional, List

from django.conf import settings
from openai import OpenAI

from matches.models import Match, Innings, Player
from matches.ai_agent.context_builder import build_match_context
from matches.ai_agent.prompts import KHEL_AI_AGENT_SYSTEM_PROMPT, AGENT_JSON_INSTRUCTION
from matches.ai_agent.tools import (
    get_current_scorecard,
    call_student1_batting_dashboard,
    call_student1_consistency_index,
    call_student1_pressure_performance,
    call_student1_shot_risk_efficiency,
    call_student2_bowling_economy_tool,
    call_student2_wicket_probability_tool,
    call_student2_control_entropy_tool,
    call_student2_full_bowling_analysis_tool,
    create_agent_banner,
    create_api_result_banner,
)
from matches.ai_agent.memory import save_agent_interaction


def _safe_json_loads(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass

    return {
        "answer": text,
        "should_create_banner": False,
        "banner_request": {},
    }


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)

def _pick_default_player(innings: Innings, context: Dict[str, Any], role: str = "batter") -> Optional[Player]:
    if role == "bowler":
        bowler_id = context.get("current_state", {}).get("bowler_id")
        if bowler_id:
            return Player.objects.filter(id=bowler_id).first()

        latest_ball = innings.ball_events.select_related("bowler").order_by("-id").first()
        if latest_ball:
            return latest_ball.bowler

        return innings.bowling_team.players.first()

    striker_id = context.get("current_state", {}).get("striker_id")
    if striker_id:
        return Player.objects.filter(id=striker_id).first()

    return innings.batting_team.players.first()

def _find_player_from_request(
    banner_request: Dict[str, Any],
    innings: Innings,
    context: Dict[str, Any],
) -> Optional[Player]:
    player_id = banner_request.get("player_id")

    if player_id:
        player = Player.objects.filter(id=player_id).first()
        if player:
            return player

    metric_type = banner_request.get("metric_type") or ""

    bowling_metrics = {
        "bowling_economy_deviation",
        "wicket_probability_model",
        "control_entropy_model",
        "full_bowling_analysis",
    }

    if metric_type in bowling_metrics:
        return _pick_default_player(innings, context, role="bowler")

    return _pick_default_player(innings, context, role="batter")

def _run_metric_tool(metric_type: str, innings: Innings, player: Player):
    if metric_type == "batting_dashboard":
        return call_student1_batting_dashboard(innings, player)

    if metric_type == "consistency_index":
        return call_student1_consistency_index(innings, player)

    if metric_type == "pressure_performance":
        return call_student1_pressure_performance(innings, player)

    if metric_type == "shot_risk_efficiency":
        return call_student1_shot_risk_efficiency(innings, player)

    if metric_type == "bowling_economy_deviation":
        return call_student2_bowling_economy_tool(innings, player)

    if metric_type == "wicket_probability_model":
        return call_student2_wicket_probability_tool(innings, player)

    if metric_type == "control_entropy_model":
        return call_student2_control_entropy_tool(innings, player)

    if metric_type == "full_bowling_analysis":
        return call_student2_full_bowling_analysis_tool(innings, player)

    return call_student1_batting_dashboard(innings, player)

def run_khel_ai_agent(
    match: Match,
    message: str,
    innings: Optional[Innings] = None,
    allow_create_banner: bool = True,
) -> Dict[str, Any]:
    if innings is None:
        innings = (
            match.innings
            .select_related("match", "batting_team", "bowling_team")
            .order_by("-innings_number")
            .first()
        )

    context = build_match_context(match, innings)

    if not settings.OPENAI_API_KEY:
        return {
            "ok": False,
            "answer": "OPENAI_API_KEY is missing. Add it to your environment first.",
            "tool_results": [],
            "created_banner": False,
            "created_card_id": None,
        }

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    prompt = f"""
{KHEL_AI_AGENT_SYSTEM_PROMPT}

{AGENT_JSON_INSTRUCTION}

MATCH CONTEXT:
{json.dumps(context, default=str, indent=2)}

ADMIN MESSAGE:
{message}

Available metric types:
- batting_dashboard
- consistency_index
- pressure_performance
- shot_risk_efficiency
- bowling_economy_deviation
- wicket_probability_model
- control_entropy_model
- full_bowling_analysis
- agent_insight

Always answer in chat. Set should_create_banner to true only when the admin explicitly asks to show/create/display a banner/card/infographic on the live screen.
"""

    response = client.responses.create(
        model=getattr(settings, "KHEL_AI_AGENT_MODEL", "gpt-5.2"),
        input=prompt,
    )

    parsed = _safe_json_loads(response.output_text)

    answer = parsed.get("answer", "No answer generated.")
    should_create_banner = _as_bool(parsed.get("should_create_banner"))
    banner_request = parsed.get("banner_request") or {}

    tool_results: List[Dict[str, Any]] = []
    created_banner = False

    if innings:
        score_tool = get_current_scorecard(match, innings)
        tool_results.append(score_tool.__dict__)

    if should_create_banner and allow_create_banner and innings:
        player = _find_player_from_request(banner_request, innings, context)
        if not player:
            answer = f"{answer}\n\nI could not create the banner because no batting player was available."
        else:
            metric_type = banner_request.get("metric_type") or "batting_dashboard"
            display_area = banner_request.get("display_area") or "between_balls"

            if metric_type == "agent_insight":
                banner_result = create_agent_banner(
                    innings=innings,
                    player=player,
                    metric_type="agent_insight",
                    title=banner_request.get("banner_title") or "Khel AI Insight",
                    text=banner_request.get("banner_text") or answer,
                    display_area=display_area,
                    raw_data={"source": "agent_response"},
                )
            else:
                tool_result = _run_metric_tool(metric_type, innings, player)
                tool_results.append(tool_result.__dict__)

                if tool_result.ok:
                    banner_result = create_api_result_banner(
                        innings=innings,
                        player=player,
                        metric_type=metric_type,
                        display_area=display_area,
                        tool_result=tool_result,
                    )
                else:
                    banner_result = create_agent_banner(
                        innings=innings,
                        player=player,
                        metric_type="agent_insight",
                        title=banner_request.get("banner_title") or "Khel AI Insight",
                        text=banner_request.get("banner_text") or answer,
                        display_area=display_area,
                        raw_data={"failed_tool": tool_result.__dict__},
                    )

            tool_results.append(banner_result.__dict__)

            if banner_result.ok:
                created_banner = bool(banner_result.data.get("created_banner"))

    save_agent_interaction(
        match=match,
        innings=innings,
        user_message=message,
        assistant_answer=answer,
        metadata={
            "tool_results": tool_results,
            "created_banner": created_banner,
            "created_card_id": None,
        },
    )

    return {
        "ok": True,
        "answer": answer,
        "created_banner": created_banner,
        "created_card_id": None,
        "tool_results": tool_results,
    }
