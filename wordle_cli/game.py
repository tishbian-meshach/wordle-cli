import json
import random
import re
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

# Wordle (dark theme) palette, 256-colour approximations
TILE_BG = {"correct": 71, "present": 178, "absent": 238, "empty": 235}
KEY_BG = {"correct": 71, "present": 178, "absent": 236, None: 245}
WHITE = 255
DIM_FG = 242

BOARD_W = WORD_LEN * 4 - 1           # " A " tiles + 1-space gaps
KEYS_W = len(QWERTY_ROWS[0]) * 4 - 1
LEFT_W = BOARD_W + 6
RIGHT_W = KEYS_W + 6
BOARD_H = MAX_TRIES * 2 - 1

ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def visible_len(text: str) -> int:
    return len(ANSI_RE.sub("", text))


def pad(text: str, width: int, align: str = "left") -> str:
    gap = max(0, width - visible_len(text))
    if align == "center":
        return " " * (gap // 2) + text + " " * (gap - gap // 2)
    return text + " " * gap


def cell(letter: str, bg: int, fg: int = WHITE) -> str:
    return f"\033[1;38;5;{fg};48;5;{bg}m {letter.upper()} {RESET}"


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


def render_board(history: list) -> list:
    lines = []
    for row in range(MAX_TRIES):
        if row < len(history):
            guess, result = history[row]
            tiles = [cell(g, TILE_BG[s]) for g, s in zip(guess, result)]
        else:
            tiles = [cell("·", TILE_BG["empty"], DIM_FG)] * WORD_LEN
        lines.append(" ".join(tiles))
        if row < MAX_TRIES - 1:
            lines.append("")
    return lines


def render_keys(letter_status: dict) -> list:
    lines = []
    for row in QWERTY_ROWS:
        keys = []
        for ch in row:
            status = letter_status.get(ch)
            fg = DIM_FG if status == "absent" else WHITE
            keys.append(cell(ch, KEY_BG[status], fg))
        lines.append(" ".join(keys))
        lines.append("")
    return lines[:-1]


def render_screen(history: list, letter_status: dict, message: str = "") -> str:
    """Two-pane box: guess board on the left, keyboard on the right."""
    board = render_board(history)
    right = render_keys(letter_status)
    right = [""] * max(0, (BOARD_H - len(right)) // 2) + right
    height = max(BOARD_H, len(right)) + 2

    board = [""] + board + [""] * (height - len(board) - 1)
    right = [""] + right + [""] * (height - len(right) - 1)

    out = ["╭" + "─" * LEFT_W + "┬" + "─" * RIGHT_W + "╮"]
    for b, r in zip(board, right):
        out.append("│" + pad(b, LEFT_W, "center") + "│" + pad(r, RIGHT_W, "center") + "│")
    out.append("├" + "─" * LEFT_W + "┴" + "─" * RIGHT_W + "┤")
    out.append("│" + pad(" " + message, LEFT_W + RIGHT_W + 1) + "│")
    out.append("╰" + "─" * (LEFT_W + RIGHT_W + 1) + "╯")
    return "\n".join(out)


def redraw(region_lines: int, header: str, screen: str) -> int:
    """Replace the previous prompt + box in place; returns lines now in the region."""
    if region_lines and sys.stdout.isatty():
        sys.stdout.write(f"\033[{region_lines}F\033[J")
    print(header)
    print(screen)
    return 1 + screen.count("\n") + 1


def play():
    print(f"{GRAY}fetching word list...{RESET}", end="\r")
    answers = get_answers()
    valid_words = get_valid_guesses()
    print(" " * 30, end="\r")  # clear the loading line

    answer = random.choice(answers)
    rank = {"correct": 2, "present": 1, "absent": 0}

    letter_status = {}
    history = []
    region = 0  # terminal lines used by the current prompt + box

    while len(history) < MAX_TRIES:
        remaining = MAX_TRIES - len(history)
        prompt = f"{BOLD}[{remaining}]{RESET} "
        try:
            raw_input = input(prompt)
            guess = raw_input.strip().lower()
            if raw_input:
                readline.add_history(raw_input)
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        region += 1
        header = prompt + guess

        if len(guess) != WORD_LEN or not guess.isalpha():
            message = f"{YELLOW}enter a {WORD_LEN}-letter word{RESET}"
            region = redraw(region, header, render_screen(history, letter_status, message))
            continue
        if guess not in valid_words:
            message = f"{YELLOW}{guess.upper()}{RESET} {GRAY}is not in word list{RESET}"
            region = redraw(region, header, render_screen(history, letter_status, message))
            continue

        result = score_guess(guess, answer)
        history.append((guess, result))
        for g, s in zip(guess, result):
            current = letter_status.get(g)
            if current is None or rank[s] > rank[current]:
                letter_status[g] = s
        message = ""

        if guess == answer:
            record_correct_word(answer)
            praise = ["Genius", "Magnificent", "Impressive", "Splendid", "Great", "Phew"][len(history) - 1]
            message = (f"{GREEN}{BOLD}{praise}!{RESET} {GRAY}solved in{RESET} "
                       f"{BOLD}{len(history)}/{MAX_TRIES}{RESET}")
            redraw(region, header, render_screen(history, letter_status, message))
            return

        region = redraw(region, header, render_screen(history, letter_status, message))

    message = f"{GRAY}the word was{RESET} {BOLD}{answer.upper()}{RESET}"
    region = redraw(region, header, render_screen(history, letter_status, message))


def main():
    try:
        play()
    except KeyboardInterrupt:
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
