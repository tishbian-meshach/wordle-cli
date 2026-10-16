import json
import random
import readline
import sys
from pathlib import Path
from .wordlist import get_answers, get_valid_guesses

GREEN = "\033[32m"
YELLOW = "\033[33m"
GRAY = "\033[90m"
RESET = "\033[0m"
BOLD = "\033[1m"

MAX_TRIES = 6
WORD_LEN = 5

CACHE_DIR = Path.home() / ".cache" / "wordle_cli"
STATS_FILE = CACHE_DIR / "stats.json"


def load_stats() -> dict:
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"total_correct": 0, "words": []}


def record_correct_word(word: str) -> int:
    stats = load_stats()
    stats["total_correct"] = stats.get("total_correct", 0) + 1
    words = stats.get("words", [])
    if word not in words:
        words.append(word)
    stats["words"] = words
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        STATS_FILE.write_text(json.dumps(stats, indent=2))
    except OSError:
        pass
    return stats["total_correct"]


def get_total_correct() -> int:
    stats = load_stats()
    return stats.get("total_correct", 0)


QWERTY_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]


def colorize(letter: str, status: str) -> str:
    color = {"correct": GREEN, "present": YELLOW, "absent": GRAY}[status]
    return f"{color}{letter.upper()}{RESET}"


def score_guess(guess: str, answer: str):
    result = ["absent"] * WORD_LEN
    answer_chars = list(answer)

    for i in range(WORD_LEN):
        if guess[i] == answer[i]:
            result[i] = "correct"
            answer_chars[i] = None

    for i in range(WORD_LEN):
        if result[i] == "correct":
            continue
        if guess[i] in answer_chars:
            result[i] = "present"
            answer_chars[answer_chars.index(guess[i])] = None

    return result


def render_keyboard(letter_status: dict, top_line: str = None, previous_guesses: list = None):
    if previous_guesses is None:
        previous_guesses = []

    left_lines = []
    vis_lengths = []

    if top_line is not None:
        left_lines.append(top_line)
        vis_lengths.append(2 * WORD_LEN - 1)

    row_lengths = [19, 17, 13]
    for i, row in enumerate(QWERTY_ROWS):
        parts = []
        for ch in row:
            status = letter_status.get(ch)
            if status == "correct":
                parts.append(f"{GREEN}{ch.upper()}{RESET}")
            elif status == "present":
                parts.append(f"{YELLOW}{ch.upper()}{RESET}")
            elif status == "absent":
                parts.append(f"{GRAY}{ch.upper()}{RESET}")
            else:
                parts.append(ch.upper())
        left_lines.append(" ".join(parts))
        vis_lengths.append(row_lengths[i])

    KEYBOARD_WIDTH = 19
    GAP = "      "
    max_lines = max(len(left_lines), len(previous_guesses))
    output_lines = []
    for i in range(max_lines):
        if i < len(left_lines):
            part = left_lines[i]
            padding = " " * (KEYBOARD_WIDTH - vis_lengths[i])
            left = part + padding
        else:
            left = " " * KEYBOARD_WIDTH

        if i < len(previous_guesses):
            output_lines.append(left + GAP + previous_guesses[i])
        else:
            output_lines.append(left.rstrip())

    return "\n".join(output_lines)


def play():
    print(f"{GRAY}fetching word list...{RESET}", end="\r")
    answers = get_answers()
    valid_words = get_valid_guesses()
    print(" " * 30, end="\r")  # clear the loading line

    answer = random.choice(answers)

    letter_status = {}
    guesses_made = 0
    found_green = [None] * WORD_LEN
    previous_guesses = []

    while guesses_made < MAX_TRIES:
        remaining = MAX_TRIES - guesses_made
        try:
            raw_input = input(f"{BOLD}[{remaining}]{RESET} ")
            guess = raw_input.strip().lower()
            if raw_input:
                readline.add_history(raw_input)
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        if len(guess) != WORD_LEN or not guess.isalpha():
            print(f"{GRAY}enter a {WORD_LEN}-letter word{RESET}")
            top_line = " ".join(colorize(char, "correct") if char is not None else "_" for char in found_green)
            print(render_keyboard(letter_status, top_line, previous_guesses))
            print()
            continue

        if guess not in valid_words:
            print(f"{GRAY}not in word list{RESET}")
            top_line = " ".join(colorize(char, "correct") if char is not None else "_" for char in found_green)
            print(render_keyboard(letter_status, top_line, previous_guesses))
            print()
            continue

        result = score_guess(guess, answer)
        guesses_made += 1

        for i in range(WORD_LEN):
            if result[i] == "correct":
                found_green[i] = guess[i]

        colored = " ".join(colorize(g, s) for g, s in zip(guess, result))

        for g, s in zip(guess, result):
            current = letter_status.get(g)
            rank = {"correct": 2, "present": 1, "absent": 0}
            if current is None or rank[s] > rank[current]:
                letter_status[g] = s

        print(render_keyboard(letter_status, colored, previous_guesses))
        print()
        previous_guesses.append(colored)

        if guess == answer:
            total = record_correct_word(answer)
            print(f"{GREEN}{BOLD}{answer.upper()}{RESET}")
            print(f"{GRAY}Total words correctly guessed: {RESET}{BOLD}{GREEN}{total}{RESET}")
            return

    total = get_total_correct()
    print(f"{GRAY}{answer.upper()}{RESET}")
    print(f"{GRAY}Total words correctly guessed: {RESET}{BOLD}{total}{RESET}")


def main():
    try:
        play()
    except KeyboardInterrupt:
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
