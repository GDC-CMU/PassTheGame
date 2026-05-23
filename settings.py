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

# ─── Cloud ────────────────────────────────────────────────────────────────────
CLOUD_START_X    = 200
CLOUD_START_Y    = 120
CLOUD_SPEED      = 4          # pixels per frame when arrow key held
CLOUD_USE_IMAGE  = True       # set False to fall back to drawn cloud

# ─── Rain ─────────────────────────────────────────────────────────────────────
RAIN_COLOR       = (130, 170, 220)
RAIN_DROP_COUNT  = 200
RAIN_SPEED_MIN   = 8
RAIN_SPEED_MAX   = 14
RAIN_LENGTH      = 12

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
