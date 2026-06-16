# ─── Window ───────────────────────────────────────────────────────────────────
TITLE        = "Pass the Game - Farm Patch"
SCREEN_W     = 1200
SCREEN_H     = 600
FPS          = 60
# Simulation time-step safety clamp. Water/sun and all dt-scaled timers multiply
# by the real frame delta, so a long stall (alt-tab, slow asset load) could apply
# a huge step at once and instantly drown/dry crops. Clamp dt to this many seconds
# (about 6 frames at 60 FPS) to keep one slow frame from wrecking the farm.
MAX_FRAME_DT = 0.1
# Display mode. Windowed SCALED uses pixel-perfect integer scaling, so text is
# crisp. FULLSCREEN looks bigger but upscales the 1200x600 buffer by a
# non-integer factor, which softens (blurs) small text. Set False if you prefer
# crisp text over a big fullscreen window.
GAME_FULLSCREEN = True

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
# Cozy ambient wind: after a short idle, clouds gently sway around wherever you
# parked them, instead of drifting endlessly one way (which used to pile both
# clouds against the right edge). WIND_SPEED kept (0 = no net drift) for
# backward compatibility.
WIND_SPEED          = 0.0
WIND_IDLE_DELAY     = 1.5     # seconds of no input before the sway resumes
WIND_SWAY_AMPLITUDE = 16.0    # max px a parked cloud drifts from its anchor
WIND_SWAY_SPEED     = 0.45    # radians/sec of the sway sine
WIND_SWAY_FOLLOW    = 0.06    # per-frame lerp toward the sway target
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

# Market-flooding price decay: every unit of a product sold *today* drives that
# product's effective price down a little (resets each in-game day). This keeps
# monocropping (e.g. selling 200 of one crop) from being the dominant strategy
# while leaving diversified selling almost untouched.
MARKET_DECAY_PER_UNIT = 0.98   # each prior unit sold today multiplies the price
MARKET_DECAY_FLOOR    = 0.40   # decay can't push a unit below 40% of base price

# Market progression shop
MARKET_RARE_SEED_ROTATE_DAYS = 2
MARKET_RARE_SEED_CHANCE = 0.45
MARKET_EVERBLOOM_UNLOCK_COST = 40
TOOL_UNLOCK_COSTS = {
    "compost": 20,
    "scarecrow": 25,
    "lightning_rod": 90,
    "bell": 50,
}

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

# ─── Perfect block (POSITION-BASED, visible reticle) ─────────────────────
# A blocking cloud must be centered within this many px of the target center
# at strike time to count as a Perfect Block (bonus damage).
PERFECT_BLOCK_TOLERANCE_PX = 18
PERFECT_BLOCK_BONUS_DAMAGE = 1
# Shrinking reticle drawn over the target during the warning, so the player can
# learn "center your cloud inside the ring as it locks".
PERFECT_BLOCK_RING_MAX_RADIUS = 64       # radius at warning start
PERFECT_BLOCK_RING_MIN_RADIUS = 16       # radius at strike (~= tolerance)
PERFECT_BLOCK_RING_WIDTH = 4
PERFECT_BLOCK_RING_COLOR = (255, 230, 120)   # "lock" color as the ring closes
# Deprecated: the old timing-based perfect block keyed off rain-toggle. Kept
# defined so any stale import won't break; the boss code no longer reads it.
PERFECT_BLOCK_WINDOW_SECONDS = 0.25

# ─── Combo + clean-fight bonus (boss fights) ─────────────────────────────
BOSS_COMBO_THRESHOLD = 3                 # consecutive blocks before bonus dmg
BOSS_COMBO_DAMAGE_BONUS = 1              # extra dmg per strike once at threshold

# ─── Salted slots (unblocked-hit penalty) ────────────────────────────────
# An unblocked boss strike "salts" the soil: the slot can't be replanted until
# the timer expires. Bigger bosses salt for longer.
STORM_TITAN_SALT_SECONDS = 12.0
CYCLONE_TITAN_SALT_SECONDS = 18.0
SALT_OVERLAY_COLOR = (235, 235, 245)     # pale grains; drawn semi-transparent
SALT_OVERLAY_ALPHA = 120

# ─── No-damage (clean fight) bonus rewards ───────────────────────────────
# Defeating a boss without losing a single plant grants an extra reward.
STORM_TITAN_NODAMAGE_BONUS_ITEM_NAME = "Storm Seed"
STORM_TITAN_NODAMAGE_BONUS_ITEM_COUNT = 1
CYCLONE_TITAN_NODAMAGE_BONUS_ITEM_NAME = "Cyclone Crystal"
CYCLONE_TITAN_NODAMAGE_BONUS_ITEM_COUNT = 1

# ─── Drought Titan (boss) - inverts the mechanic (cover the SUN) ─────────
# Instead of striking a slot with lightning, it overheats the whole farm via
# the sun. Block it by moving a cloud to COVER THE SUN during the warning.
DROUGHT_TITAN_WIDTH = 300
DROUGHT_TITAN_HEIGHT = 150
DROUGHT_TITAN_Y = 24
DROUGHT_TITAN_MAX_HP = 8
DROUGHT_TITAN_SPAWN_EVERY_SECONDS = IN_GAME_WEEK_SECONDS
DROUGHT_TITAN_STRIKE_COOLDOWN_SECONDS = 3.2
DROUGHT_TITAN_STRIKE_WARNING_SECONDS = 1.2     # longer: time to reach the sun
DROUGHT_TITAN_RETREAT_SECONDS = 3.0
# Per unblocked "overheat": applied to EVERY living planted slot.
DROUGHT_TITAN_SUN_SPIKE = 22.0
DROUGHT_TITAN_WATER_DRAIN = 18.0
DROUGHT_TITAN_REWARD_ITEM_NAME = "Sun Shard"
DROUGHT_TITAN_REWARD_ITEM_COUNT = 1
DROUGHT_TITAN_NODAMAGE_BONUS_ITEM_NAME = "Sun Shard"
DROUGHT_TITAN_NODAMAGE_BONUS_ITEM_COUNT = 1
DROUGHT_TITAN_IMAGE_FILENAME = "drought_titan.png"
DROUGHT_TITAN_RING_MAX_RADIUS = 96       # reticle over the sun
DROUGHT_TITAN_RING_MIN_RADIUS = 62       # just outside the sun

# ─── Frost Titan (boss) - winter: MULTI-MARK (paint more slots than 2 clouds) ─
# The 4th seasonal titan. Instead of one strike it marks a contiguous band of
# planted slots wider than the player's two clouds can cover at once, forcing a
# choice of which crops to sacrifice. This is the purest test of the keystone
# (2 clouds, 10 slots). An unblocked mark freezes the slot's growth (cozy, not a
# kill); the game still blights unblocked-hit slots through its existing path.
FROST_TITAN_WIDTH = 300
FROST_TITAN_HEIGHT = 160
FROST_TITAN_Y = 20
FROST_TITAN_MAX_HP = 9
FROST_TITAN_SPAWN_EVERY_SECONDS = IN_GAME_WEEK_SECONDS
FROST_TITAN_STRIKE_COOLDOWN_SECONDS = 3.2
FROST_TITAN_STRIKE_WARNING_SECONDS = 1.3   # a touch longer: react to several marks
FROST_TITAN_RETREAT_SECONDS = 3.5
# How many adjacent planted slots a single strike marks. Two 160px clouds cannot
# cover a band this wide once the field has gaps, so some marks always land.
FROST_TITAN_MARK_COUNT = 3
# An unblocked mark freezes the slot: its growth stalls for this long, on top of
# the blight the game already applies. It does not kill the plant.
FROST_TITAN_FREEZE_SECONDS = 5.0
FROST_TITAN_REWARD_ITEM_NAME = "Charged Crystal"
FROST_TITAN_REWARD_ITEM_COUNT = 1
FROST_TITAN_NODAMAGE_BONUS_ITEM_NAME = "Charged Crystal"
FROST_TITAN_NODAMAGE_BONUS_ITEM_COUNT = 1
FROST_TITAN_IMAGE_FILENAME = "frost_titan.png"

# ─── Boss escalation hook (used by the progression/Almanac system) ───────
# Level 1 == current tuning. set_difficulty(level) scales HP + spawn cadence.
BOSS_DIFFICULTY_HP_PER_LEVEL = 0.25          # +25% max HP per level above 1
BOSS_DIFFICULTY_SPAWN_MULT_PER_LEVEL = 0.95  # spawn interval x0.95 per extra level

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

# Early-game grace. Threat spawns should be quiet while a new player is learning
# the two-cloud puzzle, then reach full density by Year 3.
EARLY_THREAT_GRACE_START_MULT = 0.35
EARLY_THREAT_GRACE_FULL_YEAR = 2.0


def early_threat_grace_scale(year_index=0, season_index=0, seasons_per_year=4):
    """Return 0.35 at Week 1, ramping linearly to 1.0 by Year 3."""
    seasons = max(1, int(seasons_per_year or 4))
    progress_years = max(0.0, float(year_index) + (float(season_index) / float(seasons)))
    ramp = max(0.0, min(1.0, progress_years / float(EARLY_THREAT_GRACE_FULL_YEAR)))
    return float(EARLY_THREAT_GRACE_START_MULT) + (1.0 - float(EARLY_THREAT_GRACE_START_MULT)) * ramp


# Thieves and critters get more frequent as difficulty (the year number) climbs,
# so the field stays threatening in a long game. Each level multiplies their
# spawn chance by this factor (level 1 == base, level 4 == ~1.33x, etc.).
CRITTER_DIFFICULTY_SPAWN_MULT_PER_LEVEL = 1.10

# Auto-harvester worker
WORKER_HIRE_COST = 250
WORKER_SPEED_PX_PER_SEC = 95.0
WORKER_HARVEST_SECONDS = 0.55
WORKER_WIDTH = 34
WORKER_HEIGHT = 50
WORKER_IDLE_AMBLE_SPEED = 42.0   # gentle wander speed when nothing is ripe to harvest
WORKER_SNAKE_KILL_PADDING = 8

# Prime overripen mechanic
PRIME_MAX_BONUS_MULT = 0.50
PRIME_MAX_SECONDS = 24.0
PRIME_DANGER_SECONDS = 30.0
PRIME_SPOIL_SECONDS = 42.0
PRIME_TINT_COLOR = (255, 190, 80)
PRIME_DANGER_COLOR = (235, 80, 80)

# Flying crow thieves and Bell counterplay.
CROW_SPAWN_CHANCE = 1 / 42
CROW_RAID_SPAWN_MULT = 2.5
CROW_MAX_ACTIVE = 4
CROW_WIDTH = 32
CROW_HEIGHT = 22
CROW_SPEED_PX_PER_SEC = 310.0
CROW_FLEE_SPEED_PX_PER_SEC = 380.0
CROW_ALTITUDE_PX = 92
CROW_DIVE_SECONDS = 0.4
CROW_GRAB_BEAT_SECONDS = 0.6
CROW_CLIMB_SECONDS = 0.2
CROW_SCARECROW_PECK_SECONDS = 1.15
CROW_MURDER_MIN_ACTIVE = 3
BELL_COOLDOWN_SECONDS = 8.0
BELL_RING_COST = 8   # gold spent each time you ring the bell (a real, repeatable cost)

# ─── Beneficial day visitors (Honeybee) ───────────────────────────────────
# Bees are NOT pests: they live in a separate list, are never click-scared, and
# only ever HELP. The keystone stays intact because a bee multiplies ONLY the
# in-range (good) growth term: it speeds a crop you have already put in its
# healthy band, and does nothing for a crop that is out of band. It never
# waters or shades, so it cannot substitute for solving the 2-cloud puzzle.
BEE_GROWTH_MULT = 1.25          # in-range growth speed-up while a bee services a flower
BEE_SPAWN_CHANCE = 1 / 9        # per 1.0s check, only while the day/flower gates are met
BEE_MAX_ACTIVE = 2              # cap so bees feel present without swarming
BEE_SERVICE_SECONDS = 5.0       # how long a bee dwells on one flower before roaming
BEE_SPEED_PX_PER_SEC = 150.0    # darting flight between flowers
BEE_ALTITUDE_PX = 70            # how far above the crop tops the bee hovers
BEE_BLOOM_MIN_RATIO = 0.35      # a flower must be at least this grown to attract bees

# ─── Mini-bosses (small, frequent gap-fillers between the titans) ──────────
# These reuse the critter spawn/scare scaffolding. Each is a single ~2-4 second
# interaction that threatens ONE column (or one cloud) at a time, never demands
# both clouds at once, and leaves at most a brief, recoverable debuff (a short
# salt timer, a sun overheat, or a brief growth freeze). None of them set
# slot.dead directly.

# Spawn cadence: a roll is checked at a fixed interval while the field is busy.
# A short cooldown after each spawn keeps them from bunching, and the active cap
# keeps the screen calm (at most 1-2 telegraphs at once).
MINIBOSS_SPAWN_CHECK_SECONDS = 1.0
MINIBOSS_SPAWN_CHANCE = 0.06          # ~1 spawn per 16s of eligible field time
MINIBOSS_SPAWN_COOLDOWN_SECONDS = 8.0  # quiet gap enforced after any spawn
MINIBOSS_MAX_ACTIVE = 2

# A planted crop counts as a "sun-lover" (Glare Mote target) at this sun_min.
MINIBOSS_SUN_LOVER_SUN_MIN = 55.0

# Shared post-resolve puff so a countered/failed mini-boss reads as "done".
MINIBOSS_RESOLVE_FLASH_SECONDS = 0.45

# Burrow Mole: surfaces under a planted slot, shows a shrinking dust ring, and
# salts that slot briefly if it is not clicked in time.
MINIBOSS_MOLE_TELEGRAPH_SECONDS = 2.0
MINIBOSS_MOLE_SALT_SECONDS = 6.0
MINIBOSS_MOLE_SIZE = (46, 38)

# Locust Pair: two locusts fly in from both edges; each clears one crop unless
# clicked. Needs at least this many planted crops to spawn.
MINIBOSS_LOCUST_TELEGRAPH_SECONDS = 2.2
MINIBOSS_LOCUST_SPEED_PX_PER_SEC = 360.0
MINIBOSS_LOCUST_MIN_PLANTED = 2
MINIBOSS_LOCUST_SIZE = (30, 22)

# Glare Mote: a spark of trapped sunlight settles on a sun-lover. Shade the
# column with a cloud to snuff it; otherwise it pushes that crop's sun toward
# this value (overheat). It never sets dead, and it fizzles with no effect if it
# lands where no sun-lover is planted.
MINIBOSS_GLARE_TELEGRAPH_SECONDS = 2.5
MINIBOSS_GLARE_OVERHEAT_SUN = 100.0
# A failed Glare also scorches the soil: an instant chunk of water evaporates and
# the slot keeps drying for a few seconds. This is what makes the mote a real
# threat to every sun-lover (not just the few with sun_max < 100): you must shade
# the column to snuff it, or re-water afterwards. It never sets dead directly.
MINIBOSS_GLARE_SCORCH_SECONDS = 4.0
MINIBOSS_GLARE_SCORCH_WATER_LOSS = 32.0   # instant evaporation on resolve
SCORCH_WATER_DRAIN_PER_SEC = 5.0          # extra drying while the scorch lingers

# Chill Wisp: a pale sheen brushes a band of adjacent columns. Any column not
# covered by a cloud when it resolves has its growth stalled for this long (a
# gentle Frost primer). It never kills.
MINIBOSS_WISP_TELEGRAPH_SECONDS = 2.5
MINIBOSS_WISP_FREEZE_SECONDS = 4.0
MINIBOSS_WISP_BAND_MIN = 2
MINIBOSS_WISP_BAND_MAX = 3

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
# Drizzle is gentle rain, so it also nudges growth a little.
WEATHER_DRIZZLE_GROWTH_MULT = 1.08
# Overcast sky shown while drizzle is active (grayer / less bright than a clear
# day, but kept light enough that it still reads as daytime, not night).
SKY_DRIZZLE = (140, 148, 152)

WEATHER_GUSTS_WIND_MULT = 2.2

# ─── Tools + slot effects ────────────────────────────────────────────────
COMPOST_ITEM_NAME = "Compost"
COMPOST_FROM_DEAD_PLANT = 1
COMPOST_BOOST_SECONDS = 10.0
COMPOST_GROWTH_MULT = 1.35

SCARECROW_COST = 18
SCARECROW_RADIUS_SLOTS = 1

# Daily allowance: a small trickle of coins each new day so a wiped-out player
# (all crops dead, no money, no seeds they can afford) can never be hardlocked.
# Kept tiny on purpose so it is a safety net, not real income (one crop sale
# dwarfs it). Only announced when the player is actually low so it is not noise.
DAILY_STIPEND = 5
DAILY_STIPEND_NOTICE_BELOW = 20
# A placed scarecrow lasts ~3 in-game days, then breaks and must be replaced.
SCARECROW_DURATION_SECONDS = IN_GAME_DAY_SECONDS * 3

LIGHTNING_ROD_COST = 15
LIGHTNING_ROD_CHARGES = 2

# ─── Audio ───────────────────────────────────────────────────────────────
# Real sound files live in passthegame_audio/ and are loaded directly in
# game.py. Repeated one-shots get a small random volume jitter so they don't
# sound like a machine gun.
SFX_ENABLED = True
SFX_VOLUME = 0.35
SFX_VOLUME_JITTER = 0.15   # +/- fraction applied per play

# ─── Game feel / juice ─────────────────────────────────────────────────────
JUICE_ENABLED        = True
MAX_PARTICLES        = 140    # hard cap (oldest dropped); keeps it 60 FPS safe
AMBIENT_MAX          = 30     # separate cap for seasonal ambience (petals/leaves/snow/fireflies)
PARTICLE_GRAVITY     = 520.0  # px/s^2
HARVEST_COIN_COUNT   = 6
HARVEST_LEAF_COUNT   = 6
LEAF_COLOR           = (96, 156, 74)
FLOATTEXT_RISE_SPEED = 34.0   # px/s upward
FLOATTEXT_LIFE       = 1.1    # seconds
POP_LIFE             = 0.26   # seconds; harvest sprite "pop"
POP_OVERSHOOT        = 0.28   # +28% peak scale on the pop

SHAKE_BOSS_MAG       = 6.0    # px, Storm/Drought UNBLOCKED strike
SHAKE_CYCLONE_MAG    = 10.0   # px, Cyclone UNBLOCKED strike (bigger)
SHAKE_BLOCK_MAG      = 2.5    # px, a small bump when a strike is blocked (still an impact)
SHAKE_DURATION       = 0.28   # seconds, linear decay

# Hitstop: freeze the world sim for a few frames on a boss strike so the impact
# reads as weight. Juice (particles, shake, the frozen bolt flash) keeps playing.
HITSTOP_SECONDS      = 0.05   # ~3 frames at 60 FPS, Storm/Drought unblocked
HITSTOP_HEAVY        = 0.09   # ~5 frames, Cyclone unblocked
HITSTOP_BLOCK        = 0.03   # ~2 frames, the crisp little freeze on a block
SHAKE_INTENSITY      = 1.0    # global multiplier; set 0.0 to disable shake (accessibility)

# Warm sunrise/sunset tint; peaks mid day<->night transition, invisible at the
# extremes.
SKY_WARM_TINT        = (255, 150, 96)
SKY_WARM_MAX_ALPHA   = 70
SKY_WARM_CENTER      = 0.5
SKY_WARM_HALFWIDTH   = 0.2

# Cool night colour grading over the field (cached; alpha tracks darkness), plus a
# soft full-screen vignette for cohesion. Both are single cached alpha blits.
SKY_NIGHT_TINT       = (28, 42, 88)
SKY_NIGHT_MAX_ALPHA  = 50
SKY_NIGHT_FIELD_ALPHA = 46   # second cool pass over ground+crops so the field darkens too
VIGNETTE_STRENGTH    = 34

# Soil darkens toward this as a slot's water rises (wet-soil tint).
WET_SOIL_COLOR       = (96, 68, 50)

# Farm Status panel fades to this alpha (0..255) while a cloud is behind it, so
# the player can see what's underneath.
HUD_UNDERCLOUD_ALPHA = 120

# ─── Crop quality (Golden / star crops) ───────────────────────────────────
# A crop kept in its healthy range for at least this fraction of its growing
# life is harvested as a Golden version worth GOLDEN_VALUE_MULT x the base.
STAR_QUALITY_THRESHOLD = 0.85
STAR_MIN_ALIVE_SECONDS = 3.0     # min real growing time before Golden can trigger
GOLDEN_VALUE_MULT = 2
GOLDEN_COIN_BONUS = 6            # extra coin particles on a Golden harvest
GOLDEN_SPARKLE_COUNT = 14       # gold sparkle burst particles
GOLDEN_COLOR = (255, 214, 92)

# ─── Tool indicators ──────────────────────────────────────────────────────
# Truthful scarecrow coverage overlay (uses CRITTER_SCARECROW_AVOID_RADIUS_SLOTS).
SCARECROW_ZONE_COLOR = (235, 205, 110)
SCARECROW_ZONE_ALPHA = 40
SCARECROW_ZONE_ALPHA_ACTIVE = 80   # brighter while the scarecrow tool is held


# Year's End Tempest: during the final season (Winter) the titans converge, so their
# spawn timers run faster, building to the year-end report card. Survive the storm.
TEMPEST_SPAWN_MULT = 1.35
# Endgame / meta progression
# Legacy is persistent farm completion. It never resets the run or grants extra
# clouds. Everbloom is a prestige crop that still obeys normal water and sun bands.
LEGACY_CROP_DISCOVERY_TARGET = 12
LEGACY_TITAN_SURVIVAL_TARGET = 4
LEGACY_GOLDEN_HARVEST_TARGET = 25
LEGACY_BEST_YEAR_TARGET = 5
LEGACY_MONEY_MILESTONES = (100, 500, 1500, 5000)
LEGACY_CHALLENGE_WEIGHT = 10

EVERBLOOM_LEGACY_REQUIRED = 35
EVERBLOOM_DISCOVERED_CROPS_REQUIRED = 8
EVERBLOOM_TOTAL_EARNED_REQUIRED = 1500
EVERBLOOM_SEED_COST = 40
EVERBLOOM_SELL_PRICE = 120
