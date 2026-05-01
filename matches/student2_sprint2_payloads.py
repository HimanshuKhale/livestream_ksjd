from collections import Counter


CONTROL_ZONE_MAP = {
    "straight": "good_length_off",
    "long_off": "good_length_off",
    "deep_extra_cover": "good_length_off",
    "cover": "good_length_off",
    "point": "wide_outside_off",
    "third_man": "wide_outside_off",
    "fine_leg": "leg_side",
    "square_leg": "leg_side",
    "deep_mid_wicket": "short_ball",
    "long_on": "yorker",
    "deep_mid_on": "back_of_length",
    "mid_wicket": "short_ball",
    "deep_square_leg": "short_ball",
    "short_leg": "leg_side",
    "silly_point": "good_length_off",
    "silly_mid_on": "back_of_length",
    "silly_mid_wicket": "short_ball",
}


def _safe_divide(a, b, default=0.0):
    return round(a / b, 4) if b else default


def _phase_from_balls(legal_balls):
    over = legal_balls / 6

    if over <= 6:
        return "powerplay"
    if over <= 15:
        return "middle"
    return "death"


def _estimate_pressure_index(innings, bowler_events):
    all_events = list(innings.ball_events.all())

    total_runs = sum(e.total_runs for e in all_events)
    legal_balls = sum(1 for e in all_events if e.is_legal_delivery)
    wickets = sum(1 for e in all_events if e.wicket_fell)

    current_run_rate = (total_runs / legal_balls) * 6 if legal_balls else 0
    wicket_pressure = min(wickets / 10, 1)

    recent_events = all_events[-12:]
    recent_runs = sum(e.total_runs for e in recent_events)
    recent_legal_balls = sum(1 for e in recent_events if e.is_legal_delivery)
    recent_run_rate = (recent_runs / recent_legal_balls) * 6 if recent_legal_balls else current_run_rate

    bowler_dots = sum(1 for e in bowler_events if e.is_legal_delivery and e.total_runs == 0)
    bowler_legal = sum(1 for e in bowler_events if e.is_legal_delivery)
    bowler_dot_rate = _safe_divide(bowler_dots, bowler_legal)

    run_pressure = min(current_run_rate / 12, 1)
    recent_pressure = min(recent_run_rate / 14, 1)

    pressure_index = (
        0.35 * run_pressure
        + 0.30 * recent_pressure
        + 0.20 * wicket_pressure
        + 0.15 * bowler_dot_rate
    )

    return round(max(0, min(1, pressure_index)), 3)


def _estimate_batter_aggression(bowler_events):
    legal_balls = sum(1 for e in bowler_events if e.is_legal_delivery)

    boundaries = sum(1 for e in bowler_events if e.runs_off_bat in [4, 6])
    attacking_shots = sum(
        1
        for e in bowler_events
        if e.shot_type in ["drive", "cut", "pull", "sweep", "lofted"]
    )

    boundary_rate = _safe_divide(boundaries, legal_balls)
    attacking_shot_rate = _safe_divide(attacking_shots, legal_balls)

    aggression = (0.60 * boundary_rate) + (0.40 * attacking_shot_rate)

    return round(max(0, min(1, aggression)), 3)


def _estimate_line_length_accuracy(bowler_events):
    legal_balls = sum(1 for e in bowler_events if e.is_legal_delivery)

    good_zones = {
        "straight",
        "long_off",
        "deep_extra_cover",
        "cover",
        "silly_point",
        "long_on",
        "deep_mid_on",
    }

    good_zone_balls = sum(
        1
        for e in bowler_events
        if e.is_legal_delivery and e.shot_zone in good_zones
    )

    bad_balls = sum(
        1
        for e in bowler_events
        if e.extra_type in ["wide", "no_ball"] or e.runs_off_bat in [4, 6]
    )

    good_zone_rate = _safe_divide(good_zone_balls, legal_balls)
    bad_ball_rate = _safe_divide(bad_balls, legal_balls)

    accuracy = (0.75 * good_zone_rate) + (0.25 * (1 - bad_ball_rate))

    return round(max(0, min(1, accuracy)), 3)


def build_student2_sprint2_payloads(innings, bowler):
    bowler_events = list(
        innings.ball_events
        .select_related("bowler", "striker")
        .filter(bowler=bowler)
        .order_by("over_number", "ball_number", "id")
    )

    if not bowler_events:
        return None

    all_events = list(innings.ball_events.all())

    bowler_legal_balls = sum(1 for e in bowler_events if e.is_legal_delivery)
    overs_bowled = bowler_legal_balls / 6 if bowler_legal_balls else 0

    runs_conceded = sum(e.total_runs for e in bowler_events)

    wickets_taken = sum(
        1
        for e in bowler_events
        if e.wicket_fell and e.wicket_type not in ["run_out", "retired_out"]
    )

    dot_balls = sum(
        1
        for e in bowler_events
        if e.is_legal_delivery and e.total_runs == 0
    )

    boundaries_conceded = sum(
        1
        for e in bowler_events
        if e.runs_off_bat in [4, 6]
    )

    innings_legal_balls = sum(1 for e in all_events if e.is_legal_delivery)
    match_phase = _phase_from_balls(innings_legal_balls)

    total_runs = sum(e.total_runs for e in all_events)
    opposition_run_rate = (total_runs / innings_legal_balls) * 6 if innings_legal_balls else 7.5

    # Until venue/team historical tables exist, use live innings context as proxy.
    venue_average_economy = max(6.0, min(12.0, opposition_run_rate))
    team_average_economy = max(6.0, min(12.0, opposition_run_rate))

    pressure_index = _estimate_pressure_index(innings, bowler_events)
    batter_aggression = _estimate_batter_aggression(bowler_events)
    line_length_accuracy = _estimate_line_length_accuracy(bowler_events)

    zone_counter = Counter()

    for event in bowler_events:
        if not event.is_legal_delivery:
            continue

        mapped_zone = CONTROL_ZONE_MAP.get(event.shot_zone or "", "slot_ball")

        if event.extra_type in ["wide", "no_ball"]:
            mapped_zone = "wide_outside_off"

        if event.runs_off_bat in [4, 6]:
            mapped_zone = "slot_ball"

        zone_counter[mapped_zone] += 1

    if not zone_counter:
        zone_counter["unknown"] = bowler_legal_balls or 1

    economy_data = {
        "bowler_name": bowler.name,
        "overs_bowled": round(overs_bowled, 2),
        "runs_conceded": runs_conceded,
        "match_phase": match_phase,
        "venue_average_economy": round(venue_average_economy, 2),
        "team_average_economy": round(team_average_economy, 2),
        "opposition_run_rate": round(opposition_run_rate, 2),
        "pressure_index": pressure_index,
    }

    wicket_data = {
        "bowler_name": bowler.name,
        "balls_bowled": bowler_legal_balls,
        "wickets_taken": wickets_taken,
        "dot_balls": dot_balls,
        "boundaries_conceded": boundaries_conceded,
        "average_batter_aggression": batter_aggression,
        "line_length_accuracy": line_length_accuracy,
        "pressure_index": pressure_index,
        "match_phase": match_phase,
    }

    control_data = {
        "bowler_name": bowler.name,
        "delivery_distribution": dict(zone_counter),
    }

    return {
        "economy_data": economy_data,
        "wicket_data": wicket_data,
        "control_data": control_data,
        "full_analysis_data": {
            "economy_data": economy_data,
            "wicket_data": wicket_data,
            "control_data": control_data,
        },
    }