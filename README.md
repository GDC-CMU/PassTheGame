# Welcome to Game Dev Club Pass the Game challenge

This is a collaborative game dev experiment where one game gets passed around and evolves with every contributor. You take the game, add your twist, and pass it on. Simple as that.

## How it works

1. Clone or pull the repository  
2. Create a new branch for your changes (call it your name)  
3. Do your thing  
   - Add a feature (can range from somthing very simple to some enormous 2GBs of code ) 
   - Improve something  
   - Break something and fix it better  
   - Be creative  
4. Push your branch  
5. Open a pull request  
6. Once it is approved, it gets merged into the main game  
7. Pull again later and see how the game has changed  (optional)

That is it. Keep it fun and keep it moving.

## Rules and guidelines

- Keep your changes reasonable so others can build on them  
- Write comments as if you are talking to the next person
- Make sure the game still runs  
- Do not overwrite someone else's work unless you are improving it  
- Have fun with it  
- Make a before-after video of how you evolved the game (*Completely optional, for fun purposes only*)

## Tech

- Language: Python  
- Library: pygame 2.5+

## How to run

```bash
pip install -r requirements.txt
python main.py
```

## Controls
Figure it out yourself. Try clicking somewhere, try arrow keys, space bar, enter keys or any other special keys.

## Project structure

```
pass_the_game/
│
├── main.py          # entry point – init pygame, create Game, run loop
├── game.py          # Game class – main loop, update, draw
├── cloud.py         # Cloud sprite + RainDrop helper
├── sun.py           # Sun sprite
├── settings.py      # all tuneable constants live here
├── requirements.txt
│
└── props/           # drop your PNG images here
    ├── README.md    # lists expected filenames and sizes
    ├── your prop images    # if you use one
```

**Tip for contributors:** `settings.py` is the first place to look when you
want to tweak speeds, colours, or counts.  Add new sprites as their own files
and register them in `game.py`.


## Contributors log

Add your name and 1–2 lines about what you added below.

- **Nancy**  
  Created the base game: blue sky, a movable cloud, rain on click, and a sun that darkens the sky when covered.

- **Your Name Here**  
  What you added or changed

---

Let's see how wild this game becomes 👀
