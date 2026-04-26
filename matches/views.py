from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import LiveInfographicCard
from .sprint2_payloads import build_student1_sprint2_payload
from . import api_clients
from .analytics_payloads import (
    build_batting_form_payload,
    build_bowling_form_payload,
    build_innings_payload,
    build_match_state_payload,
    build_momentum_payload,
    build_recent_balls_payload,
)
from .forms import BallEventForm, InningsForm, MatchForm
from .models import Innings, Match, Player
from .scoring import get_scoring_state
from .services import innings_summary, build_bowler_momentum_payload
from .api_clients import call_bowler_momentum_api


def home(request):
    matches = Match.objects.select_related("team_1", "team_2").all()[:10]
    return render(request, "matches/home.html", {"matches": matches})


def match_create(request):
    form = MatchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        match = form.save()
        messages.success(request, "Match created.")
        return redirect(match.get_absolute_url())
    return render(request, "matches/form_page.html", {"title": "Create Match", "form": form})


def innings_create(request):
    form = InningsForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        innings = form.save()
        messages.success(request, "Innings created.")
        return redirect(innings.get_absolute_url())
    return render(request, "matches/form_page.html", {"title": "Create Innings", "form": form})


def match_detail(request, pk):
    match = get_object_or_404(
        Match.objects.prefetch_related("innings__ball_events"),
        pk=pk
    )

    innings_list = []
    for innings in match.innings.select_related("batting_team", "bowling_team").all():
        innings_list.append((innings, innings_summary(innings)))

    return render(
        request,
        "matches/match_detail.html",
        {
            "match": match,
            "innings_list": innings_list,
        },
    )


def innings_scoring(request, pk):
    innings = get_object_or_404(
        Innings.objects.select_related("match", "batting_team", "bowling_team"),
        pk=pk
    )

    scoring_state = get_scoring_state(innings)
    form_kwargs = {
        "innings": innings,
        "scoring_state": scoring_state,
    }
    if request.method == "POST":
        form = BallEventForm(request.POST, **form_kwargs)
    else:
        form = BallEventForm(initial=scoring_state.as_form_initial(), **form_kwargs)

    if request.method == "POST" and form.is_valid():
        ball = form.save(commit=False)
        ball.innings = innings
        ball.save()
        messages.success(request, f"Ball {ball.over_number}.{ball.ball_number} saved.")
        return redirect("innings_scoring", pk=innings.pk)

    summary = innings_summary(innings)
    suggested_batters = list(
        innings.batting_team.players.filter(id__in=scoring_state.suggested_next_batter_ids).order_by("name")
    )
    batting_players = innings.batting_team.players.in_bulk()
    bowling_players = innings.bowling_team.players.in_bulk()
    next_ball_context = {
        "over_number": scoring_state.over_number,
        "ball_number": scoring_state.ball_number,
        "striker_name": batting_players.get(scoring_state.striker_id).name if scoring_state.striker_id in batting_players else "",
        "non_striker_name": batting_players.get(scoring_state.non_striker_id).name if scoring_state.non_striker_id in batting_players else "",
        "bowler_name": bowling_players.get(scoring_state.bowler_id).name if scoring_state.bowler_id in bowling_players else "",
        "requires_new_bowler": scoring_state.requires_new_bowler,
    }
    previous_ball = scoring_state.previous_ball

    return render(
        request,
        "matches/innings_scoring.html",
        {
            "innings": innings,
            "form": form,
            "scoring_state": scoring_state,
            "next_ball_context": next_ball_context,
            "previous_ball": previous_ball,
            "summary": summary,
            "suggested_batters": suggested_batters,
        },
    )

def live_match(request, match_id):
    match = get_object_or_404(
        Match.objects.select_related("team_1", "team_2"),
        pk=match_id
    )
    innings = match.innings.select_related("batting_team", "bowling_team").order_by("-innings_number").first()
    
    active_infographic = None
    live_batting = None
    bowling_players = []
    analytics_cards = []
    bottom_bar_analytics = []
    last_ball_metadata = {
        "last_ball_id": None,
        "last_ball_label": None,
        "total_ball_events": 0,
    }

    if innings:
        scoring_state = get_scoring_state(innings)
        batting_players = innings.batting_team.players.in_bulk()
        bowling_players = list(innings.bowling_team.players.order_by("name"))

        striker = batting_players.get(scoring_state.striker_id) if scoring_state.striker_id else None
        non_striker = batting_players.get(scoring_state.non_striker_id) if scoring_state.non_striker_id else None

        live_batting = get_current_batting_display(innings)
        last_ball_metadata = get_last_ball_metadata(innings)
        analytics_cards, bottom_bar_analytics = _build_live_analytics(
            innings,
            batting_player_id=scoring_state.striker_id,
            bowling_player_id=scoring_state.bowler_id,
        )
        active_infographic = (
            innings.live_infographic_cards
            .filter(is_active=True)
            .select_related("player")
            .order_by("-created_at")
            .first()
        )

    return render(
        request,
        "matches/live_match.html",
        {
            "match": match,
            "innings": innings,
            "live_batting": live_batting,
            "bowling_players": bowling_players,
            "analytics_cards": analytics_cards,
            "bottom_bar_analytics": bottom_bar_analytics,
            "last_ball_metadata": last_ball_metadata,
            "active_infographic": active_infographic,
        },
    )

def live_analytics_api(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    innings = (
        match.innings.select_related("match", "batting_team", "bowling_team")
        .order_by("-innings_number")
        .first()
    )

    if not innings:
        return JsonResponse({
            "ok": True,
            "match_id": match.id,
            "innings_id": None,
            "last_ball_id": None,
            "last_ball_label": None,
            "total_ball_events": 0,
            "analytics_cards": [],
            "bottom_bar_analytics": [],
            "active_infographic": None,
            "active_infographics": [],
            "message": "No innings available yet.",
        })

    scoring_state = get_scoring_state(innings)

    analytics_cards, bottom_bar_analytics = _build_live_analytics(
        innings,
        batting_player_id=scoring_state.striker_id,
        bowling_player_id=scoring_state.bowler_id,
        timeout=getattr(settings, "LIVE_ANALYTICS_API_TIMEOUT", 12),
    )

    metadata = get_last_ball_metadata(innings)

    active_infographics_qs = (
        innings.live_infographic_cards
        .filter(is_active=True, is_visible=True)
        .select_related("player")
        .order_by("-created_at")[:5]
    )

    active_infographics = list(active_infographics_qs)
    active_infographic = active_infographics[0] if active_infographics else None

    active_infographics_payload = [
        {
            "id": card.id,
            "player_name": card.player.name,
            "metric_type": card.metric_type,
            "metric_label": card.get_metric_type_display(),
            "display_area": card.display_area,
            "card_data": card.card_data,
            "created_at": card.created_at.isoformat() if card.created_at else None,
        }
        for card in active_infographics
    ]

    return JsonResponse({
        "ok": True,
        "match_id": match.id,
        "innings_id": innings.id,
        "last_ball_id": metadata["last_ball_id"],
        "last_ball_label": metadata["last_ball_label"],
        "total_ball_events": metadata["total_ball_events"],
        "analytics_cards": analytics_cards,
        "bottom_bar_analytics": bottom_bar_analytics,

        # Backward compatibility: latest visible banner
        "active_infographic": active_infographics_payload[0] if active_infographics_payload else None,

        # New: multiple visible banners
        "active_infographics": active_infographics_payload,
    })


def get_last_ball_metadata(innings):
    last_ball = (
        innings.ball_events.order_by("over_number", "ball_number", "id")
        .last()
    )
    return {
        "last_ball_id": last_ball.id if last_ball else None,
        "last_ball_label": f"{last_ball.over_number}.{last_ball.ball_number}" if last_ball else None,
        "total_ball_events": innings.ball_events.count(),
    }


def _build_live_analytics(innings, batting_player_id=None, bowling_player_id=None, timeout=None):
    base_payload = build_innings_payload(innings)
    batting_form_payload = build_batting_form_payload(innings, batting_player_id)
    bowling_form_payload = build_bowling_form_payload(innings, bowling_player_id)
    recent_balls_payload = build_recent_balls_payload(innings, limit=12)
    momentum_payload = build_momentum_payload(innings, recent_overs_window=3)
    match_state_payload = build_match_state_payload(innings)

    card_specs = [
        ("Bowler Scorecard", "Student 2", api_clients.call_student2_bowler_scorecard, base_payload, _format_bowler_scorecard, "carousel"),
        ("Top Bowler", "Student 2", api_clients.call_student2_top_bowler, base_payload, _format_top_bowler, "carousel"),
        ("Bowling Form", "Student 2", api_clients.call_student2_bowling_form, bowling_form_payload, _format_bowling_form, "carousel"),
        ("Over Summary", "Student 3", api_clients.call_student3_over_summary, base_payload, _format_over_summary, "carousel"),
        ("Recent Balls", "Student 3", api_clients.call_student3_recent_balls, recent_balls_payload, _format_recent_balls, "carousel"),
        ("Momentum", "Student 3", api_clients.call_student3_momentum, momentum_payload, _format_momentum, "carousel"),
        ("Extras Summary", "Student 4", api_clients.call_student4_extras_summary, base_payload, _format_extras_summary, "carousel"),
        ("Wicket Log", "Student 4", api_clients.call_student4_wicket_log, base_payload, _format_wicket_log, "carousel"),
        ("Discipline Report", "Student 4", api_clients.call_student4_discipline_report, base_payload, _format_discipline_report, "carousel"),
        ("Match State", "Student 5", api_clients.call_student5_match_state, match_state_payload, _format_match_state, "carousel"),
        ("Required Run Rate", "Student 5", api_clients.call_student5_required_run_rate, match_state_payload, _format_required_run_rate, "carousel"),
        ("Win Probability Label", "Student 5", api_clients.call_student5_win_probability_label, match_state_payload, _format_win_probability, "carousel"),
        ("Batter Scorecard", "Student 1", api_clients.call_student1_batter_scorecard, base_payload, _format_batter_scorecard, "carousel"),
        ("Top Batter", "Student 1", api_clients.call_student1_top_batter, base_payload, _format_top_batter, "carousel"),
        ("Batting Form", "Student 1", api_clients.call_student1_batting_form, batting_form_payload, _format_batting_form, "carousel"),
        ("Match Scoreboard", "Student 1", api_clients.call_student1_match_scoreboard, base_payload, _format_match_scoreboard, "bottom"),
        ("Innings Summary", "Student 1", api_clients.call_student1_innings_summary, base_payload, _format_innings_summary, "bottom"),
    ]

    results_by_title = {}
    with ThreadPoolExecutor(max_workers=len(card_specs)) as executor:
        future_to_spec = {
            executor.submit(client, payload, timeout=timeout): (title, student, formatter, area)
            for title, student, client, payload, formatter, area in card_specs
        }
        for future in as_completed(future_to_spec):
            title, student, formatter, area = future_to_spec[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "ok": False,
                    "data": None,
                    "error": api_clients.ANALYTICS_UNAVAILABLE_MESSAGE,
                    "detail": str(exc),
                    "service": student,
                }
            results_by_title[title] = _analytics_card(title, student, result, formatter, area)

    carousel_cards = []
    bottom_cards = []
    for title, *_rest, area in card_specs:
        card = results_by_title[title]
        if area == "bottom":
            bottom_cards.append(card)
        else:
            carousel_cards.append(card)

    return carousel_cards, bottom_cards


def _analytics_card(title, student, result, formatter, area):
    ok = bool(result.get("ok"))
    data = result.get("data")
    return {
        "title": title,
        "student": student,
        "status": "ok" if ok else "error",
        "data": data,
        "error": None if ok else api_clients.ANALYTICS_UNAVAILABLE_MESSAGE,
        "lines": formatter(data) if ok else [],
        "area": area,
    }


def _nested_data(data, *keys):
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def _first_value(data, *keys, default=None):
    if not isinstance(data, dict):
        return default
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def _as_list(data, *keys):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _name(item):
    if not isinstance(item, dict):
        return str(item)
    value = _first_value(item, "name", "batter", "batter_name", "bowler", "bowler_name", "player", "player_name", default="Unknown")
    if isinstance(value, dict):
        return _name(value)
    return value


def _format_number(value):
    return "0" if value == 0 else (value if value not in (None, "") else "Unavailable")


def _compact_lines(data):
    if isinstance(data, dict):
        lines = []
        for key, value in list(data.items())[:5]:
            if isinstance(value, (dict, list)):
                continue
            lines.append(f"{key.replace('_', ' ').title()}: {_format_number(value)}")
        return lines or ["No compact analytics available"]
    if isinstance(data, list):
        return [str(item) for item in data[:5]]
    return ["No compact analytics available"]


def _format_batter_scorecard(data):
    batters = _as_list(data, "batters", "batter_scorecard", "scorecard")[:3]
    lines = []
    for batter in batters:
        runs = _first_value(batter, "runs", "total_runs", default=0)
        balls = _first_value(batter, "balls", "balls_faced", default=0)
        strike_rate = _first_value(batter, "strike_rate", "sr", default=0)
        lines.append(f"{_name(batter)}: {runs} ({balls}), SR {strike_rate}")
    return lines or _compact_lines(data)


def _format_top_batter(data):
    batter = _nested_data(data, "top_batter") or data
    if isinstance(batter, dict):
        return [
            f"Name: {_name(batter)}",
            f"Runs: {_format_number(_first_value(batter, 'runs', 'total_runs'))}",
            f"Balls: {_format_number(_first_value(batter, 'balls', 'balls_faced'))}",
            f"Strike Rate: {_format_number(_first_value(batter, 'strike_rate', 'sr'))}",
        ]
    return _compact_lines(data)


def _format_batting_form(data):
    lines = _compact_lines(data)
    return lines if lines != ["No compact analytics available"] else ["No player selected / unavailable"]


def _format_bowler_scorecard(data):
    bowlers = _as_list(data, "bowlers", "bowler_scorecard", "scorecard")[:3]
    lines = []
    for bowler in bowlers:
        overs = _first_value(bowler, "overs", default="0.0")
        wickets = _first_value(bowler, "wickets", default=0)
        economy = _first_value(bowler, "economy", "econ", default=0)
        lines.append(f"{_name(bowler)}: {overs} ov, {wickets} wk, Econ {economy}")
    return lines or _compact_lines(data)


def _format_top_bowler(data):
    bowler = _nested_data(data, "top_bowler") or data
    if isinstance(bowler, dict):
        return [
            f"Name: {_name(bowler)}",
            f"Overs: {_format_number(_first_value(bowler, 'overs'))}",
            f"Wickets: {_format_number(_first_value(bowler, 'wickets'))}",
            f"Economy: {_format_number(_first_value(bowler, 'economy', 'econ'))}",
        ]
    return _compact_lines(data)


def _format_bowling_form(data):
    lines = _compact_lines(data)
    return lines if lines != ["No compact analytics available"] else ["No player selected / unavailable"]


def _format_over_summary(data):
    overs = _as_list(data, "overs", "over_summary", "summaries")[-3:]
    lines = []

    for over in overs:
        if isinstance(over, dict):
            number = _first_value(over, "over", "over_number", default="?")
            runs = _first_value(over, "runs_in_over", "runs", "total_runs", default=0)
            wickets = _first_value(over, "wickets_in_over", "wickets", default=0)
            extras = _first_value(over, "extras_in_over", "extras", default=0)
            lines.append(f"Over {number}: {runs} runs, {wickets} wickets, {extras} extras")
        else:
            lines.append(str(over))

    return lines or _compact_lines(data)

def _format_recent_balls(data):
    balls = _as_list(data, "recent_balls", "balls")[-12:]
    lines = []
    for ball in balls:
        if isinstance(ball, dict):
            label = _first_value(ball, "label", default=None)
            if label is None:
                label = f"{_first_value(ball, 'runs', 'total_runs', 'runs_off_bat', default=0)}"
                if ball.get("wicket") or ball.get("wicket_fell"):
                    label = f"{label} W"
            over_ball = _first_value(ball, "over_ball", default=f"{ball.get('over_number', '?')}.{ball.get('ball_number', '?')}")
            lines.append(f"{over_ball}: {label}")
        else:
            lines.append(str(ball))
    return lines[-12:] or _compact_lines(data)

def _format_momentum(data):
    if isinstance(data, dict):
        return [
            f"Label: {_format_number(_first_value(data, 'momentum_label', 'label'))}",
            f"Score: {_format_number(_first_value(data, 'momentum_score'))}",
            f"Recent RR: {_format_number(_first_value(data, 'recent_run_rate', 'run_rate'))}",
            f"Recent Runs: {_format_number(_first_value(data, 'recent_runs', 'runs'))}",
            f"Recent Wickets: {_format_number(_first_value(data, 'recent_wickets', 'wickets'))}",
        ]
    return _compact_lines(data)

def _format_extras_summary(data):
    if isinstance(data, dict):
        return [
            f"Total Extras: {_format_number(_first_value(data, 'total_extras', 'extras'))}",
            f"Wides: {_format_number(_first_value(data, 'wides'))}",
            f"No Balls: {_format_number(_first_value(data, 'no_balls', 'noballs'))}",
            f"Byes: {_format_number(_first_value(data, 'byes'))}",
            f"Leg Byes: {_format_number(_first_value(data, 'leg_byes'))}",
        ]
    return _compact_lines(data)


def _format_wicket_log(data):
    wickets = _as_list(data, "wickets", "wicket_log", "dismissals")[-5:]
    lines = []
    for wicket in wickets:
        if isinstance(wicket, dict):
            player = _first_value(wicket, "dismissed_player", "player", "name", default="Wicket")
            if isinstance(player, dict):
                player = _name(player)
            over_ball = _first_value(wicket, "over_ball", default=f"{wicket.get('over_number', '?')}.{wicket.get('ball_number', '?')}")
            wicket_type = _first_value(wicket, "wicket_type", "type", default="")
            lines.append(f"{over_ball}: {player} {wicket_type}".strip())
        else:
            lines.append(str(wicket))
    return lines or _compact_lines(data)


def _format_discipline_report(data):
    if isinstance(data, dict):
        offender = _first_value(data, "worst_offender", default="None")
        if isinstance(offender, dict):
            offender = _name(offender)
        return [
            f"Score: {_format_number(_first_value(data, 'discipline_score', 'score'))}",
            f"Label: {_format_number(_first_value(data, 'label', 'discipline_label'))}",
            f"Worst Offender: {offender}",
        ]
    return _compact_lines(data)

def _format_match_state(data):
    state = _nested_data(data, "match_state") or data
    if isinstance(state, dict):
        score = _first_value(state, "score_display", "score")
        return [
            f"Score: {_format_number(score)}",
            f"Overs: {_format_number(_first_value(state, 'overs'))}",
            f"Wickets: {_format_number(_first_value(state, 'wickets'))}",
            f"Target: {_format_number(_first_value(state, 'target'))}",
            f"Chase: {_format_number(_first_value(state, 'chase_status'))}",
        ]
    return _compact_lines(data)


def _format_required_run_rate(data):
    if isinstance(data, dict):
        return [
            f"Runs Needed: {_format_number(_first_value(data, 'runs_needed'))}",
            f"Balls Remaining: {_format_number(_first_value(data, 'balls_remaining'))}",
            f"Required RR: {_format_number(_first_value(data, 'required_run_rate', 'rrr'))}",
        ]
    return _compact_lines(data)


def _format_win_probability(data):
    if isinstance(data, dict):
        return [
            f"Prediction: {_format_number(_first_value(data, 'prediction', 'label'))}",
            f"Confidence: {_format_number(_first_value(data, 'confidence_score', 'confidence'))}",
        ]
    return _compact_lines(data)


def _format_match_scoreboard(data):
    return _compact_lines(data)


def _format_innings_summary(data):
    return _compact_lines(data)

def scoreboard_api(request, match_id):
    match = get_object_or_404(
        Match.objects.select_related("team_1", "team_2"),
        pk=match_id
    )
    innings = match.innings.order_by("-innings_number").first()

    if not innings:
        return JsonResponse({
            "match": match.title,
            "status": "No innings created yet."
        })

    summary = innings_summary(innings)

    return JsonResponse({
        "match": match.title,
        "venue": match.venue,
        "stream_url": match.stream_url,
        "innings_number": innings.innings_number,
        "batting_team": innings.batting_team.name,
        "bowling_team": innings.bowling_team.name,
        "score": f"{summary['total_runs']}/{summary['wickets']}",
        "overs": summary["overs"],
        "run_rate": summary["run_rate"],
        "top_batter": summary["top_batter"],
        "top_bowler": summary["top_bowler"],
        "recent_balls": summary["recent_balls"],
        "batters": summary["batters"][:5],
        "bowlers": summary["bowlers"][:5],
    })

def bowler_momentum_proxy_api(request, innings_id, player_id):
    innings = get_object_or_404(
        Innings.objects.select_related("match", "batting_team", "bowling_team"),
        pk=innings_id
    )
    get_object_or_404(Player, pk=player_id)

    payload = build_bowler_momentum_payload(innings, player_id)

    if payload is None:
        return JsonResponse(
            {"error": "No ball events found for this bowler in this innings."},
            status=404,
        )

    try:
        result = call_bowler_momentum_api(payload)
    except requests.exceptions.Timeout:
        return JsonResponse(
            {"error": "Momentum API is waking up. Please try again in a few seconds."},
            status=504,
        )
    except requests.exceptions.RequestException as exc:
        return JsonResponse(
            {"error": "Momentum API request failed.", "detail": str(exc)},
            status=502,
        )

    return JsonResponse(result)

def get_current_batting_display(innings):
    last_ball = (
        innings.ball_events
        .select_related("striker", "non_striker")
        .order_by("over_number", "ball_number", "id")
        .last()
    )

    if not last_ball:
        return {
            "striker": None,
            "non_striker": None,
        }

    return {
        "striker": last_ball.striker,
        "non_striker": last_ball.non_striker,
    }

@require_POST
def trigger_student1_sprint2_card(request, innings_id):
    innings = get_object_or_404(Innings, pk=innings_id)
    player = get_object_or_404(Player, pk=request.POST.get("player_id"))

    metric_type = request.POST.get("metric_type", "batting_dashboard")
    display_area = request.POST.get("display_area", "between_balls")

    payload = build_student1_sprint2_payload(innings, player)

    endpoint_map = {
        "batting_dashboard": api_clients.call_student1_batting_dashboard,
        "consistency_index": api_clients.call_student1_consistency_index,
        "pressure_performance": api_clients.call_student1_pressure_performance,
        "shot_risk_efficiency": api_clients.call_student1_shot_risk_efficiency,
    }

    result = endpoint_map[metric_type](payload)

    card_data = result.get("data", {}) if result.get("ok") else {
        "error": result.get("error"),
        "detail": result.get("detail"),
    }



    LiveInfographicCard.objects.create(
        innings=innings,
        player=player,
        metric_type=metric_type,
        display_area=display_area,
        payload_sent=payload,
        api_response=result,
        card_data=card_data,
        is_active=True,
        is_visible=True,
    )

    messages.success(request, "Live infographic card triggered.")
    return redirect("innings_scoring", pk=innings.pk)

@require_POST
def hide_infographic_card(request, card_id):
    card = get_object_or_404(LiveInfographicCard, pk=card_id)
    card.is_visible = False
    card.save(update_fields=["is_visible"])
    messages.success(request, "Infographic hidden from live match.")
    return redirect("innings_scoring", pk=card.innings_id)


@require_POST
def show_infographic_card(request, card_id):
    card = get_object_or_404(LiveInfographicCard, pk=card_id)
    card.is_visible = True
    card.is_active = True
    card.save(update_fields=["is_visible", "is_active"])
    messages.success(request, "Infographic shown on live match.")
    return redirect("innings_scoring", pk=card.innings_id)


@require_POST
def remove_infographic_card(request, card_id):
    card = get_object_or_404(LiveInfographicCard, pk=card_id)
    card.is_active = False
    card.is_visible = False
    card.save(update_fields=["is_active", "is_visible"])
    messages.success(request, "Infographic removed from live match.")
    return redirect("innings_scoring", pk=card.innings_id)