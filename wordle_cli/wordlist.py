import json
import random
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

CACHE_DIR = Path.home() / ".cache" / "wordle_cli"
CACHE_FILE = CACHE_DIR / "wordle_cache.json"
WORDLE_LAUNCH = date(2021, 6, 19)  # first-ever Wordle date

GUESSES_URL = "https://raw.githubusercontent.com/tabatkins/wordle-list/main/words"
GUESSES_CACHE = CACHE_DIR / "guesses.json"

# used only if NYT and the cache are both unreachable
FALLBACK_WORDS = [
    "about", "above", "abuse", "actor", "acute", "admit", "adopt", "adult", "after",
    "again", "agent", "agree", "ahead", "alarm", "album", "alert", "alike", "alive",
    "allow", "alone", "along", "alter", "among", "anger", "angle", "angry", "apart",
    "apple", "apply", "arena", "argue", "arise", "armor", "aside", "asset", "audio",
    "audit", "avoid", "awake", "award", "aware", "badly", "baker", "bases", "basic",
    "beach", "began", "begin", "being", "below", "bench", "birth", "black", "blame",
    "blank", "blast", "blind", "block", "blood", "board", "boost", "booth", "bound",
    "brain", "brand", "brave", "bread", "break", "breed", "brief", "bring", "broad",
]

_cache = None


def _load_cache() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if CACHE_FILE.exists():
        try:
            _cache = json.loads(CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            _cache = {}
    else:
        _cache = {}
    return _cache


def _save_cache():
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(_cache))
    except OSError:
        pass


def get_daily_word(target_date: str = None) -> str:
    """Fetch the official Wordle solution for a given date (YYYY-MM-DD)."""
    target_date = target_date or date.today().isoformat()

    cache = _load_cache()
    if target_date in cache:
        return cache[target_date]

    url = f"https://www.nytimes.com/svc/wordle/v2/{target_date}.json"
    req = Request(url, headers={"User-Agent": "wordle-cli"})
    with urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    solution = data["solution"]

    cache[target_date] = solution
    _save_cache()
    return solution


def get_random_word() -> str:
    """Pick a random past Wordle solution by hitting NYT's API with a random date."""
    days_since_launch = (date.today() - WORDLE_LAUNCH).days
    random_offset = random.randint(0, days_since_launch)
    random_date = (WORDLE_LAUNCH + timedelta(days=random_offset)).isoformat()
    return get_daily_word(random_date)


def get_answers() -> list:
    """
    Provide a random Wordle answer via the NYT API, wrapped in a list so
    game.py can keep doing random.choice(get_answers()) as before.
    Falls back to a small local list if NYT is unreachable.
    """
    try:
        return [get_random_word()]
    except (URLError, HTTPError, TimeoutError, KeyError, OSError):
        print("fallbacked")
        return [random.choice(FALLBACK_WORDS)]


def get_valid_guesses() -> set:
    """Full allowed-guess list, used only to validate what the player types."""
    if GUESSES_CACHE.exists():
        try:
            words = json.loads(GUESSES_CACHE.read_text())
            return set(words)
        except (json.JSONDecodeError, OSError):
            pass

    try:
        req = Request(GUESSES_URL, headers={"User-Agent": "wordle-cli"})
        with urlopen(req, timeout=5) as resp:
            text = resp.read().decode("utf-8")
        words = [w.strip().lower() for w in text.splitlines() if len(w.strip()) == 5]
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            GUESSES_CACHE.write_text(json.dumps(words))
        except OSError:
            pass
        return set(words) | set(FALLBACK_WORDS)
    except (URLError, HTTPError, TimeoutError, OSError):
        print("fallbacked")
        return set(FALLBACK_WORDS)
