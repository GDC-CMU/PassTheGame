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
| apple_icon.png  | game.py | 64 × 64 px     | Square PNG, mature plant icon      |
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
| apple_phase1.png | game.py | 170 × 280 px    | Plant growth phase 1               |
| apple_phase2.png | game.py | 170 × 280 px    | Plant growth phase 2               |
| apple_phase3.png | game.py | 170 × 280 px    | Plant growth phase 3 (no fruit)    |
| apple_phase4.png | game.py | 170 × 280 px    | Plant growth phase 4 (with fruit)  |
| storm_titan.png | storm_titan.py | 260 × 130 px | Storm Titan boss sprite (optional; falls back to drawn) |
| cyclone_titan.png | cyclone_titan.py | 340 × 180 px | Cyclone Titan boss sprite (optional; falls back to drawn) |
| storm_seed_icon.png | plants.py | 64 × 64 px | Seed icon for the Storm Seed (special boss drop) |
| storm_seed_phase1.png | plants.py | 64 × 96 px | Storm Seed growth phase 1 (special boss plant) |
| storm_seed_phase2.png | plants.py | 64 × 96 px | Storm Seed growth phase 2 (special boss plant) |
| storm_seed_phase3.png | plants.py | 64 × 96 px | Storm Seed growth phase 3 (special boss plant) |
| storm_seed_phase4.png | plants.py | 64 × 96 px | Storm Seed growth phase 4 (special boss plant) |
| squirrel.png | critters.py | 56 × 28 px | Chipmunk thief sprite (optional; auto-scaled) |
| snake.png | critters.py | 70 × 18 px | Snake thief sprite (optional; auto-scaled) |

All images should be **PNG with an alpha channel** so transparency works
correctly against the sky background.

Note on sprite sizes: most plant phases are 64 × 96, but you can declare
custom dimensions using sprite_w sprite_h in their PlantType subclass.

If a seed icon is missing, the UI falls back to a letter placeholder.

*Note: There are no real rules as long as your code works*

Future contributors: add your own prop filenames to this table when you
introduce new sprites.
