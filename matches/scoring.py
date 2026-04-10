from dataclasses import dataclass

from .models import BallEvent


RESET_FIELDS = {
    "runs_off_bat": 0,
    "extras": 0,
    "extra_type": "",
    "is_legal_delivery": True,
    "wicket_fell": False,
    "wicket_type": "",
    "dismissed_player": None,
    "fielder_name": "",
    "shot_type": "",
    "shot_zone": "",
    "notes": "",
}


@dataclass(frozen=True)
class ScoringState:
    previous_ball: BallEvent | None
    over_number: int
    ball_number: int
    striker_id: int | None
    non_striker_id: int | None
    bowler_id: int | None
    requires_new_bowler: bool
    suggested_next_batter_ids: list[int]
    innings_is_empty: bool

    def as_form_initial(self):
        initial = {
            "over_number": self.over_number,
            "ball_number": self.ball_number,
            "striker": self.striker_id,
            "non_striker": self.non_striker_id,
            "bowler": self.bowler_id,
            **RESET_FIELDS,
        }
        return initial


def get_scoring_state(innings) -> ScoringState:
    events = list(
        innings.ball_events.select_related("striker", "non_striker", "bowler", "dismissed_player")
        .order_by("over_number", "ball_number", "id")
    )
    previous_ball = events[-1] if events else None

    if previous_ball is None:
        return ScoringState(
            previous_ball=None,
            over_number=1,
            ball_number=1,
            striker_id=None,
            non_striker_id=None,
            bowler_id=None,
            requires_new_bowler=False,
            suggested_next_batter_ids=_available_batter_ids(innings, active_batter_ids=[]),
            innings_is_empty=True,
        )

    post_event = _derive_post_event_state(previous_ball)
    return ScoringState(
        previous_ball=previous_ball,
        over_number=post_event["over_number"],
        ball_number=post_event["ball_number"],
        striker_id=post_event["striker_id"],
        non_striker_id=post_event["non_striker_id"],
        bowler_id=post_event["bowler_id"],
        requires_new_bowler=post_event["requires_new_bowler"],
        suggested_next_batter_ids=_available_batter_ids(
            innings,
            active_batter_ids=[post_event["striker_id"], post_event["non_striker_id"]],
        ),
        innings_is_empty=False,
    )


def normalize_event_data(cleaned_data):
    extra_type = cleaned_data.get("extra_type") or ""
    if extra_type in {"wide", "no_ball"}:
        cleaned_data["is_legal_delivery"] = False
    return cleaned_data


def validate_event_state(innings, cleaned_data):
    striker = cleaned_data.get("striker")
    non_striker = cleaned_data.get("non_striker")
    bowler = cleaned_data.get("bowler")
    dismissed_player = cleaned_data.get("dismissed_player")
    wicket_fell = cleaned_data.get("wicket_fell")
    wicket_type = cleaned_data.get("wicket_type") or ""

    errors = {}

    if striker and non_striker and striker == non_striker:
        errors["non_striker"] = "Striker and non-striker must be different players."

    if striker and striker.team_id != innings.batting_team_id:
        errors["striker"] = "Striker must belong to the batting team."

    if non_striker and non_striker.team_id != innings.batting_team_id:
        errors["non_striker"] = "Non-striker must belong to the batting team."

    if bowler and bowler.team_id != innings.bowling_team_id:
        errors["bowler"] = "Bowler must belong to the bowling team."

    if wicket_fell and not wicket_type:
        errors["wicket_type"] = "Wicket type is required when a wicket falls."

    active_batter_ids = {player.id for player in (striker, non_striker) if player}
    if wicket_fell and dismissed_player and dismissed_player.id not in active_batter_ids:
        errors["dismissed_player"] = "Dismissed player must be one of the active batters."

    if (
        dismissed_player
        and dismissed_player.team_id != innings.batting_team_id
    ):
        errors["dismissed_player"] = "Dismissed player must belong to the batting team."

    return errors


def _derive_post_event_state(event):
    striker_id = event.striker_id
    non_striker_id = event.non_striker_id

    if _should_swap_strike(event):
        striker_id, non_striker_id = non_striker_id, striker_id

    next_over_number = event.over_number
    next_ball_number = event.ball_number
    requires_new_bowler = False
    next_bowler_id = event.bowler_id

    if event.is_legal_delivery:
        if event.ball_number >= 6:
            next_over_number += 1
            next_ball_number = 1
            striker_id, non_striker_id = non_striker_id, striker_id
            next_bowler_id = None
            requires_new_bowler = True
        else:
            next_ball_number += 1

    if event.wicket_fell:
        dismissed_id = event.dismissed_player_id or event.striker_id
        if striker_id == dismissed_id:
            striker_id = None
        elif non_striker_id == dismissed_id:
            non_striker_id = None

    return {
        "over_number": next_over_number,
        "ball_number": next_ball_number,
        "striker_id": striker_id,
        "non_striker_id": non_striker_id,
        "bowler_id": next_bowler_id,
        "requires_new_bowler": requires_new_bowler,
    }


def _should_swap_strike(event):
    if event.extra_type == "wide":
        return max(event.extras - 1, 0) % 2 == 1

    if event.extra_type == "no_ball":
        return (event.runs_off_bat + max(event.extras - 1, 0)) % 2 == 1

    return event.total_runs % 2 == 1


def _available_batter_ids(innings, active_batter_ids):
    dismissed_ids = set(
        innings.ball_events.filter(wicket_fell=True)
        .exclude(dismissed_player__isnull=True)
        .values_list("dismissed_player_id", flat=True)
    )
    excluded_ids = dismissed_ids | {player_id for player_id in active_batter_ids if player_id}
    return list(
        innings.batting_team.players.exclude(id__in=excluded_ids)
        .order_by("name")
        .values_list("id", flat=True)
    )
