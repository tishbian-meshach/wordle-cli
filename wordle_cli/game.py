import random
import readline
import sys
from .wordlist import get_answers, get_valid_guesses

GREEN = "\033[32m"
YELLOW = "\033[33m"
GRAY = "\033[90m"
RESET = "\033[0m"
BOLD = "\033[1m"

MAX_TRIES = 6
WORD_LEN = 5

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


def render_keyboard(letter_status: dict):
    lines = []
    for row in QWERTY_ROWS:
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
        lines.append(" ".join(parts))
    return "\n".join(lines)


def play():
    print(f"{GRAY}fetching word list...{RESET}", end="\r")
    answers = get_answers()
    valid_words = get_valid_guesses()
    print(" " * 30, end="\r")  # clear the loading line

    answer = random.choice(answers)

    letter_status = {}
    guesses_made = 0
    found_green = [None] * WORD_LEN

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
            print(" ".join(colorize(char, "correct") if char is not None else "_" for char in found_green))
            print(render_keyboard(letter_status))
            print()
            continue

        if guess not in valid_words:
            print(f"{GRAY}not in word list{RESET}")
            print(" ".join(colorize(char, "correct") if char is not None else "_" for char in found_green))
            print(render_keyboard(letter_status))
            print()
            continue

        result = score_guess(guess, answer)
        guesses_made += 1

        for i in range(WORD_LEN):
            if result[i] == "correct":
                found_green[i] = guess[i]

        colored = " ".join(colorize(g, s) for g, s in zip(guess, result))
        print(colored)

        for g, s in zip(guess, result):
            current = letter_status.get(g)
            rank = {"correct": 2, "present": 1, "absent": 0}
            if current is None or rank[s] > rank[current]:
                letter_status[g] = s

        print(render_keyboard(letter_status))
        print()

        if guess == answer:
            print(f"{GREEN}{BOLD}{answer.upper()}{RESET}")
            return

    print(f"{GRAY}{answer.upper()}{RESET}")


def main():
    try:
        play()
    except KeyboardInterrupt:
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
