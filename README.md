# 🟩🟨⬜ Wordle CLI

A lightweight, beautiful, terminal-based Wordle game built in Python. Play Wordle directly from your terminal with ANSI-colored guesses, real-time QWERTY keyboard tracking, and dynamic word list caching!

![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

## 🚀 Installation

You can install `wordle-cli` directly from GitHub using `pip`:

```bash
pip install git+https://github.com/tishbian-meshach/wordle-cli
```

---

## 🎮 How to Play

```bash
wordle        # menu: pick a mode, view stats, toggle hard mode
wordle -t     # today's official Wordle
wordle -n     # endless random past Wordles
wordle -c     # campaign: every Wordle from #0, day by day
wordle -s     # statistics
wordle -H     # turn hard mode on (remembered)
```

The game runs full-screen and stays open until you quit (`q` in the menu, or `Ctrl-C`).
Type letters straight into the tiles, `Enter` to submit, `Backspace` to delete, `Esc` to go back
to the menu. Unfinished games are saved and resumed.

### Game Rules
- Guess the **5-letter word** in 6 tries or less.
- After each guess, the tiles change colour to show how close your guess was:
  - 🟩 **Green**: the letter is in the word and in the correct position.
  - 🟨 **Yellow**: the letter is in the word but in the wrong position.
  - ⬜ **Gray**: the letter is not in the word.
- **Hard mode**: revealed hints must be used in every later guess.

---

## ✨ Features

- 🎨 **ANSI Terminal Colors**: Clean, high-contrast visual display of letter guesses.
- ⌨️ **QWERTY Keyboard Tracker**: Keeps track of correct, misplaced, and invalid letters on a rendered keyboard.
- 📊 **Statistics**: Played, win %, streaks and guess distribution per mode, stored in `~/.cache/wordle_cli/stats.json`.
- 🔄 **Dynamic Wordlist Caching**: Automatic local caching for fast gameplay startup.
- ⚡ **Zero External Dependencies**: Pure Python standard library implementation.

---

## 🛠️ Local Development

If you wish to contribute or modify the codebase locally:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tishbian-meshach/wordle-cli.git
   cd wordle-cli
   ```

2. **Install in editable mode:**
   ```bash
   pip install -e .
   ```

3. **Run the application:**
   ```bash
   wordle
   ```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
