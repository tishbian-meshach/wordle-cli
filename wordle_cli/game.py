"""Full-screen terminal Wordle: menu, today / random / campaign modes, stats."""
import argparse
import os
import random
import re
import select
import shutil
import signal
import sys
import termios
import time
import tty
from collections import Counter, deque
from datetime import date, datetime, timedelta

from .store import MAX_TRIES, Store
from .wordlist import FALLBACK_WORDS, WORDLE_LAUNCH, get_daily_word, get_valid_guesses

GREEN = "\033[38;5;77m"
YELLOW = "\033[38;5;178m"
GRAY = "\033[90m"
RESET = "\033[0m"
BOLD = "\033[1m"

WORD_LEN = 5
QWERTY_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
RANK = {"correct": 2, "present": 1, "absent": 0}

# Wordle (dark theme) palette, 256-colour approximations
TILE_BG = {"correct": 71, "present": 178, "absent": 238, "empty": 235,
           "pending": 240, "typed": 240, "slot": 237}
KEY_BG = {"correct": 71, "present": 178, "absent": 236, None: 245}
WHITE = 255
DIM_FG = 242

BOARD_W = WORD_LEN * 4 - 1           # " A " tiles + 1-space gaps
KEYS_W = len(QWERTY_ROWS[0]) * 4 - 1
LEFT_W = BOARD_W + 6
RIGHT_W = KEYS_W + 6
INNER_W = LEFT_W + RIGHT_W + 1
BOX_W = INNER_W + 2
BOARD_H = MAX_TRIES * 2 - 1

PRAISE = ["Genius", "Magnificent", "Impressive", "Splendid", "Great", "Phew"]
ORDINAL = ["1st", "2nd", "3rd", "4th", "5th"]
MODE_NAMES = {"daily": "Today", "random": "Random", "campaign": "Campaign"}
FETCH_ERRORS = (OSError, ValueError, KeyError)  # URLError/HTTPError/timeouts are OSErrors

ANSI_RE = re.compile(r"\033\[[0-9;?]*[a-zA-Z]")


# --------------------------------------------------------------------------- #
# rendering helpers
# --------------------------------------------------------------------------- #
def visible_len(text: str) -> int:
    return len(ANSI_RE.sub("", text))


def pad(text: str, width: int, align: str = "left") -> str:
    gap = max(0, width - visible_len(text))
    if align == "center":
        return " " * (gap // 2) + text + " " * (gap - gap // 2)
    if align == "right":
        return " " * gap + text
    return text + " " * gap


def block(lines: list) -> list:
    """Pad lines to a common width so a centred block stays left-aligned."""
    width = max((visible_len(line) for line in lines), default=0)
    return [pad(line, width) for line in lines]


def cell(letter: str, bg: int, fg: int = WHITE) -> str:
    return f"\033[1;38;5;{fg};48;5;{bg}m {letter.upper()} {RESET}"


def dim(text: str) -> str:
    return f"{GRAY}{text}{RESET}"


def spread(left: str, right: str, width: int = INNER_W - 2) -> str:
    return left + " " * max(1, width - visible_len(left) - visible_len(right)) + right


SEP = object()  # a column line drawn as a horizontal rule joined to the borders


def box(columns: list, widths: list, footer: str = None) -> list:
    height = max(len(col) for col in columns)
    columns = [col + [""] * (height - len(col)) for col in columns]
    out = ["╭" + "┬".join("─" * w for w in widths) + "╮"]
    for row in zip(*columns):
        rules = [t is SEP for t in row]
        line = "├" if rules[0] else "│"
        for i, (t, w) in enumerate(zip(row, widths)):
            line += "─" * w if rules[i] else pad(t, w, "center")
            if i + 1 < len(row):
                line += {(True, True): "┼", (True, False): "┤", (False, True): "├"}.get(
                    (rules[i], rules[i + 1]), "│")
        out.append(line + ("┤" if rules[-1] else "│"))
    if footer is None:
        out.append("╰" + "┴".join("─" * w for w in widths) + "╯")
    else:
        total = sum(widths) + len(widths) - 1
        out.append("├" + "┴".join("─" * w for w in widths) + "┤")
        out.append("│" + pad(" " + footer, total) + "│")
        out.append("╰" + "─" * total + "╯")
    return out


SCREEN_H = BOARD_H + 4  # height of the game box; every screen uses exactly this size


def panel(lines: list, footer: str = None) -> list:
    """Single-pane box, same size as the game box, content centred vertically."""
    rows = SCREEN_H - (2 if footer is None else 4)
    lines = lines[:rows]
    top = (rows - len(lines)) // 2
    return box([[""] * top + lines + [""] * (rows - len(lines) - top)], [INNER_W], footer)


def logo() -> list:
    colours = ["correct", "present", "absent", "correct", "present", "absent"]
    return [" ".join(cell(ch, TILE_BG[c]) for ch, c in zip("wordle", colours))]


# --------------------------------------------------------------------------- #
# game rules
# --------------------------------------------------------------------------- #
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


def hard_mode_error(guess: str, history: list):
    """Revealed hints must be reused: greens stay put, yellows must appear."""
    for prev, result in history:
        for i, (ch, status) in enumerate(zip(prev, result)):
            if status == "correct" and guess[i] != ch:
                return f"{ORDINAL[i]} letter must be {ch.upper()}"
        needed = Counter(ch for ch, status in zip(prev, result) if status != "absent")
        have = Counter(guess)
        for ch, count in needed.items():
            if have[ch] < count:
                return f"guess must contain {ch.upper()}"
    return None


class Game:
    def __init__(self, mode: str, key: str, answer: str, title: str, hard: bool,
                 guesses=(), day: date = None, number: int = None):
        self.mode, self.key, self.answer, self.title = mode, key, answer, title
        self.hard, self.day, self.number = hard, day, number
        self.history, self.status, self.current = [], {}, ""
        for guess in guesses:
            self.apply(guess)

    def apply(self, guess: str):
        result = score_guess(guess, self.answer)
        self.history.append((guess, result))
        for ch, status in zip(guess, result):
            known = self.status.get(ch)
            if known is None or RANK[status] > RANK[known]:
                self.status[ch] = status

    @property
    def guesses(self) -> list:
        return [guess for guess, _ in self.history]

    @property
    def won(self) -> bool:
        return bool(self.history) and self.history[-1][0] == self.answer

    @property
    def over(self) -> bool:
        return self.won or len(self.history) >= MAX_TRIES


def render_board(history: list, current: str = None) -> list:
    """current=None hides the typing row (game over / revealing)."""
    lines = []
    for row in range(MAX_TRIES):
        if row < len(history):
            guess, result = history[row]
            tiles = [cell(g, TILE_BG[s]) for g, s in zip(guess, result)]
        elif row == len(history) and current is not None:
            tiles = ([cell(ch, TILE_BG["typed"]) for ch in current]
                     + [cell(" ", TILE_BG["slot"])] * (WORD_LEN - len(current)))
        else:
            tiles = [cell("·", TILE_BG["empty"], DIM_FG)] * WORD_LEN
        lines.append(" ".join(tiles))
        lines.append("")
    return lines[:-1]


def render_keys(letter_status: dict) -> list:
    lines = []
    for i, row in enumerate(QWERTY_ROWS):
        keys = []
        for ch in row:
            status = letter_status.get(ch)
            keys.append(cell(ch, KEY_BG[status], DIM_FG if status == "absent" else WHITE))
        if i == len(QWERTY_ROWS) - 1:
            keys = [cell("enter", KEY_BG[None])] + keys + [cell("⌫", KEY_BG[None])]
        lines.append(" ".join(keys))
        lines.append("")
    return lines[:-1]


# --------------------------------------------------------------------------- #
# terminal
# --------------------------------------------------------------------------- #
class Terminal:
    """Raw-ish key input on the alternate screen; restores the terminal on exit."""

    def __enter__(self):
        self.fd = sys.stdin.fileno()
        self.saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        sys.stdout.write("\033[?1049h\033[?25l")  # alternate screen, hide cursor
        sys.stdout.flush()
        self.last = []
        self.pending = deque()
        signal.signal(signal.SIGWINCH, lambda *_: self.paint())
        return self

    def __exit__(self, *exc):
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()

    KEYS = {"\r": "enter", "\n": "enter", "\x7f": "backspace", "\x08": "backspace",
            "\x1b": "esc", "\x04": "quit", "A": "up", "B": "down", "C": "right", "D": "left"}

    def key(self, timeout: float = None):
        """Next key press, or None if `timeout` seconds pass without one."""
        if not self.pending:
            if timeout is not None and not select.select([self.fd], [], [], max(0, timeout))[0]:
                return None
            self.pending.extend(self.parse(os.read(self.fd, 256).decode(errors="ignore")))
        return self.pending.popleft() if self.pending else None

    @classmethod
    def parse(cls, data: str) -> list:
        """Split a burst of input (fast typing arrives together) into keys."""
        keys, i = [], 0
        while i < len(data):
            ch = data[i]
            i += 1
            if ch == "\x1b" and i < len(data) and data[i] in "[O":
                end = i + 1
                while end < len(data) and not "@" <= data[end] <= "~":
                    end += 1
                seq = data[i + 1:end + 1]
                i = end + 1
                if seq in ("A", "B", "C", "D"):  # arrows; other escape sequences are ignored
                    keys.append(cls.KEYS[seq])
            elif ch in cls.KEYS and len(ch) == 1 and not ch.isalpha():
                keys.append(cls.KEYS[ch])
            elif ch.isprintable():
                keys.append(ch)
        return keys

    def paint(self, lines: list = None):
        """Draw lines centred on screen, overwriting the previous frame."""
        if lines is not None:
            self.last = lines
        lines = self.last
        if not lines:
            return
        cols, rows = shutil.get_terminal_size()
        width = max(visible_len(line) for line in lines)
        if cols < width or rows < len(lines):
            lines = [f"enlarge the terminal to {width}×{len(lines)} (now {cols}×{rows})"]
            width = visible_len(lines[0])
        left = " " * max(0, (cols - width) // 2)
        top = max(0, (rows - len(lines)) // 2)
        out = "\033[K\n" * top + "\n".join(left + line + "\033[K" for line in lines)
        sys.stdout.write("\033[H" + out + "\033[J")
        sys.stdout.flush()


# --------------------------------------------------------------------------- #
# application
# --------------------------------------------------------------------------- #
def puzzle_number(day: date) -> int:
    return (day - WORDLE_LAUNCH).days


def time_to_tomorrow() -> str:
    now = datetime.now()
    left = datetime.combine(now.date() + timedelta(days=1), datetime.min.time()) - now
    hours, rest = divmod(int(left.total_seconds()), 3600)
    return f"{hours}h {rest // 60:02d}m"


class Quit(Exception):
    pass


class App:
    def __init__(self, term: Terminal, store: Store):
        self.term, self.store = term, store
        self.valid = None
        self.menu_index = 0

    def key(self, timeout: float = None):
        k = self.term.key(timeout)
        if k == "quit":
            raise Quit
        return k

    def notice(self, text: str, wait: bool = True):
        self.term.paint(panel(["", text, ""], dim("press any key") if wait else ""))
        if wait:
            self.key()

    def words(self) -> set:
        if self.valid is None:
            self.notice(dim("loading word list…"), wait=False)
            self.valid = get_valid_guesses()
        return self.valid

    # main loop ---------------------------------------------------------------
    def run(self, mode: str = None):
        try:
            while True:
                mode = mode or self.menu()
                if mode == "quit":
                    return
                if mode == "stats":
                    self.stats_screen()
                elif mode == "help":
                    self.help_screen()
                else:
                    self.session(mode)
                mode = None
        except Quit:
            return

    # menu ------------------------------------------------------------------
    def menu_items(self) -> list:
        today = date.today()
        result = self.store.daily_result(today)
        if result:
            today_desc = f"solved in {len(result['guesses'])}" if result["won"] else "missed"
        elif self.store.progress(f"daily:{today}"):
            today_desc = "in progress"
        else:
            today_desc = "not played yet"
        total = puzzle_number(today) + 1
        done = min(self.store.campaign_next, total)
        return [
            ("daily", "t", "Today's Wordle", f"#{puzzle_number(today)} · {today_desc}"),
            ("random", "n", "Random", "endless practice"),
            ("campaign", "c", "Campaign", f"day {done} of {total} solved" if done else "from Wordle #0"),
            ("stats", "s", "Statistics", ""),
            ("hard", "h", "Hard mode", f"{GREEN}on{RESET}" if self.store.hard else "off"),
            ("help", "?", "Help", ""),
            ("quit", "q", "Quit", ""),
        ]

    def menu(self) -> str:
        while True:
            items = self.menu_items()
            rows = []
            for i, (_, hotkey, label, desc) in enumerate(items):
                if i == self.menu_index:
                    rows.append(f"{GREEN}{BOLD}▸ {label:<16}{RESET}{GRAY}{desc}{RESET}")
                else:
                    rows.append(f"  {label:<16}{GRAY}{desc}{RESET}")
            lines = logo() + [""] + block(rows)
            footer = spread(dim("↑↓ move · enter select"), dim("q quit"))
            self.term.paint(panel(lines, footer))

            k = self.key()
            if k in ("up", "k"):
                self.menu_index = (self.menu_index - 1) % len(items)
            elif k in ("down", "j"):
                self.menu_index = (self.menu_index + 1) % len(items)
            else:
                if k == "enter":
                    choice = items[self.menu_index][0]
                else:
                    choice = next((item[0] for item in items if item[1] == k), None)
                    if choice:
                        self.menu_index = [item[0] for item in items].index(choice)
                if choice == "hard":
                    self.store.hard = not self.store.hard
                elif choice:
                    return choice

    # sessions ------------------------------------------------------------------
    def session(self, mode: str):
        """Keep playing games of one mode until the player leaves to the menu."""
        while True:
            game = self.next_game(mode)
            if game is None or self.play(game) == "menu":
                return
            if mode == "daily":
                return

    def next_game(self, mode: str):
        hard = self.store.hard
        tag = " · hard" if hard else ""
        today = date.today()

        if mode == "random":
            saved = self.store.progress("random")
            if saved:
                answer, guesses = saved["answer"], saved["guesses"]
            else:
                self.notice(dim("picking a word…"), wait=False)
                answer, guesses = self.random_answer(), []
            played = self.store.mode_stats("random")["played"]
            return Game("random", "random", answer, f"Random · game {played + 1}{tag}", hard, guesses)

        if mode == "daily":
            day = today
            title = f"Wordle #{puzzle_number(day)} · {day:%a %d %b %Y}{tag}"
            result = self.store.daily_result(day)
            if result:
                return Game("daily", f"daily:{day}", result["answer"], title, hard,
                            result["guesses"], day=day)
        else:
            number = self.store.campaign_next
            day = WORDLE_LAUNCH + timedelta(days=number)
            if day > today:
                self.notice(f"{GREEN}{BOLD}All caught up!{RESET} you have played every Wordle up to today")
                return None
            title = f"Campaign · #{number} · {day:%d %b %Y}{tag}"

        key = f"{mode}:{day if mode == 'daily' else number}"
        saved = self.store.progress(key)
        if saved:
            answer, guesses = saved["answer"], saved["guesses"]
        else:
            self.notice(dim("fetching puzzle…"), wait=False)
            try:
                answer, guesses = get_daily_word(day.isoformat()).lower(), []
            except FETCH_ERRORS:
                self.notice(f"{YELLOW}couldn't fetch Wordle #{puzzle_number(day)}{RESET} · check your connection")
                return None
        return Game(mode, key, answer, title, hard, guesses, day=day, number=puzzle_number(day))

    @staticmethod
    def random_answer() -> str:
        day = WORDLE_LAUNCH + timedelta(days=random.randint(0, puzzle_number(date.today())))
        try:
            return get_daily_word(day.isoformat()).lower()
        except FETCH_ERRORS:
            return random.choice(FALLBACK_WORDS)

    # playing ------------------------------------------------------------------
    def draw_game(self, game: Game, message: str = "", history: list = None, tips: str = None,
                  typing: bool = None):
        if typing is None:
            typing = history is None and not game.over
        board = [""] + render_board(game.history if history is None else history,
                                    game.current if typing else None) + [""]
        name, *details = game.title.split(" · ")
        title = f"{BOLD}{name}{RESET}" + "".join(dim(f" · {d}") for d in details)
        # title lines up with the first board row, tips with the last one
        if tips is None:  # while typing, a message takes the place of the key tips
            bottom = [message or dim("enter submit · ⌫ delete · esc menu"), ""]
        else:
            bottom = [message, tips] if message else [tips, ""]
        right = ["", title, SEP, ""] + render_keys(game.status) + ["", SEP] + bottom
        self.term.paint(box([board, right], [LEFT_W, RIGHT_W]))

    def reveal(self, game: Game, guess: str):
        """Flip the tiles one by one; keys typed meanwhile go to the next row."""
        result = score_guess(guess, game.answer)
        last_row = guess == game.answer or len(game.history) + 1 >= MAX_TRIES
        later = []
        for shown in range(1, WORD_LEN + 1):
            partial = result[:shown] + ["pending"] * (WORD_LEN - shown)
            deadline = time.time() + 0.15
            while True:
                self.draw_game(game, history=game.history + [(guess, partial)], typing=not last_row)
                k = self.key(deadline - time.time())
                if k is None:
                    break
                if last_row:
                    continue  # nothing to type into; don't let keys skip the result
                if later or not self.type_key(game, k):
                    later.append(k)  # enter and anything after it: handled once revealed
        game.apply(guess)
        self.term.pending.extendleft(reversed(later))

    @staticmethod
    def type_key(game: Game, k: str) -> bool:
        """Apply a letter/backspace to the row being typed; False for other keys."""
        if k == "backspace":
            game.current = game.current[:-1]
        elif k and len(k) == 1 and k.isascii() and k.isalpha():
            if len(game.current) < WORD_LEN:
                game.current += k.lower()
        else:
            return False
        return True

    def submit(self, game: Game) -> str:
        """Returns an error message, or '' if the guess was played."""
        guess = game.current
        if len(guess) < WORD_LEN:
            return "not enough letters"
        if guess != game.answer and guess not in self.words():
            return f"{BOLD}{guess.upper()}{RESET}{YELLOW} is not in the word list"
        if game.hard:
            error = hard_mode_error(guess, game.history)
            if error:
                return error
        game.current = ""
        self.reveal(game, guess)
        if game.over:
            self.store.record(game.mode, game.key, game.answer, game.guesses, game.won,
                              day=game.day, number=game.number)
        else:
            self.store.save_progress(game.key, game.answer, game.guesses)
        return ""

    def play(self, game: Game) -> str:
        """Returns 'next' to continue the session or 'menu' to leave it."""
        self.words()
        message = ""
        while not game.over:
            self.draw_game(game, f"{YELLOW}{message}{RESET}" if message else "")
            k = self.key()
            message = ""
            if k == "esc":
                return "menu"
            if k == "enter":
                message = self.submit(game)
            else:
                self.type_key(game, k)

        if game.won:
            result = f"{GREEN}{BOLD}{PRAISE[len(game.history) - 1]}!{RESET} solved in {len(game.history)}/{MAX_TRIES}"
        else:
            result = f"the word was {BOLD}{game.answer.upper()}{RESET}"
        if game.mode == "daily":
            hint = dim(f"next in {time_to_tomorrow()} · s stats · enter menu")
        else:
            hint = dim(f"enter next {'word' if game.mode == 'random' else 'day'} · s stats · esc menu")

        while True:
            self.draw_game(game, result, tips=hint)
            k = self.key()
            if k == "s":
                self.stats_screen(game.mode)
            elif k == "enter":
                return "menu" if game.mode == "daily" else "next"
            elif k in ("esc", "m"):
                return "menu"

    # screens ------------------------------------------------------------------
    def stats_screen(self, mode: str = "daily"):
        modes = list(MODE_NAMES)
        tab = modes.index(mode)
        while True:
            mode = modes[tab]
            stats = self.store.mode_stats(mode)
            tabs = "     ".join(f"{GREEN}{BOLD}{MODE_NAMES[m]}{RESET}" if m == mode else dim(MODE_NAMES[m])
                                for m in modes)
            played = stats["played"]
            numbers = [played, round(100 * stats["won"] / played) if played else 0,
                       self.store.streak(mode), stats["max_streak"]]
            labels = ["played", "win %", "streak", "max streak"]

            top = max(stats["dist"]) or 1
            bars = []
            for i, count in enumerate(stats["dist"]):
                bg = TILE_BG["correct"] if stats["last"] == i + 1 else TILE_BG["absent"]
                width = round(30 * count / top)
                bars.append(f"{i + 1} \033[1;38;5;{WHITE};48;5;{bg}m{' ' * width} {count} {RESET}")

            lines = [tabs, "",
                     "".join(pad(f"{BOLD}{n}{RESET}", 12, "center") for n in numbers),
                     "".join(pad(dim(label), 12, "center") for label in labels),
                     ""] + [pad(bar, 38) for bar in bars]  # fixed width: no shifting between tabs
            if mode == "campaign":
                total = puzzle_number(date.today()) + 1
                done = min(self.store.campaign_next, total)
                extra = dim("campaign ") + f"{BOLD}{done}/{total}{RESET}" + dim(f" · {100 * done // total}%")
            else:
                extra = dim("lifetime words solved ") + f"{GREEN}{BOLD}{self.store.total_correct}{RESET}"
            footer = spread(dim("←→ switch · esc back"), extra)
            self.term.paint(panel(lines, footer))

            k = self.key()
            if k in ("left", "h"):
                tab = (tab - 1) % len(modes)
            elif k in ("right", "l", "\t"):
                tab = (tab + 1) % len(modes)
            elif k in ("esc", "enter", "q", "s"):
                return

    def help_screen(self):
        sample = [("w", "correct"), ("e", "present"), ("a", "absent")]
        lines = block([
            f"{BOLD}How to play{RESET}  guess the hidden word in {MAX_TRIES} tries",
            " ".join(cell(ch, TILE_BG[s]) for ch, s in sample)
            + dim("  right spot · in the word, wrong spot · not in it"),
            "",
            f"{BOLD}Today{RESET}       the official Wordle of the day      {dim('wordle -t')}",
            f"{BOLD}Random{RESET}      endless practice with past answers  {dim('wordle -n')}",
            f"{BOLD}Campaign{RESET}    every Wordle from #0, day by day    {dim('wordle -c')}",
            f"{BOLD}Statistics{RESET}  streaks and guess distribution      {dim('wordle -s')}",
            f"{BOLD}Hard mode{RESET}   revealed hints must be reused       {dim('wordle -H')}",
            "",
            f"{BOLD}Keys{RESET}  enter submit · ⌫ delete · esc menu (saved) · ctrl-c quit",
        ])
        self.term.paint(panel(lines, dim("press any key")))
        self.key()


def main():
    parser = argparse.ArgumentParser(prog="wordle", description="Wordle in your terminal.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("-t", "--today", dest="mode", action="store_const", const="daily",
                       help="play today's Wordle")
    modes.add_argument("-n", "--random", dest="mode", action="store_const", const="random",
                       help="endless random past Wordles")
    modes.add_argument("-c", "--campaign", dest="mode", action="store_const", const="campaign",
                       help="play every Wordle from day one, in order")
    modes.add_argument("-s", "--stats", dest="mode", action="store_const", const="stats",
                       help="show statistics")
    parser.add_argument("-H", "--hard", action="store_true", help="turn hard mode on (remembered)")
    args = parser.parse_args()

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        sys.exit("wordle needs an interactive terminal")

    store = Store()
    if args.hard:
        store.hard = True
    try:
        with Terminal() as term:
            App(term, store).run(args.mode)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
