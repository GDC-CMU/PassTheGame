# Contributing to Pass the Game

Welcome! This file has the practical "how do I actually open a PR" details.
The vibe / what-this-is-about lives in the [README](README.md).

If anything below is unclear, ask in the Game Dev Club Discord - that's faster
than guessing.

---

## 1. One-time setup

You need **Python 3.9+**, **git**, and a GitHub account.

```bash
# 1. Clone the repo
git clone https://github.com/GDC-CMU/PassTheGame.git
cd PassTheGame

# 2. Create a virtual environment (optional but strongly recommended)
python3 -m venv venv              # Windows: py -3 -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the game to make sure everything works
python3 main.py                   # Windows: py -3 main.py
```

If `python3 main.py` opens the game with a sky, a sun, two clouds, and a 10-slot farm, you're set. The right cloud should move with Arrow keys and the left cloud with WASD.

---

## 2. The workflow

1. **Pull the latest `main`** before you start. The game has probably changed
   since the last time you looked.
   ```bash
   git checkout main
   git pull
   ```
2. **Make a branch named after you.** First name is fine; add a suffix if
   someone with the same name already has a branch.
   ```bash
   git checkout -b your-name
   ```
3. **Do your thing.** Add a feature, fix a bug, add an asset, swap the sky for
   a portal to another dimension - whatever fits "and now it's different".
4. **Test that the game still runs.**
   ```bash
   python3 main.py
   ```
   If it crashes for you, it will crash for everyone else.

   For logic changes (farming, save/load, economy), also run the headless
   self-test. It needs no display and exits non-zero if anything broke:
   ```bash
   python3 tests/selftest.py
   ```
5. **Update the Contributors log** at the bottom of `README.md` with your name
   and one or two lines about what you added.
6. **Commit and push.**
   ```bash
   git add .
   git commit -m "short description of what you did"
   git push -u origin your-name
   ```
7. **Open a Pull Request** against `main`. The link will be printed by `git
   push`, or use the "Compare & pull request" button on GitHub.
8. **Wait for review.** Once it's approved it gets merged into the main game.
   You're done.

---

## 3. PR checklist

Before clicking "Create pull request", make sure:

- [ ] The game still runs (`python3 main.py` opens the window without crashing)
- [ ] Logic changes pass the headless self-test (`python3 tests/selftest.py`)
- [ ] You added your name to the Contributors log in `README.md`
- [ ] Your changes are something the next person can build on - no
      hard-coded "only works on my machine" paths, no leftover debug prints
- [ ] You haven't deleted or rewritten someone else's contribution unless
      you're clearly improving it
- [ ] Any new image assets are in `props/` and listed in `props/README.md`
- [ ] Any new sound assets are in `passthegame_audio/`, not `props/`, with source notes in `passthegame_audio/SOURCES.md`
- [ ] Your commit message says what you actually changed

---

## 4. Style notes (not strict)

- **Tunable numbers go in `settings.py`.** Speeds, colours, sizes, counts.
  This is the first place anyone looks when they want to tweak something.
- **New sprite = new file.** Make a class, then register it in `game.py` so
  it shows up in the main loop.
- **Comment like you're writing to the next person**, because you are. Short
  comments are better than no comments.
- **Drop new images into `props/`** and follow the existing pattern: try to
  load the PNG, fall back to a drawn version if it isn't there. This means
  the game never crashes just because someone is missing a file.
- **Drop new audio into `passthegame_audio/`**. Do not put sound files in `props/`. Add CC0/source notes to `passthegame_audio/SOURCES.md`.

---

## 5. Things that are fine

- Vibe coding / using AI to help - encouraged
- Tiny changes (one new key binding, one new colour, one extra cloud)
- Huge changes (new game mode, physics, scoring, audio)
- Breaking the existing aesthetic completely
- Adding new dependencies - just remember to update `requirements.txt`

---

## 6. Things that are not fine

- Pushing directly to `main`
- Force-pushing over someone else's branch
- Committing secrets, personal info, or anything copyrighted you don't have
  the right to share
- Submitting code you know is broken and hoping reviewers won't notice

---

## 7. Stuck?

Ping the organisers in the Game Dev Club Discord. If you hit a setup
problem, paste the full error message - "it doesn't work" is hard to debug
remotely.

Have fun.
