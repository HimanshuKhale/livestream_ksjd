from collections import defaultdict


def innings_summary(innings):
    events = list(innings.ball_events.select_related("striker", "bowler"))

    total_runs = sum(e.total_runs for e in events)
    wickets = sum(1 for e in events if e.wicket_fell)
    legal_balls = sum(1 for e in events if e.is_legal_delivery)

    overs = f"{legal_balls // 6}.{legal_balls % 6}"
    run_rate = round((total_runs / (legal_balls / 6)), 2) if legal_balls else 0.0

    batter_stats = defaultdict(lambda: {
        "name": "",
        "runs": 0,
        "balls": 0,
        "fours": 0,
        "sixes": 0,
        "strike_rate": 0.0,
    })

    bowler_stats = defaultdict(lambda: {
        "name": "",
        "balls": 0,
        "runs_conceded": 0,
        "wickets": 0,
        "overs": "0.0",
        "economy": 0.0,
    })

    for e in events:
        batter = batter_stats[e.striker_id]
        batter["name"] = e.striker.name
        batter["runs"] += e.runs_off_bat

        if e.is_legal_delivery:
            batter["balls"] += 1

        if e.runs_off_bat == 4:
            batter["fours"] += 1
        if e.runs_off_bat == 6:
            batter["sixes"] += 1

        bowler = bowler_stats[e.bowler_id]
        bowler["name"] = e.bowler.name
        bowler["runs_conceded"] += e.total_runs

        if e.is_legal_delivery:
            bowler["balls"] += 1

        if e.wicket_fell and e.wicket_type not in {"run_out", "retired_out"}:
            bowler["wickets"] += 1

    for item in batter_stats.values():
        item["strike_rate"] = round((item["runs"] / item["balls"]) * 100, 2) if item["balls"] else 0.0

    for item in bowler_stats.values():
        item["overs"] = f"{item['balls'] // 6}.{item['balls'] % 6}"
        item["economy"] = round((item["runs_conceded"] / (item["balls"] / 6)), 2) if item["balls"] else 0.0

    batters = sorted(batter_stats.values(), key=lambda x: (-x["runs"], x["balls"]))
    bowlers = sorted(bowler_stats.values(), key=lambda x: (-x["wickets"], x["runs_conceded"]))

    recent_balls = [
        {
            "over_ball": f"{e.over_number}.{e.ball_number}",
            "striker": e.striker.name,
            "bowler": e.bowler.name,
            "runs": e.total_runs,
            "wicket": e.wicket_fell,
            "label": _ball_label(e),
        }
        for e in events[-6:]
    ]

    return {
        "total_runs": total_runs,
        "wickets": wickets,
        "legal_balls": legal_balls,
        "overs": overs,
        "run_rate": run_rate,
        "batters": batters,
        "bowlers": bowlers,
        "top_batter": batters[0] if batters else None,
        "top_bowler": bowlers[0] if bowlers else None,
        "recent_balls": recent_balls,
    }


def _ball_label(event):
    parts = []

    if event.extra_type:
        parts.append(event.extra_type.replace("_", " ").title())

    parts.append(str(event.total_runs) if event.total_runs else "0")

    if event.wicket_fell:
        parts.append("W")

    return " ".join(parts)