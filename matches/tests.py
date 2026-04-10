from django.test import TestCase

from .forms import BallEventForm
from .models import BallEvent, Innings, Match, Player, Team
from .scoring import get_scoring_state


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

    def test_legal_delivery_advances_ball_and_preserves_players(self):
        self._ball()

        state = get_scoring_state(self.innings)

        self.assertEqual((state.over_number, state.ball_number), (1, 2))
        self.assertEqual(state.striker_id, self.a1.id)
        self.assertEqual(state.non_striker_id, self.a2.id)
        self.assertEqual(state.bowler_id, self.b1.id)
        self.assertFalse(state.requires_new_bowler)

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
