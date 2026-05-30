# ─── Window ───────────────────────────────────────────────────────────────────
TITLE        = "Pass the Game - Farm Patch"
SCREEN_W     = 1200
SCREEN_H     = 600
FPS          = 60

# ─── Sky colours ──────────────────────────────────────────────────────────────
SKY_DAY      = (135, 206, 235)   # clear-day blue
SKY_DARK     = (40,  55,  90)    # overcast / sun-covered

# ─── Sun ──────────────────────────────────────────────────────────────────────
SUN_X        = 520
SUN_Y        = 100
SUN_RADIUS   = 55
SUN_COLOR    = (255, 220, 50)

# ─── Moon ──────────────────────────────────────────────────────────────────────
MOON_X        = 520
MOON_Y        = 100
MOON_RADIUS   = 55
MOON_COLOR    = (235, 230, 200)
BITE_OFFSET_X = 18
BITE_OFFSET_Y = -6
BITE_RADIUS_RATIO = 0.85 #relative to MOON_RADIUS

# ─── Stars ──────────────────────────────────────────────────────────────────────
STAR_COLOR        = (240, 240, 220)
STAR_COUNT        = 60
SPARKLING_SPEED     = 2 #rad/sec

# ─── Cloud ────────────────────────────────────────────────────────────────────
CLOUD_START_X    = 700
CLOUD_START_Y    = 150
CLOUD2_START_X   = 200
CLOUD2_START_Y   = 120
CLOUD_SPEED      = 4          # pixels per frame when arrow key held
CLOUD_USE_IMAGE  = True       # set False to fall back to drawn cloud
WIND_SPEED       = 0.4        # wind moves clouds even when player isn't pressing any keys
                              # WIND_SPEED is a delta of num of pixels per frame
# ─── Rain ─────────────────────────────────────────────────────────────────────
RAIN_COLOR       = (130, 170, 220)
RAIN_DROP_COUNT  = 200
RAIN_SPEED_MIN   = 8
RAIN_SPEED_MAX   = 14
RAIN_LENGTH      = 12

# Rain intensity (cloud click cycles Off → Light → Heavy → Off)
# NOTE: RAIN_DROP_COUNT remains as a legacy/default reference value.
RAIN_INTENSITY_OFF = 0
RAIN_INTENSITY_LIGHT = 1
RAIN_INTENSITY_HEAVY = 2

RAIN_LIGHT_DROP_COUNT = 120
RAIN_HEAVY_DROP_COUNT = 260

# ─── Farm layout ───────────────────────────────────────────────────────────────
UI_PANEL_W        = 240
GROUND_HEIGHT_PCT = 0.10
SLOT_COUNT        = 10
SLOT_PADDING      = 6
SLOT_COLOR        = (150, 110, 80)
SLOT_BORDER_COLOR = (110, 80, 60)
GROUND_COLOR      = (115, 85, 65)

# ─── Plant simulation ─────────────────────────────────────────────────────────
WATER_GAIN_RAIN   = 0.15
WATER_LOSS        = 0.05
SUN_GAIN_CLEAR    = 0.15
SUN_LOSS          = 0.07
PLANT_MAX_STAT    = 100.0
OVERWATER_THRESHOLD = 92.0
OVERSUN_THRESHOLD   = 92.0
PLANT_BAD_SECONDS_TO_DIE = 6.0
PLANT_BAD_RECOVERY_RATE = 1.5
PLANT_GROWTH_RATE_GOOD = 1.0
PLANT_GROWTH_RATE_BAD = 0.4
PLANT_SPRITE_W = 64
PLANT_SPRITE_H = 96

# Plant tuning extensions
WATER_GAIN_RAIN_LIGHT = 0.12
WATER_GAIN_RAIN_HEAVY = 0.22
HEAVY_RAIN_GROWTH_MULT = 1.12

# ─── In-game time ────────────────────────────────────────────────────────────
# We use an in-game "week" to schedule the Storm Titan. This is intentionally
# tunable so contributors can make the cadence faster/slower.
IN_GAME_DAY_SECONDS = 60.0
IN_GAME_DAYS_PER_WEEK = 7
IN_GAME_WEEK_SECONDS = IN_GAME_DAY_SECONDS * IN_GAME_DAYS_PER_WEEK

# ─── Seasons (advance once per in-game week) ───────────────────────────────
# Multipliers are indexed by season id.
SEASON_NAMES = ("Spring", "Summer", "Fall", "Winter")
SEASON_GROWTH_MULT = (1.05, 0.95, 1.00, 0.90)
SEASON_WATER_LOSS_MULT = (1.00, 1.20, 1.05, 0.90)
SEASON_SUN_GAIN_MULT = (1.00, 1.10, 0.95, 0.80)

# ─── Market (daily featured/discounted item) ──────────────────────────────
MARKET_FEATURED_MULT = 2.0
MARKET_DISCOUNT_MULT = 0.5

# ─── Storm Titan (boss) ──────────────────────────────────────────────────────
STORM_TITAN_WIDTH = 260
STORM_TITAN_HEIGHT = 130
STORM_TITAN_Y = 32

# 5 reflected blocks defeats the boss.
STORM_TITAN_MAX_HP = 5
# Spawn twice per in-game week.
STORM_TITAN_SPAWN_EVERY_SECONDS = IN_GAME_WEEK_SECONDS / 2

STORM_TITAN_STRIKE_COOLDOWN_SECONDS = 3.0
STORM_TITAN_STRIKE_WARNING_SECONDS = 1.0

# When the boss is defeated it lingers briefly, then leaves.
STORM_TITAN_RETREAT_SECONDS = 3.0

# Reward is delivered as an inventory item the player can plant.
STORM_TITAN_REWARD_ITEM_NAME = "Storm Seed"
STORM_TITAN_REWARD_ITEM_COUNT = 1

# Plant effect for an unblocked strike.
STORM_TITAN_LIGHTNING_KILLS_PLANT = True

# Visuals (fallback drawing if PNGs are missing)
STORM_TITAN_IMAGE_FILENAME = "storm_titan.png"

# ─── Cyclone Titan (boss) ───────────────────────────────────────────────────
CYCLONE_TITAN_WIDTH = 340
CYCLONE_TITAN_HEIGHT = 180
CYCLONE_TITAN_Y = 18

# Bigger boss with a bigger health bar.
CYCLONE_TITAN_MAX_HP = 12
CYCLONE_TITAN_SPAWN_EVERY_SECONDS = IN_GAME_WEEK_SECONDS

CYCLONE_TITAN_STRIKE_COOLDOWN_SECONDS = 2.4
CYCLONE_TITAN_STRIKE_WARNING_SECONDS = 0.9

CYCLONE_TITAN_RETREAT_SECONDS = 3.5

# Unblocked strikes one-shot plants and also hit nearby slots.
CYCLONE_TITAN_AOE_RADIUS_SLOTS = 1

# Visuals (fallback drawing if PNGs are missing)
CYCLONE_TITAN_IMAGE_FILENAME = "cyclone_titan.png"

# ─── Perfect block bonus (boss fights) ───────────────────────────────────
# If the player starts blocking within this window before the strike, it's a
# "perfect block" and deals extra boss damage.
PERFECT_BLOCK_WINDOW_SECONDS = 0.25
PERFECT_BLOCK_BONUS_DAMAGE = 1

# ─── Critters (squirrel/snake) ─────────────────────────────────────────────
# Spawn rolls are checked at a fixed interval while the game is unpaused.
CRITTER_SPAWN_CHECK_SECONDS = 1.0

SQUIRREL_SPAWN_CHANCE = 1 / 20
SQUIRREL_SPEED_PX_PER_SEC = 180.0
SQUIRREL_EAT_SECONDS = 3.0
SQUIRREL_IMAGE_FILENAME = "squirrel.png"

SNAKE_SPAWN_CHANCE = 1 / 50
SNAKE_SPEED_PX_PER_SEC = 240.0
SNAKE_EAT_SECONDS = 4.0
SNAKE_IMAGE_FILENAME = "snake.png"

# ─── Critter drops + behaviors ───────────────────────────────────────────
CHIPMUNK_DROP_ITEM_NAME = "Fur"
CHIPMUNK_DROP_CHANCE = 0.35
CHIPMUNK_DROP_COUNT = 1

SNAKE_DROP_ITEM_NAME = "Venom"
SNAKE_DROP_CHANCE = 0.25
SNAKE_DROP_COUNT = 1

CRITTER_SCARECROW_AVOID_RADIUS_SLOTS = 1

# ─── Weather events (picked at day start) ─────────────────────────────────
# Events are optional; "None" means no active event.
WEATHER_EVENT_NAMES = ("None", "Heatwave", "Drizzle", "Gusts")

# Simple weights used when selecting the day's event.
WEATHER_EVENT_WEIGHTS = {
    "None": 0.55,
    "Heatwave": 0.15,
    "Drizzle": 0.20,
    "Gusts": 0.10,
}

# Default: events last most of the day.
WEATHER_EVENT_DURATION_SECONDS = IN_GAME_DAY_SECONDS * 0.75

WEATHER_HEATWAVE_WATER_LOSS_MULT = 1.35
WEATHER_HEATWAVE_SUN_GAIN_MULT = 1.25

WEATHER_DRIZZLE_WATER_BONUS = 0.06
WEATHER_DRIZZLE_SUN_GAIN_MULT = 0.70

WEATHER_GUSTS_WIND_MULT = 2.2

# ─── Tools + slot effects ────────────────────────────────────────────────
COMPOST_ITEM_NAME = "Compost"
COMPOST_FROM_DEAD_PLANT = 1
COMPOST_BOOST_SECONDS = 10.0
COMPOST_GROWTH_MULT = 1.35

SCARECROW_COST = 18
SCARECROW_RADIUS_SLOTS = 1

LIGHTNING_ROD_COST = 25
LIGHTNING_ROD_CHARGES = 2

# ─── Optional audio (all files live in props/) ───────────────────────────
SFX_ENABLED = True
SFX_VOLUME = 0.35

SFX_HARVEST_FILENAME = "sfx_harvest.ogg"
SFX_BOSS_WARNING_FILENAME = "sfx_boss_warning.ogg"
SFX_BOSS_STRIKE_FILENAME = "sfx_boss_strike.ogg"
SFX_BOSS_BLOCK_FILENAME = "sfx_boss_block.ogg"
SFX_BOSS_PERFECT_BLOCK_FILENAME = "sfx_boss_perfect.ogg"
SFX_CRITTER_SPAWN_FILENAME = "sfx_critter_spawn.ogg"
SFX_CRITTER_SCARE_FILENAME = "sfx_critter_scare.ogg"
