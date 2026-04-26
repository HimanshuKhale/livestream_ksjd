from .services import innings_summary


def player_ref(player):
    if player is None:
        return None
    return {
        "id": player.id,
        "name": player.name,
    }


def _innings_target(innings):
    if innings.innings_number < 2:
        return None

    first_innings = (
        innings.match.innings.filter(innings_number=1)
        .prefetch_related("ball_events")
        .first()
    )
    if first_innings is None:
        return None

    return innings_summary(first_innings)["total_runs"] + 1


def _balls_for_innings(innings):
    events = (
        innings.ball_events.select_related(
            "striker",
            "non_striker",
            "bowler",
            "dismissed_player",
        )
        .order_by("over_number", "ball_number", "id")
    )

    return [
        {
            "over_number": e.over_number,
            "ball_number": e.ball_number,
            "striker": player_ref(e.striker),
            "non_striker": player_ref(e.non_striker),
            "bowler": player_ref(e.bowler),
            "runs_off_bat": e.runs_off_bat,
            "extras": e.extras,
            "extra_type": e.extra_type or "",
            "is_legal_delivery": e.is_legal_delivery,
            "wicket_fell": e.wicket_fell,
            "wicket_type": e.wicket_type or "",
            "dismissed_player": player_ref(e.dismissed_player),
            "fielder_name": e.fielder_name or None,
            "notes": e.notes or None,
        }
        for e in events
    ]


def build_innings_payload(innings):
    target = _innings_target(innings)
    match = innings.match

    return {
        "match": {
            "id": match.id,
            "title": match.title,
            "venue": match.venue,
            "total_overs": innings.total_overs_limit,
            "target": target,
        },
        "innings": {
            "id": innings.id,
            "innings_number": innings.innings_number,
            "batting_team": innings.batting_team.name,
            "bowling_team": innings.bowling_team.name,
            "total_overs_limit": innings.total_overs_limit,
            "target": target,
        },
        "balls": _balls_for_innings(innings),
    }


def build_batting_form_payload(innings, player_id):
    if not player_id:
        return {
            "player_id": 0,
            "innings_payloads": [],
        }

    innings_list = (
        innings.match.innings
        .select_related("match", "batting_team", "bowling_team")
        .prefetch_related("ball_events")
        .order_by("innings_number")
    )

    return {
        "player_id": player_id,
        "innings_payloads": [
            build_innings_payload(item)
            for item in innings_list
        ],
    }


def build_bowling_form_payload(innings, player_id):
    if not player_id:
        return {
            "player_id": 0,
            "innings_payloads": [],
        }

    innings_list = (
        innings.match.innings
        .select_related("match", "batting_team", "bowling_team")
        .prefetch_related("ball_events")
        .order_by("innings_number")
    )

    return {
        "player_id": player_id,
        "innings_payloads": [
            build_innings_payload(item)
            for item in innings_list
        ],
    }


def build_recent_balls_payload(innings, limit=12):
    return {
        "innings_payload": build_innings_payload(innings),
        "limit": limit,
        "order": "oldest_to_newest",
    }


def build_momentum_payload(innings, recent_overs_window=3):
    return {
        "innings_payload": build_innings_payload(innings),
        "recent_overs_window": recent_overs_window,
    }

def build_match_state_payload(innings):
    return build_innings_payload(innings)
