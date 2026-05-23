# props/

Drop your image files here.  The game loads them automatically if they exist;
otherwise it falls back to the built-in drawn versions.

| Filename    | Used by   | Recommended size | Notes                              |
|-------------|-----------|------------------|------------------------------------|
| cloud.png   | cloud.py  | 160 × 80 px      | PNG with transparency (RGBA)       |
| sun.png     | sun.py    | 150 × 150 px     | PNG with transparency (RGBA)       |
| carrot_icon.png  | game.py | 64 × 64 px     | Square PNG, mature plant icon      |
| lettuce_icon.png | game.py | 64 × 64 px     | Square PNG, mature plant icon      |
| tomato_icon.png  | game.py | 64 × 64 px     | Square PNG, mature plant icon      |
| ui_panel.png | game.py  | 240 × 600 px     | Right-side UI panel background     |
| dead_plant.png | game.py | 64 × 96 px     | Dead plant sprite                  |
| carrot_phase1.png | game.py | 64 × 96 px     | Plant growth phase 1               |
| carrot_phase2.png | game.py | 64 × 96 px     | Plant growth phase 2               |
| carrot_phase3.png | game.py | 64 × 96 px     | Plant growth phase 3               |
| lettuce_phase1.png | game.py | 64 × 96 px    | Plant growth phase 1               |
| lettuce_phase2.png | game.py | 64 × 96 px    | Plant growth phase 2               |
| lettuce_phase3.png | game.py | 64 × 96 px    | Plant growth phase 3               |
| tomato_phase1.png | game.py | 64 × 96 px     | Plant growth phase 1               |
| tomato_phase2.png | game.py | 64 × 96 px     | Plant growth phase 2               |
| tomato_phase3.png | game.py | 64 × 96 px     | Plant growth phase 3               |
| tomato_phase4.png | game.py | 64 × 96 px     | Plant growth phase 4               |

All images should be **PNG with an alpha channel** so transparency works
correctly against the sky background.

If a seed icon is missing, the UI falls back to a letter placeholder.

*Note: There are no real rules as long as your code works*

Future contributors: add your own prop filenames to this table when you
introduce new sprites.
