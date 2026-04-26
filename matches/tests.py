from unittest.mock import patch

import requests
from django.test import TestCase
from django.urls import reverse

from .analytics_payloads import build_innings_payload, player_ref
from .api_clients import ANALYTICS_UNAVAILABLE_MESSAGE, call_external_analytics_api
from .forms import BallEventForm
from .models import BallEvent, Innings, Match, Player, Team
from .scoring import get_scoring_state
from .views import _build_live_analytics


class ScoringStateEngineTests(TestCase):
    def setUp(self):
        self.team_a = Team.objects.create(name="Alpha", short_name="ALP")
        self.team_b = Team.objects.create(name="Bravo", short_name="BRV")

        self.a1 = Player.objects.create(team=self.team_a, name="A One")
        self.a2 = Player.objects.create(team=self.team_a, name="A Two")
        self.a3 = Player.objects.create(team=self.team_a, name="A Three")
        self.a4 = Player.objects.create(team=self.team_a, name="A Four")

        self.b1 = Player.objects.create(team=self.team_b, name="B One")
        self.b2 = Player.objects.create(team=self.team_b, name="B Two")

        self.match = Match.objects.create(
            title="Alpha vs Bravo",
            team_1=self.team_a,
            team_2=self.team_b,
        )
        self.innings = Innings.objects.create(
            match=self.match,
            innings_number=1,
            batting_team=self.team_a,
            bowling_team=self.team_b,
            total_overs_limit=20,
        )

    def _ball(self, **overrides):
        payload = {
            "innings": self.innings,
            "over_number": 1,
            "ball_number": 1,
            "striker": self.a1,
            "non_striker": self.a2,
            "bowler": self.b1,
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
        payload.update(overrides)
        return BallEvent.objects.create(**payload)

    def test_first_ball_defaults_when_innings_is_empty(self):
        state = get_scoring_state(self.innings)

        self.assertTrue(state.innings_is_empty)
        self.assertEqual(state.over_number, 1)
        self.assertEqual(state.ball_number, 1)
        self.assertIsNone(state.striker_id)
        self.assertIsNone(state.non_striker_id)
        self.assertIsNone(state.bowler_id)
        self.assertFalse(state.requires_new_bowler)
        self.assertEqual(state.suggested_next_batter_ids, [self.a4.id, self.a1.id, self.a3.id, self.a2.id])

    def test_scoring_page_preloads_first_ball_defaults(self):
        response = self.client.get(reverse("innings_scoring", args=[self.innings.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["over_number"], 1)
        self.assertEqual(response.context["form"].initial["ball_number"], 1)
        self.assertEqual(response.context["form"].initial["runs_off_bat"], 0)
        self.assertEqual(response.context["form"].initial["wicket_fell"], False)
        self.assertEqual(response.context["next_ball_context"]["over_number"], 1)
        self.assertEqual(response.context["next_ball_context"]["ball_number"], 1)

    def test_legal_delivery_advances_ball_and_preserves_players(self):
        self._ball()

        state = get_scoring_state(self.innings)

        self.assertEqual((state.over_number, state.ball_number), (1, 2))
        self.assertEqual(state.striker_id, self.a1.id)
        self.assertEqual(state.non_striker_id, self.a2.id)
        self.assertEqual(state.bowler_id, self.b1.id)
        self.assertFalse(state.requires_new_bowler)

    def test_next_ball_initial_resets_event_specific_fields(self):
        self._ball(
            over_number=1,
            ball_number=3,
            runs_off_bat=4,
            extras=1,
            extra_type="bye",
            wicket_fell=True,
            wicket_type="caught",
            dismissed_player=self.a1,
            fielder_name="Point",
            shot_type="cut",
            shot_zone="off-side",
            notes="Edged behind point.",
        )

        state = get_scoring_state(self.innings)
        initial = state.as_form_initial()

        self.assertEqual((initial["over_number"], initial["ball_number"]), (1, 4))
        self.assertEqual(initial["runs_off_bat"], 0)
        self.assertEqual(initial["extras"], 0)
        self.assertEqual(initial["extra_type"], "")
        self.assertTrue(initial["is_legal_delivery"])
        self.assertFalse(initial["wicket_fell"])
        self.assertEqual(initial["wicket_type"], "")
        self.assertIsNone(initial["dismissed_player"])
        self.assertEqual(initial["fielder_name"], "")
        self.assertEqual(initial["shot_type"], "")
        self.assertEqual(initial["shot_zone"], "")
        self.assertEqual(initial["notes"], "")

    def test_odd_runs_swap_strike(self):
        self._ball(runs_off_bat=1)

        state = get_scoring_state(self.innings)

        self.assertEqual((state.over_number, state.ball_number), (1, 2))
        self.assertEqual(state.striker_id, self.a2.id)
        self.assertEqual(state.non_striker_id, self.a1.id)

    def test_over_end_swaps_strike_and_requires_new_bowler(self):
        self._ball(over_number=1, ball_number=6, striker=self.a1, non_striker=self.a2, bowler=self.b1)

        state = get_scoring_state(self.innings)

        self.assertEqual((state.over_number, state.ball_number), (2, 1))
        self.assertEqual(state.striker_id, self.a2.id)
        self.assertEqual(state.non_striker_id, self.a1.id)
        self.assertIsNone(state.bowler_id)
        self.assertTrue(state.requires_new_bowler)

    def test_non_legal_wide_does_not_increment_ball_number(self):
        self._ball(extra_type="wide", extras=1, is_legal_delivery=False)

        state = get_scoring_state(self.innings)

        self.assertEqual((state.over_number, state.ball_number), (1, 1))
        self.assertEqual(state.striker_id, self.a1.id)
        self.assertEqual(state.non_striker_id, self.a2.id)
        self.assertEqual(state.bowler_id, self.b1.id)
        self.assertFalse(state.requires_new_bowler)

    def test_wicket_clears_dismissed_batter_slot_and_suggests_next_batter(self):
        self._ball(
            wicket_fell=True,
            wicket_type="bowled",
            dismissed_player=self.a1,
        )

        state = get_scoring_state(self.innings)

        self.assertIsNone(state.striker_id)
        self.assertEqual(state.non_striker_id, self.a2.id)
        self.assertEqual(state.suggested_next_batter_ids, [self.a4.id, self.a3.id])

    def test_wicket_without_dismissed_player_still_excludes_inferred_out_batter(self):
        self._ball(
            wicket_fell=True,
            wicket_type="bowled",
        )

        state = get_scoring_state(self.innings)

        self.assertIsNone(state.striker_id)
        self.assertEqual(state.non_striker_id, self.a2.id)
        self.assertEqual(state.suggested_next_batter_ids, [self.a4.id, self.a3.id])

    def test_form_forces_wides_and_no_balls_to_be_non_legal(self):
        form = BallEventForm(
            data={
                "over_number": 1,
                "ball_number": 1,
                "striker": self.a1.id,
                "non_striker": self.a2.id,
                "bowler": self.b1.id,
                "runs_off_bat": 0,
                "extras": 1,
                "extra_type": "wide",
                "is_legal_delivery": True,
                "wicket_fell": False,
                "wicket_type": "",
                "dismissed_player": "",
                "fielder_name": "",
                "shot_type": "",
                "shot_zone": "",
                "notes": "",
            },
            innings=self.innings,
        )

        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data["is_legal_delivery"])

    def test_form_keeps_manual_override_fields_editable(self):
        self._ball(over_number=1, ball_number=1)

        form = BallEventForm(
            data={
                "over_number": 4,
                "ball_number": 5,
                "striker": self.a2.id,
                "non_striker": self.a3.id,
                "bowler": self.b2.id,
                "runs_off_bat": 2,
                "extras": 0,
                "extra_type": "",
                "is_legal_delivery": True,
                "wicket_fell": False,
                "wicket_type": "",
                "dismissed_player": "",
                "fielder_name": "",
                "shot_type": "drive",
                "shot_zone": "mid-off",
                "notes": "Manual override",
            },
            innings=self.innings,
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["over_number"], 4)
        self.assertEqual(form.cleaned_data["ball_number"], 5)
        self.assertEqual(form.cleaned_data["striker"], self.a2)
        self.assertEqual(form.cleaned_data["non_striker"], self.a3)
        self.assertEqual(form.cleaned_data["bowler"], self.b2)


class AnalyticsIntegrationTests(TestCase):
    def setUp(self):
        self.team_a = Team.objects.create(name="Alpha", short_name="ALP")
        self.team_b = Team.objects.create(name="Bravo", short_name="BRV")
        self.a1 = Player.objects.create(team=self.team_a, name="A One")
        self.a2 = Player.objects.create(team=self.team_a, name="A Two")
        self.b1 = Player.objects.create(team=self.team_b, name="B One")
        self.b2 = Player.objects.create(team=self.team_b, name="B Two")
        self.match = Match.objects.create(
            title="Alpha vs Bravo",
            venue="Main Ground",
            team_1=self.team_a,
            team_2=self.team_b,
        )
        self.innings = Innings.objects.create(
            match=self.match,
            innings_number=1,
            batting_team=self.team_a,
            bowling_team=self.team_b,
            total_overs_limit=20,
        )

    def _ball(self, innings=None, **overrides):
        payload = {
            "innings": innings or self.innings,
            "over_number": 1,
            "ball_number": 1,
            "striker": self.a1,
            "non_striker": self.a2,
            "bowler": self.b1,
            "runs_off_bat": 4,
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
        payload.update(overrides)
        return BallEvent.objects.create(**payload)

    def test_player_ref_handles_none(self):
        self.assertIsNone(player_ref(None))
        self.assertEqual(player_ref(self.a1), {"id": self.a1.id, "name": "A One"})

    def test_build_innings_payload_returns_expected_shape(self):
        self._ball(extras=1, extra_type="wide", is_legal_delivery=False)

        payload = build_innings_payload(self.innings)

        self.assertEqual(payload["match"]["id"], self.match.id)
        self.assertEqual(payload["match"]["title"], "Alpha vs Bravo")
        self.assertEqual(payload["match"]["venue"], "Main Ground")
        self.assertEqual(payload["innings"]["batting_team"], "Alpha")
        self.assertEqual(payload["innings"]["bowling_team"], "Bravo")
        self.assertEqual(payload["innings"]["target"], None)
        self.assertEqual(len(payload["balls"]), 1)
        ball = payload["balls"][0]
        self.assertEqual(ball["striker"], {"id": self.a1.id, "name": "A One"})
        self.assertEqual(ball["non_striker"], {"id": self.a2.id, "name": "A Two"})
        self.assertEqual(ball["bowler"], {"id": self.b1.id, "name": "B One"})
        self.assertEqual(ball["runs_off_bat"], 4)
        self.assertEqual(ball["extras"], 1)
        self.assertEqual(ball["extra_type"], "wide")
        self.assertFalse(ball["is_legal_delivery"])

    def test_second_innings_target_uses_first_innings_total_plus_one(self):
        self._ball(runs_off_bat=6)
        self._ball(over_number=1, ball_number=2, runs_off_bat=2, extras=1)
        second_innings = Innings.objects.create(
            match=self.match,
            innings_number=2,
            batting_team=self.team_b,
            bowling_team=self.team_a,
            total_overs_limit=20,
        )

        payload = build_innings_payload(second_innings)

        self.assertEqual(payload["match"]["target"], 10)
        self.assertEqual(payload["innings"]["target"], 10)

    @patch("matches.api_clients.requests.post")
    def test_external_api_client_handles_timeout_without_raising(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("service asleep")

        result = call_external_analytics_api(
            "https://example.test",
            "/student/test",
            {"hello": "world"},
            "Student X",
        )

        self.assertFalse(result["ok"])
        self.assertIsNone(result["data"])
        self.assertEqual(result["error"], ANALYTICS_UNAVAILABLE_MESSAGE)
        self.assertEqual(result["service"], "Student X")

    @patch("matches.api_clients.requests.post")
    def test_external_api_client_respects_custom_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("service asleep")

        call_external_analytics_api(
            "https://example.test",
            "/student/test",
            {"hello": "world"},
            "Student X",
            timeout=3,
        )

        self.assertEqual(mock_post.call_args.kwargs["timeout"], 3)

    @patch("matches.api_clients.requests.post")
    def test_live_match_loads_when_external_analytics_fail(self, mock_post):
        self._ball()
        mock_post.side_effect = requests.exceptions.RequestException("down")

        response = self.client.get(reverse("live_match", args=[self.match.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("analytics_cards", response.context)
        self.assertIn("bottom_bar_analytics", response.context)
        self.assertTrue(response.context["analytics_cards"])
        self.assertTrue(response.context["bottom_bar_analytics"])
        self.assertContains(response, ANALYTICS_UNAVAILABLE_MESSAGE)

    @patch("matches.api_clients.requests.post")
    def test_live_analytics_endpoint_returns_200(self, mock_post):
        self._ball()
        mock_post.side_effect = requests.exceptions.RequestException("down")

        response = self.client.get(reverse("live_analytics_api", args=[self.match.pk]))
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["match_id"], self.match.id)
        self.assertEqual(data["innings_id"], self.innings.id)
        self.assertTrue(data["analytics_cards"])
        self.assertTrue(data["bottom_bar_analytics"])

    def test_live_analytics_endpoint_with_no_innings_returns_safe_json(self):
        match = Match.objects.create(
            title="No Innings Match",
            team_1=self.team_a,
            team_2=self.team_b,
        )

        response = self.client.get(reverse("live_analytics_api", args=[match.pk]))
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertIsNone(data["innings_id"])
        self.assertIsNone(data["last_ball_id"])
        self.assertEqual(data["analytics_cards"], [])
        self.assertEqual(data["bottom_bar_analytics"], [])
        self.assertEqual(data["message"], "No innings available yet.")

    @patch("matches.api_clients.requests.post")
    def test_live_analytics_latest_ball_id_changes_after_new_ball(self, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException("down")
        first_ball = self._ball(over_number=1, ball_number=1)

        first_response = self.client.get(reverse("live_analytics_api", args=[self.match.pk]))
        self._ball(over_number=1, ball_number=2)
        second_response = self.client.get(reverse("live_analytics_api", args=[self.match.pk]))

        first_data = first_response.json()
        second_data = second_response.json()
        self.assertEqual(first_data["last_ball_id"], first_ball.id)
        self.assertNotEqual(first_data["last_ball_id"], second_data["last_ball_id"])
        self.assertEqual(second_data["last_ball_label"], "1.2")
        self.assertEqual(second_data["total_ball_events"], 2)

    @patch("matches.api_clients.requests.post")
    def test_live_analytics_api_failure_returns_error_cards_with_200(self, mock_post):
        self._ball()
        mock_post.side_effect = requests.exceptions.RequestException("down")

        response = self.client.get(reverse("live_analytics_api", args=[self.match.pk]))
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["analytics_cards"][0]["status"], "error")
        self.assertEqual(data["analytics_cards"][0]["error"], ANALYTICS_UNAVAILABLE_MESSAGE)

    @patch("matches.api_clients.requests.post")
    def test_build_live_analytics_accepts_timeout(self, mock_post):
        self._ball()
        mock_post.side_effect = requests.exceptions.RequestException("down")

        analytics_cards, bottom_bar_analytics = _build_live_analytics(
            self.innings,
            batting_player_id=self.a1.id,
            bowling_player_id=self.b1.id,
            timeout=4,
        )

        self.assertTrue(analytics_cards)
        self.assertTrue(bottom_bar_analytics)
        self.assertTrue(mock_post.call_args_list)
        self.assertTrue(all(call.kwargs["timeout"] == 4 for call in mock_post.call_args_list))
