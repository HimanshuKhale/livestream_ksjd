from .services import innings_summary


def get_match_phase(innings, overs_completed):
    total_overs = innings.total_overs_limit or 20

    if overs_completed <= total_overs * 0.3:
        return "powerplay"
    if overs_completed <= total_overs * 0.75:
        return "middle"
    return "death"


def build_student1_sprint2_payload(innings, player):
    balls = (
        innings.ball_events
        .select_related("striker", "dismissed_player")
        .order_by("over_number", "ball_number", "id")
    )

    player_balls = [b for b in balls if b.striker_id == player.id and b.is_legal_delivery]
    recent_balls = list(balls)[-12:]
    summary = innings_summary(innings)

    runs = sum(b.runs_off_bat for b in player_balls)
    balls_faced = len(player_balls)
    dot_balls = sum(1 for b in player_balls if b.runs_off_bat == 0)
    ones = sum(1 for b in player_balls if b.runs_off_bat == 1)
    twos = sum(1 for b in player_balls if b.runs_off_bat == 2)
    threes = sum(1 for b in player_balls if b.runs_off_bat == 3)
    fours = sum(1 for b in player_balls if b.runs_off_bat == 4)
    sixes = sum(1 for b in player_balls if b.runs_off_bat == 6)

    dismissed_ball = next(
        (b for b in player_balls if b.dismissed_player_id == player.id),
        None
    )

    legal_balls = balls.filter(is_legal_delivery=True).count()
    overs_completed = legal_balls // 6 + (legal_balls % 6) / 10
    balls_remaining = max((innings.total_overs_limit * 6) - legal_balls, 0)

    latest_ball = player_balls[-1] if player_balls else None

    return {
        "player_id": str(player.id),
        "player_name": player.name,
        "match_id": str(innings.match.id),

        "innings_stats": {
            "runs_scored": runs,
            "balls_faced": balls_faced,
            "dot_balls": dot_balls,
            "fours": fours,
            "sixes": sixes,
            "ones": ones,
            "twos": twos,
            "threes": threes,
            "dismissal_status": "out" if dismissed_ball else "not_out",
            "dismissal_type": dismissed_ball.wicket_type if dismissed_ball else None,
        },

        "match_state": {
            "match_id": str(innings.match.id),
            "innings_number": innings.innings_number,
            "current_score": summary["total_runs"],
            "target": None,
            "wickets_lost": summary["wickets"],
            "overs_completed": overs_completed,
            "balls_remaining": balls_remaining,
            "required_run_rate": 0,
            "current_run_rate": summary["run_rate"],
            "match_phase": get_match_phase(innings, overs_completed),
        },

        "recent_ball_events": [
            {
                "over": b.over_number,
                "ball": b.ball_number,
                "runs": b.runs_off_bat,
                "is_dot": b.runs_off_bat == 0,
                "is_boundary": b.runs_off_bat in [4, 6],
                "is_wicket": b.wicket_fell,
                "shot_type": b.shot_type,
                "shot_zone": b.shot_zone,
                "phase": get_match_phase(innings, overs_completed),
            }
            for b in recent_balls
        ],

        "shot_details": {
            "shot_type": latest_ball.shot_type if latest_ball else "",
            "shot_zone": latest_ball.shot_zone if latest_ball else "",
            "ball_line": "",
            "ball_length": "",
            "is_boundary": latest_ball.runs_off_bat in [4, 6] if latest_ball else False,
            "is_six": latest_ball.runs_off_bat == 6 if latest_ball else False,
            "is_wicket": latest_ball.wicket_fell if latest_ball else False,
            "fielder_position": latest_ball.fielder_name if latest_ball else "",
            "bowler_type": "",
        },
    }