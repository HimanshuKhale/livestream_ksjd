from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("matches/new/", views.match_create, name="match_create"),
    path("innings/new/", views.innings_create, name="innings_create"),
    path("matches/<int:pk>/", views.match_detail, name="match_detail"),
    path("innings/<int:pk>/scoring/", views.innings_scoring, name="innings_scoring"),
    path("live/<int:match_id>/", views.live_match, name="live_match"),
    path("api/live/<int:match_id>/analytics/", views.live_analytics_api, name="live_analytics_api"),
    path("api/matches/<int:match_id>/scoreboard/", views.scoreboard_api, name="scoreboard_api"),
    path(
    "api/innings/<int:innings_id>/bowler/<int:player_id>/momentum-proxy/",
    views.bowler_momentum_proxy_api,
    name="bowler_momentum_proxy_api",
    ),

    path(
    "innings/<int:innings_id>/trigger-student1-card/",
    views.trigger_student1_sprint2_card,
    name="trigger_student1_sprint2_card",
    ),
    path(
    "infographic/<int:card_id>/hide/",
    views.hide_infographic_card,
    name="hide_infographic_card",
    ),
    path(
        "infographic/<int:card_id>/show/",
        views.show_infographic_card,
        name="show_infographic_card",
    ),
    path(
        "infographic/<int:card_id>/remove/",
        views.remove_infographic_card,
        name="remove_infographic_card",
    ),
    path(
    "api/agent/<int:match_id>/",
    views.khel_ai_agent_api,
    name="khel_ai_agent_api",
    ),
]
