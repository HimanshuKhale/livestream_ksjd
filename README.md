# Khel.ai MVP

Same-day Django MVP for:
- match setup
- innings setup
- ball-by-ball scoring
- public live scoreboard
- JSON analytics endpoint

## Setup

python -m venv .venv

### Windows
.venv\Scripts\activate

### macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

## Demo flow

1. Create teams in Django admin
2. Create players in Django admin
3. Create a match
4. Create an innings
5. Enter ball events
6. Open the public live page in another tab