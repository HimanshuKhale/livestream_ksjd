from django.db import models
from django.urls import reverse


class Team(models.Model):
    name = models.CharField(max_length=120, unique=True)
    short_name = models.CharField(max_length=12, blank=True)

    def __str__(self):
        return self.name


class Player(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="players")
    name = models.CharField(max_length=120)
    jersey_number = models.PositiveIntegerField(null=True, blank=True)
    batting_hand = models.CharField(max_length=20, blank=True)
    bowling_style = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ("team", "name")
        ordering = ["team__name", "name"]

    def __str__(self):
        return f"{self.name} ({self.team.short_name or self.team.name})"


class Match(models.Model):
    title = models.CharField(max_length=200)
    tournament_name = models.CharField(max_length=200, blank=True)
    venue = models.CharField(max_length=200, blank=True)
    match_date = models.DateField(null=True, blank=True)

    team_1 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="home_matches")
    team_2 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="away_matches")

    toss_winner = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="toss_wins"
    )
    toss_decision = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=30, default="live")
    stream_url = models.URLField(blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("match_detail", args=[self.pk])


class Innings(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="innings")
    innings_number = models.PositiveSmallIntegerField()
    batting_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="batting_innings")
    bowling_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="bowling_innings")
    total_overs_limit = models.PositiveSmallIntegerField(default=20)
    is_complete = models.BooleanField(default=False)

    class Meta:
        unique_together = ("match", "innings_number")
        ordering = ["innings_number"]

    def __str__(self):
        return f"{self.match.title} - Innings {self.innings_number}"

    def get_absolute_url(self):
        return reverse("innings_scoring", args=[self.pk])


class BallEvent(models.Model):
    EXTRA_CHOICES = [
        ("", "None"),
        ("wide", "Wide"),
        ("no_ball", "No Ball"),
        ("bye", "Bye"),
        ("leg_bye", "Leg Bye"),
        ("penalty", "Penalty"),
    ]

    WICKET_CHOICES = [
        ("", "None"),
        ("bowled", "Bowled"),
        ("caught", "Caught"),
        ("lbw", "LBW"),
        ("run_out", "Run Out"),
        ("stumped", "Stumped"),
        ("hit_wicket", "Hit Wicket"),
        ("retired_out", "Retired Out"),
    ]

    SHOT_CHOICES = [
        ("", "Unknown"),
        ("defence", "Defence"),
        ("leave", "Leave"),
        ("drive", "Drive"),
        ("cover_drive", "Cover Drive"),
        ("straight_drive", "Straight Drive"),
        ("on_drive", "On Drive"),
        ("lofted_drive", "Lofted Drive"),
        ("cut", "Cut"),
        ("late_cut", "Late Cut"),
        ("square_cut", "Square Cut"),
        ("pull", "Pull"),
        ("hook", "Hook"),
        ("sweep", "Sweep"),
        ("reverse_sweep", "Reverse Sweep"),
        ("paddle_sweep", "Paddle Sweep"),
        ("glance", "Glance"),
        ("flick", "Flick"),
        ("clip", "Clip"),
        ("lofted", "Lofted Shot"),
        ("slog", "Slog"),
        ("switch_hit", "Switch Hit"),
        ("ramp", "Ramp"),
        ("upper_cut", "Upper Cut"),
        ("scoop", "Scoop"),
    ]
    SHOT_ZONE_CHOICES = [
        ("", "Unknown"),

        # Outside 30-yard circle
        ("long_off", "Long Off"),
        ("deep_cover", "Deep Cover"),
        ("third_point", "Third Point"),
        ("fine_leg", "Fine Leg"),
        ("long_on", "Long On"),
        ("deep_square_leg", "Deep Square Leg"),
        ("mid_on_area", "Mid On Area"),
        ("deep_extra_cover", "Deep Extra Cover"),

        # Inside 30-yard circle
        ("straight_inside", "Straight (Inside)"),
        ("mid_off", "Mid Off"),
        ("cover_inside", "Cover (Inside)"),
        ("point_inside", "Point (Inside)"),
        ("fine_leg_inside", "Fine Leg (Inside)"),
        ("square_leg_inside", "Square Leg (Inside)"),
        ("mid_on_inside", "Mid On (Inside)"),
        ("cover_point_inside", "Cover Point (Inside)"),

        # Close-in fielders (advanced)
        ("short_leg", "Short Leg"),
        ("silly_point", "Silly Point"),
        ("silly_mid_on", "Silly Mid On"),
        ("silly_mid_wicket", "Silly Mid Wicket"),
    ]
    innings = models.ForeignKey(Innings, on_delete=models.CASCADE, related_name="ball_events")
    over_number = models.PositiveSmallIntegerField()
    ball_number = models.PositiveSmallIntegerField(help_text="Use 1-6 for legal ball slot in the over.")

    striker = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="balls_faced_as_striker")
    non_striker = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="balls_faced_as_non_striker")
    bowler = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="balls_bowled")

    runs_off_bat = models.PositiveSmallIntegerField(default=0)
    extras = models.PositiveSmallIntegerField(default=0)
    extra_type = models.CharField(max_length=20, choices=EXTRA_CHOICES, blank=True)

    is_legal_delivery = models.BooleanField(default=True)

    wicket_fell = models.BooleanField(default=False)
    wicket_type = models.CharField(max_length=20, choices=WICKET_CHOICES, blank=True)
    dismissed_player = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dismissals"
    )
    fielder_name = models.CharField(max_length=120, blank=True)

    shot_type = models.CharField(max_length=20, choices=SHOT_CHOICES, blank=True)
    shot_zone = models.CharField(max_length=50, choices=SHOT_ZONE_CHOICES, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["over_number", "ball_number", "id"]

    def __str__(self):
        return f"Innings {self.innings_id} - {self.over_number}.{self.ball_number}"

    @property
    def total_runs(self):
        return self.runs_off_bat + self.extras