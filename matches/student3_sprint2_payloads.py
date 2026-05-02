from collections import defaultdict


def _safe_divide(a, b, default=0.0):
    return round(a / b, 4) if b else default


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))


def _player_events_for_innings(innings, player):
    return list(
        innings.ball_events
        .select_related("striker", "bowler")
        .filter(striker=player)
        .order_by("over_number", "ball_number", "id")
    )


def _bowler_events_for_innings(innings, player):
    return list(
        innings.ball_events
        .select_related("striker", "bowler")
        .filter(bowler=player)
        .order_by("over_number", "ball_number", "id")
    )


def _calculate_batting_score(batting_events):
    legal_balls = sum(1 for e in batting_events if e.is_legal_delivery)
    runs = sum(e.runs_off_bat for e in batting_events)
    boundaries = sum(1 for e in batting_events if e.runs_off_bat in [4, 6])
    dots = sum(1 for e in batting_events if e.is_legal_delivery and e.runs_off_bat == 0)

    strike_rate = _safe_divide(runs * 100, legal_balls)
    boundary_rate = _safe_divide(boundaries, legal_balls)
    dot_rate = _safe_divide(dots, legal_balls)

    score = (
        0.45 * min(strike_rate / 2, 100)
        + 0.35 * min(runs * 2, 100)
        + 0.15 * boundary_rate * 100
        + 0.05 * (1 - dot_rate) * 100
    )

    return round(_clamp(score), 2)


def _calculate_bowling_score(bowler_events):
    legal_balls = sum(1 for e in bowler_events if e.is_legal_delivery)

    if legal_balls == 0:
        return 0.0

    runs_conceded = sum(e.total_runs for e in bowler_events)
    wickets = sum(
        1 for e in bowler_events
        if e.wicket_fell and e.wicket_type not in ["run_out", "retired_out"]
    )
    dots = sum(1 for e in bowler_events if e.is_legal_delivery and e.total_runs == 0)
    boundaries = sum(1 for e in bowler_events if e.runs_off_bat in [4, 6])

    economy = _safe_divide(runs_conceded * 6, legal_balls)
    dot_rate = _safe_divide(dots, legal_balls)
    boundary_leakage = _safe_divide(boundaries, legal_balls)

    economy_score = max(0, 100 - economy * 7)

    score = (
        0.35 * economy_score
        + 0.30 * min(wickets * 30, 100)
        + 0.25 * dot_rate * 100
        + 0.10 * (1 - boundary_leakage) * 100
    )

    return round(_clamp(score), 2)


def _calculate_fielding_score(player):
    # Placeholder until Khel MVP has structured fielding event models.
    # Keeps integration stable while allowing future upgrade.
    return 50.0


def build_student3_sprint2_payloads(innings, player):
    batting_events = _player_events_for_innings(innings, player)
    bowling_events = _bowler_events_for_innings(innings, player)

    batting_score = _calculate_batting_score(batting_events)
    bowling_score = _calculate_bowling_score(bowling_events)
    fielding_score = _calculate_fielding_score(player)

    innings_events = list(innings.ball_events.all())
    total_runs = sum(e.total_runs for e in innings_events)
    legal_balls = sum(1 for e in innings_events if e.is_legal_delivery)
    run_rate = _safe_divide(total_runs * 6, legal_balls)

    match_pressure_index = round(max(0, min(1, run_rate / 12)), 3)

    # Since the current MVP is innings-based, we create a recent-over series.
    # Later, this can be replaced by last 5-10 match records from DB.
    batting_by_over = defaultdict(float)
    bowling_by_over = defaultdict(float)

    for event in batting_events:
        batting_by_over[event.over_number] += event.runs_off_bat

    for event in bowling_events:
        bowling_by_over[event.over_number] += max(0, 12 - event.total_runs)

        if event.wicket_fell and event.wicket_type not in ["run_out", "retired_out"]:
            bowling_by_over[event.over_number] += 20

    all_overs = sorted(set(batting_by_over.keys()) | set(bowling_by_over.keys()))

    batting_series = [round(batting_by_over[o], 2) for o in all_overs]
    bowling_series = [round(bowling_by_over[o], 2) for o in all_overs]

    if len(batting_series) < 2:
        batting_series = [batting_score, batting_score * 0.85]

    if len(bowling_series) < 2:
        bowling_series = [bowling_score, bowling_score * 0.85]

    min_len = min(len(batting_series), len(bowling_series))
    batting_series = batting_series[:min_len]
    bowling_series = bowling_series[:min_len]

    weighted_contribution_data = {
        "player_name": player.name,
        "batting_score": batting_score,
        "bowling_score": bowling_score,
        "fielding_score": fielding_score,
        "batting_weight": 0.4,
        "bowling_weight": 0.4,
        "fielding_weight": 0.2,
        "match_pressure_index": match_pressure_index,
    }

    correlation_data = {
        "player_name": player.name,
        "batting_series": batting_series,
        "bowling_series": bowling_series,
    }

    variance_data = {
        "player_name": player.name,
        "batting_series": batting_series,
        "bowling_series": bowling_series,
    }

    return {
        "weighted_contribution_data": weighted_contribution_data,
        "correlation_data": correlation_data,
        "variance_data": variance_data,
        "full_analysis_data": {
            "weighted_contribution_data": weighted_contribution_data,
            "correlation_data": correlation_data,
            "variance_data": variance_data,
        },
    }