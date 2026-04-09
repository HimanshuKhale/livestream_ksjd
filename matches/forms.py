from django import forms
from .models import BallEvent, Innings, Match


def apply_form_control_styles(fields):
    for field in fields.values():
        css = (
            "w-full rounded-xl border border-slate-300 bg-white "
            "px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 "
            "focus:border-emerald-500 focus:outline-none"
        )
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs.update({"class": "h-4 w-4 rounded border-slate-300"})
        else:
            field.widget.attrs.update({"class": css})


class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = [
            "title",
            "tournament_name",
            "venue",
            "match_date",
            "team_1",
            "team_2",
            "toss_winner",
            "toss_decision",
            "status",
            "stream_url",
        ]
        widgets = {
            "match_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_control_styles(self.fields)


class InningsForm(forms.ModelForm):
    class Meta:
        model = Innings
        fields = [
            "match",
            "innings_number",
            "batting_team",
            "bowling_team",
            "total_overs_limit",
            "is_complete",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_control_styles(self.fields)


class BallEventForm(forms.ModelForm):
    class Meta:
        model = BallEvent
        fields = [
            "over_number",
            "ball_number",
            "striker",
            "non_striker",
            "bowler",
            "runs_off_bat",
            "extras",
            "extra_type",
            "is_legal_delivery",
            "wicket_fell",
            "wicket_type",
            "dismissed_player",
            "fielder_name",
            "shot_type",
            "shot_zone",
            "notes",
        ]

    def __init__(self, *args, innings=None, **kwargs):
        super().__init__(*args, **kwargs)

        if innings is not None:
            batting_qs = innings.batting_team.players.all().order_by("name")
            bowling_qs = innings.bowling_team.players.all().order_by("name")

            self.fields["striker"].queryset = batting_qs
            self.fields["non_striker"].queryset = batting_qs
            self.fields["dismissed_player"].queryset = batting_qs
            self.fields["bowler"].queryset = bowling_qs

        apply_form_control_styles(self.fields)