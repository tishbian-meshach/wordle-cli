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

Once installed, simply run:

```bash
wordle
```

### Game Rules
- Guess the **5-letter word** in 6 tries or less.
- After each guess, the color of the letters will change to show how close your guess was to the target word:
  - 🟩 **Green**: The letter is in the word and in the correct position.
  - 🟨 **Yellow**: The letter is in the word but in the wrong position.
  - ⬜ **Gray**: The letter is not in the word.
- Below each guess, an updated **QWERTY keyboard layout** is rendered showing the letter states to help you plan your next move.

---

## ✨ Features

- 🎨 **ANSI Terminal Colors**: Clean, high-contrast visual display of letter guesses.
- ⌨️ **QWERTY Keyboard Tracker**: Keeps track of correct, misplaced, and invalid letters on a rendered keyboard.
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
