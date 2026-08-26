<p align="center">
  <img src="marketing/logo.png" alt="Pass the Game - Farm Patch" width="860">
</p>

# Pass the Game

A Python 3.9+ / pygame cozy farming-defense hybrid built by CMU Game Dev Club.

## Enjoy the game here:

[Play Farm Patch](https://eterna-studio.itch.io/farm-patch)

## What this is

You manage a 10-slot farm with two movable clouds, one sun, and crops that only thrive inside their own water and sun bands. The right cloud uses Arrow keys. The left cloud uses WASD. Click a cloud to cycle rain Off, Light, and Heavy.

The puzzle is farming under pressure: keep crops in band, harvest them into Inventory, sell produce, unlock Market licenses, and survive thieves, crows, mini-bosses, and five Titans.

## Features

- 10 plant slots with per-crop water and sun bands.
- Two independent clouds for shade and rain control.
- 18 crops, including keystone crops Fern, Reed, Clover, Orchid, Lightning Vine, and the Everbloom quest crop.
- Carrot and Clover are forgiving starters, but their soil dries out enough that Golden harvests still need watering.
- Golden crops when a plant spends most of its life in band. Golden produce sells for 2x.
- Five Titans: Storm, Cyclone, Drought, Frost, and the finale Inferno Titan.
- Year's End Tempest in Winter, with faster Titan timers and an Inferno opener once difficulty reaches 4.
- Early-game grace that ramps threats up over the first weeks and years instead of swarming new players.
- Daily 5g stipend so a wiped-out farm can recover.
- Ground thieves, flying crows, five mini-bosses, and helpful bees.
- Market progression for seed licenses, rare seed offers, and tool unlocks as related threats appear.
- Tools: Compost, Scarecrow, Lightning Rod, and Bell.
- Hireable auto-harvester worker and Prime harvest timing.
- Almanac goals, yearly report card, Legacy %, Next-Year preview, challenge ladder, and Everbloom quest.
- Rewritten 12-step tutorial that uses an isolated save path. It never reads or writes `savegame.json`.
- Particle juice, parallax mountains, day-night visuals, ambient loops, and sound effects.
- Auto-save every 2 minutes plus manual Save.

## How to run

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 main.py                 # Windows may use: py -3 main.py
```

The game is fullscreen by default because `GAME_FULLSCREEN = True` in `settings.py`.
Set it to `False` if you want the scaled 1200x600 window instead.

## Controls

### Farming and menus

- Arrow keys: move the right cloud.
- WASD: move the left cloud.
- Click a cloud: cycle rain Off, Light, Heavy.
- Click a seed in the panel: select it. Click an empty slot to plant it.
- Drag a seed from the panel to a slot: plant it.
- Click a harvestable crop: harvest it into Inventory.
- Click a dead crop: clear it and gain Compost salvage.
- Click an Inventory item row: sell one item.
- Right-click an Inventory item row: sell the whole stack.
- E: open or close Inventory.
- M: open or close Market.
- J: open or close Almanac. Also dismisses the yearly report card.
- P: pause or resume.
- ESC: close an overlay, or return to the main menu.
- Enter, Space, ESC, or J: dismiss the yearly report card.
- Main Menu button: return to the main menu.

### Defense

- Click Squirrel, Snake, crows, Burrow Mole, Locust Pair, or the Tangle Vine root to scare or counter them.
- Move a cloud over Glare Mote or Chill Wisp danger zones to counter them.
- Move a cloud over a Titan warning marker to block the strike.
- T: ring the Bell. Costs 8g and has a cooldown.
- H: hire the worker when you can afford it.
- Click tool buttons in the panel, then click a slot to use Compost, Scarecrow, or Lightning Rod.

### Debug keys

These are live in normal gameplay and are useful for testing.

- Shift+M: add 500 money.
- U: unlock all seeds and tools, plus grant +5 Storm Crystal and +5 Compost.
- B: toggle Storm Titan.
- C: toggle Cyclone Titan.
- X: toggle Drought Titan.
- F: toggle Frost Titan.
- I: toggle Inferno Titan.
- 1: force Burrow Mole.
- 2: force Locust Pair.
- 3: force Glare Mote.
- 4: force Tangle Vine.
- G: force a crow.
- V: force Squirrel.
- N: force Snake.
- O: force Prime timers on current crops.

## How to play

### Farm the bands

Every crop has a healthy water band and sun band. Clouds shade crops and, when raining, add water. Clear sky adds sun and dries plants out. Growth is best while a crop is in range. Bad conditions can kill a plant.

Some crops change the layout puzzle:

- Sunflower warms its neighbors when ripe.
- Fern shades its neighbors when ripe.
- Reed waters its neighbors when ripe.
- Clover is cheap, pollinatable, and needs enough rain to finish Golden.
- Moonpetal only grows at night.
- Mushroom can spread to an empty neighbor when harvested.
- Lightning Vine grows faster while a boss is active and can surge from lightning.
- Orchid and Everbloom have tight bands and need attention.

### Handle Titans

Titans target valuable crops when they can. Their HP and spawn cadence scale with Almanac difficulty. Difficulty climbs each year up to a high safety cap, so normal play keeps getting harder. A perfect block gives bonus damage, and block combos add more damage.

- Storm Titan targets one slot. Cover the marked x-position with any cloud.
- Cyclone Titan targets one slot plus adjacent slots. It requires a raining cloud to block.
- Drought Titan attacks through the sun. Cover the sun with a cloud during the warning.
- Frost Titan marks multiple planted slots. Each mark is checked separately. Unblocked marks freeze growth instead of killing.
- Inferno Titan unlocks at difficulty 4. It cycles Storm, Cyclone, Drought, Frost, then its own fire phase, alternating Firestorm multi-marks and Lava strikes.

Winter brings the Year's End Tempest, where Titan spawn timers run faster. Once Inferno is unlocked, it opens the Tempest. The year ends with a report card and a preview of next year's difficulty.

### Use the Market loop

Tools start locked. The Market unlocks tool licenses after the related threat appears:

- Crop death unlocks Compost offers.
- Ground critters unlock Scarecrow offers.
- Lightning threats unlock Lightning Rod offers.
- Flying crows unlock Bell offers.

The Market also sells seed licenses as your total earnings rise and can feature rare locked seeds. Everbloom appears through its Legacy quest. You also get a 5g daily stipend so a wiped-out farm can recover.

### Deal with pests and helpers

Squirrels and snakes walk in from the sides and steal plants unless clicked or blocked by scarecrows. Crows fly in, can steal crops, and when enough are active they gang up on scarecrows. The Bell scares off active flying crows for 8g.

Mini-bosses are short reaction tests:

- Burrow Mole salts a slot unless clicked.
- Locust Pair clears crops unless both locusts are clicked.
- Glare Mote overheats a sun-lover unless the column is shaded.
- Chill Wisp freezes growth across a band unless covered by clouds.
- Tangle Vine pins the nearest cloud for about 3.5 seconds unless its root is clicked three times.

Bees are helpers, not pests. During calm daylight they visit flowering crops such as Tomato, Apple, Pumpkin, Sunflower, Clover, and Everbloom. A bee only boosts a crop that is already in its healthy band.

### Worker, Prime, and Legacy

The worker auto-harvests ripe crops into Inventory after being hired. Ripe crops also enter Prime: harvest soon for extra value, wait too long and the crop spoils. Legacy tracks long-term completion through crop discovery, Titan survival, golden harvests, best year, money milestones, and challenges. Everbloom unlocks through that endgame quest and still follows normal water and sun rules.

## Audio and assets

- Image assets live in `props/` and are listed in `props/README.md`.
- Sound assets live in `passthegame_audio/`.
- `passthegame_audio/SOURCES.md` lists the CC0 sources for the generated sound effects.

Current audio covers UI clicks/open/close/errors, purchases, tool placement, worker hire, boss spawn/block/perfect, critter spawn/scare/steal, bees, crows, mini-boss spawn/counter/fail, new day, and report card cues, plus ambience and legacy sound files.

## Project structure

```text
PassTheGame/
├── main.py                  # entry point
├── main_menu.py             # title screen and tutorial entry
├── tutorial.py              # isolated 12-step teach-through-play tutorial
├── game.py                  # main game loop, input, UI, saves
├── settings.py              # tunable constants
├── plants.py                # crop definitions and sprite filenames
├── farming.py               # PlantSlot state and rendering helpers
├── critters.py              # Squirrel, Snake, Bee
├── crows.py                 # flying crows and Bell support
├── minibosses.py            # Burrow Mole, Locust Pair, Glare Mote, Chill Wisp, Tangle Vine
├── storm_titan.py           # Storm Titan
├── cyclone_titan.py         # Cyclone Titan
├── drought_titan.py         # Drought Titan
├── frost_titan.py           # Frost Titan
├── finalboss.py             # Inferno Titan
├── market.py                # seed and tool license offers
├── almanac.py               # seasonal goals and yearly difficulty
├── endgame.py               # Legacy, preview, challenge ladder, Everbloom quest
├── worker_prime.py          # worker and Prime harvest logic
├── effects.py               # shared particle and tween helpers
├── props/                   # PNG sprites and image asset README
├── passthegame_audio/       # sound assets and SOURCES.md
└── tests/selftest.py        # headless smoke test
```

## Contributor notes

- Put tunable numbers in `settings.py`.
- Add crop stats and sprite filenames in `plants.py`.
- Add PNGs to `props/` and list them in `props/README.md`.
- Put sound files in `passthegame_audio/`, not `props/`. Add source notes to `passthegame_audio/SOURCES.md`.
- Run `python3 main.py` before opening a PR. For logic changes, also run `python3 tests/selftest.py`.

For the PR workflow, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Contributors log

Add your name and 1-2 lines about what you added below.

- **Nancy**: Created the base sky, sun, cloud, and rain prototype.
- **Minh**: Added farming, seed buying, plant care, harvests, and selling.
- **Danel**: Added night, moon, stars, wind, pausing, a second cloud, and regrowing apple trees.
- **Yousef**: Added early Titans, ground thieves, tools, market modifiers, and more crops.
- **Mohamed**: Added the main menu, tutorial flow, fullscreen mode, and audio asset structure.
- **Noor**: Added a Quit button and pause UI changes.
- **Rawan**: Reworked meters, save/load, auto-save, scarecrow durability, HUD, and seed unlock UI.
- **Funan**: Clarified tutorial controls, added the Main Menu button, and expanded in-game help.
- **Mohammed**: Added animated home-screen props and audio cues under `passthegame_audio/`.
- **Abdulrahman**: Added Almanac progression, five-Titan escalation, Drought/Frost/Inferno, perfect blocks, salted/blighted soil, market balance, golden crops, seasonal juice, crows, mini-bosses, bees, worker/Prime, Legacy, and Everbloom.
