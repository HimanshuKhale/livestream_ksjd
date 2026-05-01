import requests
from django.conf import settings

ANALYTICS_UNAVAILABLE_MESSAGE = "Analytics temporarily unavailable"


def call_external_analytics_api(base_url, endpoint, payload, service_name, timeout=None):
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    request_timeout = timeout if timeout is not None else getattr(settings, "EXTERNAL_ANALYTICS_API_TIMEOUT", 90)

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=request_timeout,
        )
        response.raise_for_status()
        return {
            "ok": True,
            "data": response.json(),
            "error": None,
            "service": service_name,
        }
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "error": ANALYTICS_UNAVAILABLE_MESSAGE,
            "detail": str(exc),
            "service": service_name,
        }


def call_bowler_momentum_api(payload):
    response = requests.post(
        settings.BOWLER_MOMENTUM_API_URL,
        json=payload,
        timeout=getattr(settings, "BOWLER_MOMENTUM_API_TIMEOUT", 70),
    )
    response.raise_for_status()
    return response.json()


def call_student1_match_scoreboard(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT1_API_BASE_URL, "/student1/match-scoreboard", payload, "Student 1", timeout=timeout)


def call_student1_innings_summary(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT1_API_BASE_URL, "/student1/innings-summary", payload, "Student 1", timeout=timeout)


def call_student1_batter_scorecard(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT1_API_BASE_URL, "/student1/batter-scorecard", payload, "Student 1", timeout=timeout)


def call_student1_top_batter(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT1_API_BASE_URL, "/student1/top-batter", payload, "Student 1", timeout=timeout)


def call_student1_batting_form(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT1_API_BASE_URL, "/student1/batting-form", payload, "Student 1", timeout=timeout)


def call_student2_bowler_scorecard(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT2_API_BASE_URL, "/student2/bowler-scorecard", payload, "Student 2", timeout=timeout)


def call_student2_top_bowler(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT2_API_BASE_URL, "/student2/top-bowler", payload, "Student 2", timeout=timeout)


def call_student2_bowling_form(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT2_API_BASE_URL, "/student2/bowling-form", payload, "Student 2", timeout=timeout)


def call_student3_over_summary(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT3_API_BASE_URL, "/student3/over-summary", payload, "Student 3", timeout=timeout)


def call_student3_recent_balls(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT3_API_BASE_URL, "/student3/recent-balls", payload, "Student 3", timeout=timeout)


def call_student3_momentum(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT3_API_BASE_URL, "/student3/momentum", payload, "Student 3", timeout=timeout)


def call_student4_extras_summary(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT4_API_BASE_URL, "/student4/extras-summary", payload, "Student 4", timeout=timeout)


def call_student4_wicket_log(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT4_API_BASE_URL, "/student4/wicket-log", payload, "Student 4", timeout=timeout)


def call_student4_discipline_report(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT4_API_BASE_URL, "/student4/discipline-report", payload, "Student 4", timeout=timeout)


def call_student5_match_state(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT5_API_BASE_URL, "/student5/match-state", payload, "Student 5", timeout=timeout)


def call_student5_required_run_rate(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT5_API_BASE_URL, "/student5/required-run-rate", payload, "Student 5", timeout=timeout)


def call_student5_win_probability_label(payload, timeout=None):
    return call_external_analytics_api(settings.STUDENT5_API_BASE_URL, "/student5/win-probability-label", payload, "Student 5", timeout=timeout)


def call_student1_sprint2_api(endpoint, payload, timeout=None):
    return call_external_analytics_api(
        settings.STUDENT1_SPRINT2_API_BASE_URL,
        endpoint,
        payload,
        "Student 1 Sprint 2",
        timeout=timeout,
    )


def call_student1_batting_dashboard(payload, timeout=None):
    return call_student1_sprint2_api(
        "/api/v1/cards/batting-dashboard",
        payload,
        timeout=timeout,
    )


def call_student1_consistency_index(payload, timeout=None):
    return call_student1_sprint2_api(
        "/api/v1/batting/consistency-index",
        payload,
        timeout=timeout,
    )


def call_student1_pressure_performance(payload, timeout=None):
    return call_student1_sprint2_api(
        "/api/v1/batting/pressure-performance",
        payload,
        timeout=timeout,
    )


def call_student1_shot_risk_efficiency(payload, timeout=None):
    return call_student1_sprint2_api(
        "/api/v1/batting/shot-risk-efficiency",
        payload,
        timeout=timeout,
    )


def _post_json(url, payload, timeout=90):
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def call_student2_bowling_economy_deviation(payload):
    url = f"{settings.STUDENT2_SPRINT2_API_BASE_URL}/student2/bowling-economy-deviation"
    return _post_json(
        url,
        payload,
        timeout=getattr(settings, "STUDENT2_SPRINT2_API_TIMEOUT", 90),
    )


def call_student2_wicket_probability_model(payload):
    url = f"{settings.STUDENT2_SPRINT2_API_BASE_URL}/student2/wicket-probability-model"
    return _post_json(
        url,
        payload,
        timeout=getattr(settings, "STUDENT2_SPRINT2_API_TIMEOUT", 90),
    )


def call_student2_control_entropy_model(payload):
    url = f"{settings.STUDENT2_SPRINT2_API_BASE_URL}/student2/control-entropy-model"
    return _post_json(
        url,
        payload,
        timeout=getattr(settings, "STUDENT2_SPRINT2_API_TIMEOUT", 90),
    )


def call_student2_full_bowling_analysis(payload):
    url = f"{settings.STUDENT2_SPRINT2_API_BASE_URL}/student2/full-bowling-analysis"
    return _post_json(
        url,
        payload,
        timeout=getattr(settings, "STUDENT2_SPRINT2_API_TIMEOUT", 90),
    )