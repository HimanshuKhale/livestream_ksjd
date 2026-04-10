from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BallEventForm, InningsForm, MatchForm
from .models import Innings, Match
from .scoring import get_scoring_state
from .services import innings_summary


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
    events = innings.ball_events.select_related("striker", "non_striker", "bowler").order_by("-id")[:12]
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

    return render(
        request,
        "matches/innings_scoring.html",
        {
            "innings": innings,
            "form": form,
            "scoring_state": scoring_state,
            "next_ball_context": next_ball_context,
            "summary": summary,
            "events": events,
            "suggested_batters": suggested_batters,
        },
    )


def live_match(request, match_id):
    match = get_object_or_404(
        Match.objects.select_related("team_1", "team_2"),
        pk=match_id
    )
    innings = match.innings.order_by("-innings_number").first()

    return render(
        request,
        "matches/live_match.html",
        {
            "match": match,
            "innings": innings,
        },
    )


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
