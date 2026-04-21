import requests
from django.conf import settings


def call_bowler_momentum_api(payload):
    response = requests.post(
        settings.BOWLER_MOMENTUM_API_URL,
        json=payload,
        timeout=getattr(settings, "BOWLER_MOMENTUM_API_TIMEOUT", 70),
    )
    response.raise_for_status()
    return response.json()