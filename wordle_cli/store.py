"""Persistent player data: stats per mode, saved games, campaign progress."""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "wordle_cli"
STATS_FILE = CACHE_DIR / "stats.json"

MODES = ("daily", "random", "campaign")
MAX_TRIES = 6


def _new_mode_stats() -> dict:
    return {"played": 0, "won": 0, "streak": 0, "max_streak": 0,
            "dist": [0] * MAX_TRIES, "last": None, "last_date": None}


class Store:
    def __init__(self):
        self.data = self._load()

    @staticmethod
    def _load() -> dict:
        data = {}
        if STATS_FILE.exists():
            try:
                data = json.loads(STATS_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                data = {}
        # keys from the original version are kept as-is
        data.setdefault("total_correct", 0)
        data.setdefault("words", [])
        data.setdefault("settings", {}).setdefault("hard", False)
        modes = data.setdefault("modes", {})
        for mode in MODES:
            stats = modes.setdefault(mode, _new_mode_stats())
            for key, value in _new_mode_stats().items():
                stats.setdefault(key, value)
        data.setdefault("daily", {})          # "YYYY-MM-DD" -> finished game
        data.setdefault("campaign", {}).setdefault("next", 0)
        data["campaign"].setdefault("results", {})  # "day index" -> finished game
        data.setdefault("in_progress", {})    # game key -> {"answer", "guesses"}
        data.setdefault("history", [])        # every finished game, oldest first
        return data

    def save(self):
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = STATS_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=1))
            tmp.replace(STATS_FILE)
        except OSError:
            pass

    # settings ---------------------------------------------------------------
    @property
    def hard(self) -> bool:
        return self.data["settings"]["hard"]

    @hard.setter
    def hard(self, value: bool):
        self.data["settings"]["hard"] = bool(value)
        self.save()

    # games in progress ------------------------------------------------------
    def progress(self, key: str):
        return self.data["in_progress"].get(key)

    def save_progress(self, key: str, answer: str, guesses: list):
        self.data["in_progress"][key] = {"answer": answer, "guesses": list(guesses)}
        self.save()

    # finished games -----------------------------------------------------------
    def daily_result(self, day: date):
        return self.data["daily"].get(day.isoformat())

    @property
    def campaign_next(self) -> int:
        return self.data["campaign"]["next"]

    def record(self, mode: str, key: str, answer: str, guesses: list, won: bool,
               day: date = None, number: int = None):
        stats = self.data["modes"][mode]
        stats["played"] += 1
        if won:
            stats["won"] += 1
            stats["dist"][len(guesses) - 1] += 1
            if mode == "daily" and stats["last_date"] != (day - timedelta(days=1)).isoformat():
                stats["streak"] = 1
            else:
                stats["streak"] += 1
            stats["max_streak"] = max(stats["max_streak"], stats["streak"])
            self.data["total_correct"] += 1
            if answer not in self.data["words"]:
                self.data["words"].append(answer)
        else:
            stats["streak"] = 0
        stats["last"] = len(guesses) if won else None
        if day is not None:
            stats["last_date"] = day.isoformat()

        game = {"answer": answer, "guesses": list(guesses), "won": won}
        if mode == "daily":
            self.data["daily"][day.isoformat()] = game
        elif mode == "campaign":
            self.data["campaign"]["results"][str(number)] = game
            self.data["campaign"]["next"] = number + 1

        self.data["history"].append(dict(game, mode=mode, number=number,
                                         at=datetime.now().isoformat(timespec="seconds")))
        self.data["in_progress"].pop(key, None)
        self.save()

    # stats ------------------------------------------------------------------
    def mode_stats(self, mode: str) -> dict:
        return self.data["modes"][mode]

    def streak(self, mode: str) -> int:
        stats = self.data["modes"][mode]
        if mode == "daily":
            recent = {date.today().isoformat(), (date.today() - timedelta(days=1)).isoformat()}
            if stats["last_date"] not in recent:
                return 0
        return stats["streak"]

    @property
    def total_correct(self) -> int:
        return self.data["total_correct"]
