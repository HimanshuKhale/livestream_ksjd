from typing import Dict, Any, Optional
from types import SimpleNamespace

from django.core.cache import cache

from matches.models import Match, Innings


def _safe_player_name(player):
    return player.name if player else None


def _innings_summary(innings: Innings) -> Dict[str, Any]:
    balls = innings.ball_events.all()

    total_runs = 0
    wickets = 0
    legal_balls = 0

    for ball in balls:
        total_runs += (ball.runs_off_bat or 0) + (ball.extras or 0)

        if getattr(ball, "wicket_fell", False):
            wickets += 1

        if getattr(ball, "is_legal_delivery", True):
            legal_balls += 1

    overs = f"{legal_balls // 6}.{legal_balls % 6}"
    run_rate = round((total_runs / legal_balls) * 6, 2) if legal_balls else 0

    return {
        "total_runs": total_runs,
        "wickets": wickets,
        "legal_balls": legal_balls,
        "overs": overs,
        "run_rate": run_rate,
    }


def _get_scoring_state(innings: Innings):
    last_ball = (
        innings.ball_events
        .select_related("striker", "non_striker", "bowler")
        .order_by("-over_number", "-ball_number", "-id")
        .first()
    )

    if not last_ball:
        return SimpleNamespace(
            striker_id=None,
            non_striker_id=None,
            bowler_id=None,
        )

    return SimpleNamespace(
        striker_id=getattr(last_ball, "striker_id", None),
        non_striker_id=getattr(last_ball, "non_striker_id", None),
        bowler_id=getattr(last_ball, "bowler_id", None),
    )


def build_match_context(match: Match, innings: Optional[Innings] = None) -> Dict[str, Any]:
    if innings is None:
        innings = (
            match.innings
            .select_related("match", "batting_team", "bowling_team")
            .order_by("-innings_number")
            .first()
        )

    if not innings:
        return {
            "match_id": match.id,
            "match_name": str(match),
            "has_innings": False,
            "message": "No innings available yet.",
        }

    scoring_state = _get_scoring_state(innings)
    summary = _innings_summary(innings)

    recent_balls = list(
        innings.ball_events
        .select_related("striker", "bowler", "dismissed_player")
        .order_by("-over_number", "-ball_number", "-id")[:12]
    )
    recent_balls.reverse()

    active_infographic = cache.get(f"live_infographic_banner:innings:{innings.id}")

    batting_players = list(innings.batting_team.players.all())

    return {
        "match_id": match.id,
        "match_name": str(match),
        "has_innings": True,
        "innings_id": innings.id,
        "innings_number": innings.innings_number,
        "batting_team": innings.batting_team.name,
        "bowling_team": innings.bowling_team.name,
        "score": summary,
        "current_state": {
            "striker_id": scoring_state.striker_id,
            "non_striker_id": scoring_state.non_striker_id,
            "bowler_id": scoring_state.bowler_id,
        },
        "players_available_for_analysis": [
            {
                "id": player.id,
                "name": player.name,
            }
            for player in batting_players
        ],
        "recent_balls": [
            {
                "over": ball.over_number,
                "ball": ball.ball_number,
                "striker": _safe_player_name(ball.striker),
                "bowler": _safe_player_name(ball.bowler),
                "runs_off_bat": ball.runs_off_bat,
                "extras": ball.extras,
                "wicket_fell": ball.wicket_fell,
                "dismissed_player": _safe_player_name(ball.dismissed_player),
                "shot_type": getattr(ball, "shot_type", ""),
                "shot_zone": getattr(ball, "shot_zone", ""),
            }
            for ball in recent_balls
        ],
        "active_infographics": [active_infographic] if active_infographic else [],
    }
