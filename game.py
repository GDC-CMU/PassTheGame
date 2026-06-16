import os
import json
import math
import random
from dataclasses import dataclass
import pygame
from settings import (
    TITLE, SCREEN_W, SCREEN_H, FPS, MAX_FRAME_DT, GAME_FULLSCREEN,
    SKY_DAY, SKY_DARK, SKY_DRIZZLE,
    UI_PANEL_W, GROUND_HEIGHT_PCT, SLOT_COUNT,
    SLOT_PADDING, SLOT_COLOR, SLOT_BORDER_COLOR,
    GROUND_COLOR,
    WATER_GAIN_RAIN_LIGHT, WATER_GAIN_RAIN_HEAVY, WATER_LOSS, SUN_GAIN_CLEAR,
    SUN_LOSS, OVERWATER_THRESHOLD, OVERSUN_THRESHOLD,
    PLANT_BAD_SECONDS_TO_DIE, PLANT_BAD_RECOVERY_RATE,
    PLANT_GROWTH_RATE_GOOD, PLANT_GROWTH_RATE_BAD,
    PLANT_SPRITE_W, PLANT_SPRITE_H,
    HEAVY_RAIN_GROWTH_MULT,
    CLOUD_START_X, CLOUD_START_Y, CLOUD2_START_X, CLOUD2_START_Y,
    IN_GAME_DAY_SECONDS, IN_GAME_DAYS_PER_WEEK,
    SEASON_NAMES,
    SEASON_GROWTH_MULT, SEASON_WATER_LOSS_MULT, SEASON_SUN_GAIN_MULT,
    MARKET_FEATURED_MULT, MARKET_DISCOUNT_MULT,
    MARKET_DECAY_PER_UNIT, MARKET_DECAY_FLOOR,
    WIND_SPEED, WIND_SWAY_AMPLITUDE,
    WEATHER_EVENT_WEIGHTS, WEATHER_EVENT_DURATION_SECONDS,
    WEATHER_HEATWAVE_WATER_LOSS_MULT, WEATHER_HEATWAVE_SUN_GAIN_MULT,
    WEATHER_DRIZZLE_WATER_BONUS, WEATHER_DRIZZLE_SUN_GAIN_MULT, WEATHER_DRIZZLE_GROWTH_MULT,
    WEATHER_GUSTS_WIND_MULT,
    COMPOST_ITEM_NAME, COMPOST_FROM_DEAD_PLANT, COMPOST_BOOST_SECONDS, COMPOST_GROWTH_MULT,
    SCARECROW_COST, SCARECROW_RADIUS_SLOTS, SCARECROW_DURATION_SECONDS,
    LIGHTNING_ROD_COST, LIGHTNING_ROD_CHARGES,
    CRITTER_SCARECROW_AVOID_RADIUS_SLOTS,
    SCARECROW_ZONE_COLOR, SCARECROW_ZONE_ALPHA, SCARECROW_ZONE_ALPHA_ACTIVE,
    GOLDEN_VALUE_MULT, GOLDEN_COIN_BONUS, GOLDEN_SPARKLE_COUNT, GOLDEN_COLOR,
    JUICE_ENABLED, MAX_PARTICLES, AMBIENT_MAX, PARTICLE_GRAVITY,
    HARVEST_COIN_COUNT, HARVEST_LEAF_COUNT, LEAF_COLOR,
    FLOATTEXT_RISE_SPEED, FLOATTEXT_LIFE, POP_LIFE, POP_OVERSHOOT,
    SHAKE_BOSS_MAG, SHAKE_CYCLONE_MAG, SHAKE_BLOCK_MAG, SHAKE_DURATION, SHAKE_INTENSITY,
    HITSTOP_SECONDS, HITSTOP_HEAVY, HITSTOP_BLOCK, BOSS_COMBO_THRESHOLD, TEMPEST_SPAWN_MULT,
    BEE_MAX_ACTIVE, BEE_GROWTH_MULT, PRIME_MAX_SECONDS, BELL_RING_COST,
    CRITTER_DIFFICULTY_SPAWN_MULT_PER_LEVEL,
    early_threat_grace_scale,
    DAILY_STIPEND, DAILY_STIPEND_NOTICE_BELOW,
    SKY_WARM_TINT, SKY_WARM_MAX_ALPHA, SKY_WARM_CENTER, SKY_WARM_HALFWIDTH,
    SKY_NIGHT_TINT, SKY_NIGHT_MAX_ALPHA, SKY_NIGHT_FIELD_ALPHA, VIGNETTE_STRENGTH,
    SFX_VOLUME_JITTER, HUD_UNDERCLOUD_ALPHA,
)
from cloud import Cloud
from sun import Sun
from moon import Moon
from stars import Stars
from farming import PlantSlot, set_wind_factor
from plants import (
    PlantType, Carrot, Lettuce, Tomato, Apple, StormSeed,
    Mushroom, Cactus, Rice, NightBloom, Pumpkin,
    Sunflower, Moonpetal, LightningVine,
    Fern, Reed, Clover, Orchid,
)
from items import ITEMS
from storm_titan import StormTitan
from cyclone_titan import CycloneTitan
from drought_titan import DroughtTitan
from frost_titan import FrostTitan
from finalboss import (
    InfernoTitan, PHASE_CYCLONE, PHASE_DROUGHT, PHASE_FROST, PHASE_INFERNO,
    PHASE_STORM, FIRE_FIRESTORM, FIRE_LAVA, PHASE_COLORS,
)
from minibosses import MiniBossDirector
import minibosses as minibosses_module
from crows import CrowFlock, BellTool
from worker_prime import (
    AutoHarvesterWorker, update_prime_slots, draw_prime_overlays,
    harvest_prime_bonus_to_money, reset_slot_prime,
    prime_save_slots, prime_load_slots, draw_worker_hire_button,
)
from critters import make_squirrel, make_snake, make_bee
from almanac import Almanac, GoalKind, YEAR_UNLOCK_ORDER
from market import (
    MarketState, MarketOffer,
    THREAT_GROUND_CRITTER, THREAT_FLYING_CROW, THREAT_LIGHTNING, THREAT_CROP_DEATH,
    TOOL_TRIGGER_FLAGS,
)
import effects
import ui_theme

PROPS_DIR = os.path.join(os.path.dirname(__file__), "props")
SAVE_PATH = os.path.join(os.path.dirname(__file__), "savegame.json")

# Real-time seconds between automatic saves.
AUTOSAVE_INTERVAL_SECONDS = 120.0

# A just-completed Almanac goal is shown highlighted, then fades out over this
# many seconds, each time the journal is opened.
ALMANAC_COMPLETED_FADE_SECONDS = 2.5

# Tool IDs (kept as strings so the UI/event code stays simple)
TOOL_COMPOST = "compost"
TOOL_SCARECROW = "scarecrow"
TOOL_LIGHTNING_ROD = "lightning_rod"
TOOL_BELL = "bell"

TOOL_ICON_FILENAMES = {
    TOOL_COMPOST: "compost_icon.png",
    TOOL_SCARECROW: "scarecrow_icon.png",
    TOOL_LIGHTNING_ROD: "lightning_rod_icon.png",
    TOOL_BELL: "bell_icon.png",
}

TOOL_HELP = {
    TOOL_COMPOST: "Speeds growth on a planted crop. Uses 1 Compost from inventory.",
    TOOL_SCARECROW: f"Blocks thieves on nearby plots until it breaks. Costs ${SCARECROW_COST}.",
    TOOL_LIGHTNING_ROD: f"Protects one slot from boss lightning. Costs ${LIGHTNING_ROD_COST}.",
    TOOL_BELL: f"Rings a bell that scares off every flying crow at once. Costs ${BELL_RING_COST}, then a short cooldown.",
}
PANEL_SAVE_HELP = "Save your farm now. Auto-save also runs every 2 minutes."
PANEL_SELL_HELP = "Sell all harvested items in Inventory for money."

# Sky Forecast: show the "incoming titan" telegraph this many seconds before it spawns.
SKY_FORECAST_WINDOW_SECONDS = 75.0


@dataclass
class Particle:
    """Short-lived juice: a coin, a leaf, or a scaling sprite "pop"."""
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    life: float = 0.6
    max_life: float = 0.6
    size: int = 3
    color: tuple = (255, 255, 255)
    image: "pygame.Surface | None" = None
    gravity: float = PARTICLE_GRAVITY
    scale_pop: float = 0.0  # >0 = overshoot-then-settle scale tween (the pop)

    def update(self, dt: float) -> None:
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt

    def draw(self, surf: pygame.Surface) -> None:
        t = max(0.0, self.life / self.max_life) if self.max_life > 0 else 0.0
        alpha = int(255 * t)
        if self.image is not None:
            img = self.image
            if self.scale_pop > 0.0:
                p = 1.0 - t
                s = 1.0 + self.scale_pop * math.sin(min(1.0, p) * math.pi)
                w = max(1, int(img.get_width() * s))
                h = max(1, int(img.get_height() * s))
                img = pygame.transform.smoothscale(img, (w, h))
            img = img.copy()
            img.set_alpha(alpha)
            surf.blit(img, img.get_rect(center=(int(self.x), int(self.y))))
        else:
            s = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, alpha), (self.size, self.size), self.size)
            surf.blit(s, (int(self.x - self.size), int(self.y - self.size)))


@dataclass
class FloatText:
    """A small rising, fading label (e.g. "+12g")."""
    x: float
    y: float
    text: str
    color: tuple = (250, 235, 140)
    life: float = FLOATTEXT_LIFE
    max_life: float = FLOATTEXT_LIFE

    def update(self, dt: float) -> None:
        self.y -= FLOATTEXT_RISE_SPEED * dt
        self.life -= dt


class Game:
    """
    Core game loop.  All state lives here; sprites are kept in groups so that
    future contributors can easily add more sprites or layers.
    """

    def __init__(self, new_game: bool = False):
        os.environ.setdefault("SDL_HINT_RENDER_SCALE_QUALITY", "0")  # crisp fullscreen scaling
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.SCALED | (pygame.FULLSCREEN if GAME_FULLSCREEN else 0))
        pygame.display.set_caption(TITLE)
        self.clock  = pygame.time.Clock()
        self.paused = False

        # ── sprites ───────────────────────────────────────────────────────────
        self.sun   = Sun()
        self.moon = Moon()
        self.stars = Stars()
        self._darkness = 0.0

        # ── world time / seasons ───────────────────────────────────────────
        # I only advance world time while unpaused.
        self._rng = random.Random()
        self._world_seconds = 0.0
        self._day_index = 0
        self._week_index = 0
        self._season_index = 0
        self._last_day_index = -1
        self._last_week_index = -1
        self._tempest_active = False   # the Year's End Tempest runs through Winter

        # ── market (daily sell multipliers) ────────────────────────────────
        self._market_featured_item = None
        self._market_discounted_item = None
        self._market = MarketState(self._rng)
        # Units of each product sold so far *today* (drives market-flooding
        # price decay; reset every in-game day in _on_new_day).
        self._units_sold_today: dict[str, int] = {}

        # ── weather events (rolled daily) ─────────────────────────────────
        self._weather_event = "None"
        self._weather_remaining = 0.0
        # Named-weather-day banner: a short non-blocking announcement at each day start.
        self._day_banner_t = 0.0
        self._day_banner_title = ""
        self._day_banner_sub = ""

        # ── boss ─────────────────────────────────────────────────────────────
        self.storm_titan = StormTitan()
        self.cyclone_titan = CycloneTitan()
        self.drought_titan = DroughtTitan()
        self.frost_titan = FrostTitan()
        # The Inferno Titan is the climactic finale: it cycles through all four
        # titans' attack patterns plus its own fire abilities. Disabled until the
        # late game (enabled at difficulty >= 4, then opens the Year's End Tempest).
        self.inferno_titan = InfernoTitan()
        self.inferno_titan.enabled = False
        # Priority order when multiple bosses are ready to spawn (Inferno first).
        self._bosses = [self.inferno_titan, self.cyclone_titan, self.drought_titan, self.frost_titan, self.storm_titan]

        #controls for cloud2
        WASD = {
            "left": pygame.K_a,
            "right": pygame.K_d,
            "up": pygame.K_w,
            "down": pygame.K_s,
        }
        self.clouds = {
            Cloud(start_pos=(CLOUD_START_X, CLOUD_START_Y), control_label="Arrows"),
            Cloud(start_pos=(CLOUD2_START_X, CLOUD2_START_Y), controls=WASD, control_label="WASD"),
        }

        self.all_sprites = pygame.sprite.Group(self.sun, *self.clouds)

        # ── sky transition ────────────────────────────────────────────────────
        self._sky_color = list(SKY_DAY)   # mutable for lerp
        self._font = pygame.font.SysFont("arial", 18)
        self._small_font = pygame.font.SysFont("arial", 16)
        # Bold cuts for the menu-style headers, plaques, and button labels.
        self._font_bold = pygame.font.SysFont("arial", 18, bold=True)
        self._small_bold = pygame.font.SysFont("arial", 15, bold=True)
        self._banner_font = pygame.font.SysFont("arial", 34, bold=True)
        self._head_font = pygame.font.SysFont("arial", 16, bold=True)
        # Reusable cozy-UI motion + frame delta for eased hover/press/fade.
        self._ui_motion = ui_theme.Motion()
        self._ui_dt = 1.0 / float(FPS)
        # Open timestamps for the modal fade-in (reset when a modal closes).
        self._modal_open_at: dict[str, float] = {}
        self._modal_close_at: dict[str, float] = {}
        self._mountain_masks: list[tuple[pygame.Surface, float]] | None = None
        self._mountain_tinted: list[pygame.Surface] = []
        self._mountain_tint_key: tuple | None = None

        # ── farm setup ─────────────────────────────────────────────────────────
        self._ground_height = int(SCREEN_H * GROUND_HEIGHT_PCT)
        self._field_rect = pygame.Rect(0, 0, SCREEN_W - UI_PANEL_W, SCREEN_H)
        self._ground_rect = pygame.Rect(
            0, SCREEN_H - self._ground_height, self._field_rect.width, self._ground_height,
        )

        # ── critters ─────────────────────────────────────────────────────────
        self.squirrel = make_squirrel()
        self.snake = make_snake()
        self._critters = [self.squirrel, self.snake]
        # Honeybees are beneficial day visitors. They live OUTSIDE _critters so a
        # stray click never scares them. The pool size is the active-bee cap.
        self._bees = [make_bee() for _ in range(int(BEE_MAX_ACTIVE))]
        # Mini-bosses: small, frequent, single-column gap-fillers between titans.
        self._minibosses = MiniBossDirector()
        # Flying crow thieves (raid-biased) and the Bell tool that scares them.
        self._crows = CrowFlock()
        self._bell = BellTool()
        # Hireable auto-harvester (harvest-only, snake-killable) + Prime overripen.
        self.auto_worker = AutoHarvesterWorker()
        self._worker_button = pygame.Rect(0, 0, 0, 0)

        # Add new plants by instantiating PlantType subclasses here.
        self.seeds: list[PlantType] = [
            Carrot(), Lettuce(), Tomato(), Apple(), StormSeed(),
            Mushroom(), Cactus(), Rice(), NightBloom(), Pumpkin(),
            Sunflower(), Moonpetal(), LightningVine(),
            Fern(), Reed(), Clover(), Orchid(),
        ]
        self.money = 20
        self._money_display = float(self.money)  # eased value for the number ticker
        self._money_bump = 0.0                   # brief lift/brighten when coins land
        self._hitstop_remaining = 0.0            # freezes world sim on a boss strike
        self._fly_coins: list = []               # coins arcing to the money counter
        self._coin_small: pygame.Surface | None = None  # cached 12px coin for tool costs
        # Cumulative money earned from selling (tracked for stats / migration).
        self._total_earned = 0
        # Seeds the player has purchased the right to plant. Seeds with
        # unlock_at <= 0 are always available; the rest must be bought once.
        self._unlocked_seeds: set[str] = {
            type(s).__name__ for s in self.seeds if int(getattr(s, "unlock_at", 0)) <= 0
        }
        # Cozy progression spine: per-season goals + a yearly capstone.
        self._almanac = Almanac(SEASON_NAMES)
        self._show_almanac = False
        self._show_inventory_overlay = False
        self._show_market_overlay = False
        self._almanac_open_time = 0.0
        self._almanac_seen: set[str] = set()
        self.inventory: dict[str, int] = {}
        self._golden_inventory: dict[str, int] = {}
        self.items = ITEMS
        self.drag_seed: PlantType | None = None
        self.selected_seed: PlantType | None = None
        self.selected_tool = None
        self._seed_buttons: list[tuple[PlantType, pygame.Rect]] = []
        self._locked_seed_buttons: list[tuple[PlantType, pygame.Rect]] = []
        self._seed_icons: dict[str, pygame.Surface] = {}
        self._tool_buttons: list[tuple[str, pygame.Rect]] = []
        self._tool_icons: dict[str, pygame.Surface] = {}
        self._item_icons: dict[str, pygame.Surface] = {}
        self._golden_item_icons: dict[str, pygame.Surface] = {}
        self._plant_phase_icons: dict[str, pygame.Surface] = {}
        self._hover_slot: PlantSlot | None = None
        self._panel_help_lines: list[str] = []
        self._sell_feedback_timer = 0
        self._sell_feedback_msg = ""
        self._sell_button = pygame.Rect(0, 0, 0, 0)
        self._save_button = pygame.Rect(0, 0, 0, 0)
        self._inventory_button = pygame.Rect(0, 0, 0, 0)
        self._market_button = pygame.Rect(0, 0, 0, 0)
        self._inventory_overlay_rect = pygame.Rect(0, 0, 0, 0)
        self._market_overlay_rect = pygame.Rect(0, 0, 0, 0)
        self._almanac_overlay_rect = pygame.Rect(0, 0, 0, 0)
        self._inventory_close_button = pygame.Rect(0, 0, 0, 0)
        self._market_close_button = pygame.Rect(0, 0, 0, 0)
        self._almanac_close_button = pygame.Rect(0, 0, 0, 0)
        self._market_rows: list[tuple[MarketOffer, pygame.Rect]] = []
        self._save_flash_timer = 0
        self._money_flash_timer = 0
        self._ui_panel_image: pygame.Surface | None = None
        self._coin_icon: pygame.Surface | None = None
        self._lock_icon: pygame.Surface | None = None
        self._dead_plant_image: pygame.Surface | None = None
        # sell confirmation UI
        self._pending_sell_total: int | None = None
        self._pending_sell_items: dict[str, int] = {}
        self._show_sell_confirm: bool = False
        self._sell_confirm_buttons: dict[str, pygame.Rect] = {}
        self._inventory_rows: list[tuple[str, bool, pygame.Rect]] = []  # (name, golden, rect)
        # end-of-year report card (modal)
        self._show_report_card = False
        self._pending_report = None
        self._report_queue: list = []
        self._report_card_buttons: dict[str, pygame.Rect] = {}
        self._golden_sparkle_img: pygame.Surface | None = None
        self._warm_glow_surf: pygame.Surface | None = None
        self._night_wash_surf: pygame.Surface | None = None
        self._field_night_surf: pygame.Surface | None = None
        self._ground_surf: pygame.Surface | None = None
        self._wood_panel_cache: dict = {}
        self._shadow_cache: dict = {}
        # seed-unlock purchase confirmation UI
        self._pending_purchase: PlantType | None = None
        self._show_purchase_confirm: bool = False
        self._purchase_confirm_buttons: dict[str, pygame.Rect] = {}
        self._unlocked_tools: set[str] = set()
        # auto-save every AUTOSAVE_INTERVAL_SECONDS of real time
        self._autosave_timer: float = 0.0
        # juice: particles, floating text, screen shake
        self._particles: list[Particle] = []
        self._perfect_flashes: list = []   # [x, y, t0] white pops on a perfect block
        self._ouch_flash_t = 0.0
        self._combo_crossed: dict[int, bool] = {}
        self._boss_arrivals: dict[int, float] = {}
        self._prev_active_boss_ids: set[int] = set()
        self._sfx_debounce: dict[str, float] = {}
        self._prev_bee_active: set[int] = set()
        self._worker_foot_accum = 0.0
        self._ambient: list[Particle] = []     # seasonal ambience pool (own cap)
        self._ambient_accum = 0.0
        self._float_texts: list[FloatText] = []
        self._shake_remaining = 0.0
        self._shake_mag = 0.0
        self._zoom_remaining = 0.0
        self._zoom_dur = 0.12
        self._zoom_mag = 0.0
        self._coin_particle_img: pygame.Surface | None = None
        self._block_rule_label_until: dict[str, float] = {}
        self._seen_block_rules: set[str] = set()

        self.slots = self._create_slots()
        self._load_seed_icons()
        self._load_ui_panel()
        self._load_coin_icon()
        self._load_lock_icon()
        self._load_tool_icons()
        self._load_plant_phases()
        self._load_dead_plant()
        self._build_item_icons()

        # ── SFX ───────────────────────────────────────────────────────────────
        self._sfx_plant: pygame.mixer.Sound | None = None
        _sfx_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "planting.wav")
        if os.path.exists(_sfx_path):
            try:
                self._sfx_plant = pygame.mixer.Sound(_sfx_path)
            except Exception:
                pass
        self._sfx_plant_variants = self._load_sfx_variants("planting")

        self._sfx_harvest: pygame.mixer.Sound | None = None
        _sfx_harvest_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "harvesting.mp3")
        if os.path.exists(_sfx_harvest_path):
            try:
                self._sfx_harvest = pygame.mixer.Sound(_sfx_harvest_path)
                self._sfx_harvest.set_volume(0.5)
            except Exception:
                pass
        self._sfx_harvest_variants = self._load_sfx_variants("harvesting", volume=0.5)

        # Optional sell/coin one-shot (drop passthegame_audio/coin.wav to enable;
        # silent fallback otherwise, matching the load-else-skip convention).
        self._sfx_sell: pygame.mixer.Sound | None = None
        _sfx_sell_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "coin.wav")
        if os.path.exists(_sfx_sell_path):
            try:
                self._sfx_sell = pygame.mixer.Sound(_sfx_sell_path)
                self._sfx_sell.set_volume(0.6)
            except Exception:
                pass
        self._sfx_sell_variants = self._load_sfx_variants("sell", volume=0.6)

        self._sfx_crickets: pygame.mixer.Sound | None = None
        self._crickets_playing = False
        _sfx_crickets_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "crickets.mp3")
        if os.path.exists(_sfx_crickets_path):
            try:
                self._sfx_crickets = pygame.mixer.Sound(_sfx_crickets_path)
                self._sfx_crickets.set_volume(0.5)
            except Exception:
                pass

        self._sfx_nature: pygame.mixer.Sound | None = None
        self._nature_playing = False
        _sfx_nature_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "nature_ambience.mp3")
        if os.path.exists(_sfx_nature_path):
            try:
                self._sfx_nature = pygame.mixer.Sound(_sfx_nature_path)
            except Exception:
                pass

        self._sfx_ready_harvest: pygame.mixer.Sound | None = None
        _sfx_ready_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "ready_to_harvest.mp3")
        if os.path.exists(_sfx_ready_path):
            try:
                self._sfx_ready_harvest = pygame.mixer.Sound(_sfx_ready_path)
            except Exception:
                pass
        self._prev_harvestable: set[int] = set()

        self._sfx_lightning: pygame.mixer.Sound | None = None
        _sfx_lightning_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "lightning.mp3")
        if os.path.exists(_sfx_lightning_path):
            try:
                self._sfx_lightning = pygame.mixer.Sound(_sfx_lightning_path)
            except Exception:
                pass
        self._prev_bolt_flashes: dict[int, float] = {}
        self._prev_warn: dict[int, float] = {}
        # Per-slot seconds of continuous rain, so splash particles only appear
        # after a drop has had time to fall to the ground (not the instant rain starts).
        self._slot_rain_secs: dict[int, float] = {}

        self._sfx_bell: pygame.mixer.Sound | None = None
        _sfx_bell_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "bell.wav")
        if os.path.exists(_sfx_bell_path):
            try:
                self._sfx_bell = pygame.mixer.Sound(_sfx_bell_path)
            except Exception:
                pass

        self._sfx_will_die: pygame.mixer.Sound | None = None
        _sfx_will_die_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "will_die.mp3")
        if os.path.exists(_sfx_will_die_path):
            try:
                self._sfx_will_die = pygame.mixer.Sound(_sfx_will_die_path)
            except Exception:
                pass
        self._prev_shaking: set[int] = set()
        # Three-act death + coexist tracking.
        self._prev_dead: set[int] = set()       # slots already dead last frame
        self._danger_slots: set[int] = set()     # slots deep in Act 2 (recovery window)
        self._coexist_latched = False            # Spring sun+shade goal, once per season
        # Blight (within-season spreading cost from unblocked titan hits).
        self._fight_blight_hits = 0              # unblocked hits in the current boss visit
        self._fight_blight_spreads = 0           # neighbor spreads so far this visit
        self._boss_was_active = False            # rising-edge tracker to reset per-visit counts
        # Boss/crop cues are real WAV assets (built by tools/gen_sfx.py, no numpy at
        # runtime) so they sound the same on every machine; fall back to the numpy
        # synth only if an asset is somehow missing.
        self._sfx_death = self._load_sfx("death.wav") or self._make_tone(98.0, 0.34, kind="thud")
        self._sfx_relief = self._load_sfx("relief.wav") or self._make_tone(660.0, 0.22, kind="chime")
        # Drought has no thunderclap: a rising charge while it warns, then a flare burst.
        self._sfx_drought_windup = self._load_sfx("drought_windup.wav") or self._make_tone(160.0, 0.80, kind="charge", volume=0.45)
        self._sfx_drought_strike = self._load_sfx("drought_strike.wav")
        self._sfx_crow_shoo = self._load_sfx("crow_shoo.wav") or self._make_tone(520.0, 0.12, kind="chime", volume=0.22)
        self._sfx_combo_chime = self._load_sfx("combo_chime.wav") or self._make_tone(880.0, 0.24, kind="chime", volume=0.36)
        self._sfx_ui_click = self._load_sfx("ui_click.ogg")
        self._sfx_ui_open = self._load_sfx("ui_open.ogg")
        self._sfx_ui_close = self._load_sfx("ui_close.ogg")
        self._sfx_ui_error = self._load_sfx("ui_error.ogg")
        self._sfx_seed_select = self._load_sfx("seed_select.ogg")
        self._sfx_rain_toggle = self._load_sfx("rain_toggle.ogg")
        self._sfx_save_confirm = self._load_sfx("save_confirm.ogg")
        self._sfx_purchase_unlock = self._load_sfx("purchase_unlock.ogg")
        self._sfx_tool_place = self._load_sfx("tool_place.ogg")
        self._sfx_worker_hire = self._load_sfx("worker_hire.ogg")
        self._sfx_boss_spawn = self._load_sfx("boss_spawn.ogg")
        self._sfx_boss_block = self._load_sfx("boss_block.ogg")
        self._sfx_perfect_block = self._load_sfx("perfect_block.ogg")
        self._sfx_miniboss_spawn = self._load_sfx("miniboss_spawn.ogg")
        self._sfx_miniboss_counter = self._load_sfx("miniboss_counter.ogg")
        self._sfx_miniboss_resolve_fail = self._load_sfx("miniboss_resolve_fail.ogg")
        self._sfx_critter_spawn = self._load_sfx("critter_spawn.ogg")
        self._sfx_critter_scare = self._load_sfx("critter_scare.ogg")
        self._sfx_critter_steal = self._load_sfx("critter_steal.ogg")
        self._sfx_bee_buzz = self._load_sfx("bee_buzz.wav")
        self._sfx_crow_caw = self._load_sfx("crow_caw.mp3")
        self._sfx_crow_dive_wings = self._load_sfx("crow_dive_wings.mp3")
        self._sfx_crow_grab = self._load_sfx("crow_grab.ogg")
        self._sfx_snake_hiss = self._load_sfx("snake_hiss.wav")
        self._sfx_squirrel_chirp = self._load_sfx("squirrel_chirp.wav")
        self._sfx_new_day = self._load_sfx("new_day.ogg")
        self._sfx_report_card_open = self._load_sfx("report_card_open.ogg")
        self._sfx_report_card_close = self._load_sfx("report_card_close.ogg")
        for snd, vol in (
            (self._sfx_ui_click, 0.26), (self._sfx_ui_open, 0.30), (self._sfx_ui_close, 0.28),
            (self._sfx_ui_error, 0.22), (self._sfx_seed_select, 0.26), (self._sfx_rain_toggle, 0.26),
            (self._sfx_save_confirm, 0.30), (self._sfx_purchase_unlock, 0.34), (self._sfx_tool_place, 0.28),
            (self._sfx_worker_hire, 0.34), (self._sfx_boss_spawn, 0.34), (self._sfx_boss_block, 0.30),
            (self._sfx_perfect_block, 0.34), (self._sfx_miniboss_spawn, 0.30), (self._sfx_miniboss_counter, 0.28),
            (self._sfx_miniboss_resolve_fail, 0.30), (self._sfx_critter_spawn, 0.24),
            (self._sfx_critter_scare, 0.26), (self._sfx_critter_steal, 0.28), (self._sfx_bee_buzz, 0.18),
            (self._sfx_crow_caw, 0.23), (self._sfx_crow_dive_wings, 0.20), (self._sfx_crow_grab, 0.26),
            (self._sfx_snake_hiss, 0.22), (self._sfx_squirrel_chirp, 0.22), (self._sfx_new_day, 0.30),
            (self._sfx_report_card_open, 0.30), (self._sfx_report_card_close, 0.28),
        ):
            if snd is not None:
                snd.set_volume(vol)

        self._sfx_rain: pygame.mixer.Sound | None = None
        self._rain_sfx_playing = False
        _sfx_rain_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "rain.mp3")
        if os.path.exists(_sfx_rain_path):
            try:
                self._sfx_rain = pygame.mixer.Sound(_sfx_rain_path)
                self._sfx_rain.set_volume(0.15)
            except Exception:
                pass

        self._sfx_squirrel: pygame.mixer.Sound | None = None
        self._squirrel_sfx_playing = False
        _sfx_squirrel_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "squirrel.mp3")
        if os.path.exists(_sfx_squirrel_path):
            try:
                self._sfx_squirrel = pygame.mixer.Sound(_sfx_squirrel_path)
            except Exception:
                pass

        self._sfx_snake: pygame.mixer.Sound | None = None
        self._snake_sfx_playing = False
        _sfx_snake_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "snake.mp3")
        if os.path.exists(_sfx_snake_path):
            try:
                self._sfx_snake = pygame.mixer.Sound(_sfx_snake_path)
            except Exception:
                pass

        # ── pause menu buttons ────────────────────────────────────────────────
        self._pause_resume_btn = pygame.Rect(SCREEN_W // 2 - 100, SCREEN_H // 2 - 15, 200, 45)
        self._pause_quit_btn = pygame.Rect(SCREEN_W // 2 - 100, SCREEN_H // 2 + 35, 200, 45)
        self._main_menu_btn = pygame.Rect(self._field_rect.right - 118, 8, 110, 28)

        # New Game starts from the fresh state set up above and overwrites the
        # save slot. Continue loads the existing save (creating one if missing).
        if new_game:
            self.save_game()
            self._save_flash_timer = 0
        else:
            self.load_game()

    # ── main loop ─────────────────────────────────────────────────────────────
    def run(self):
        running = True
        while running:
            self.clock.tick(FPS)

            for event in pygame.event.get():
                if self._show_report_card:
                    # Year-end report card owns all input until dismissed.
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_j):
                        self._dismiss_report_card()
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        btn = self._report_card_buttons.get("dismiss")
                        if btn and btn.collidepoint(event.pos):
                            self._dismiss_report_card()
                    continue
                if event.type == pygame.QUIT:
                    running = False
                elif self._main_menu_button_clicked(event):
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self._close_overlays():
                        continue
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_p:
                    self.paused = not self.paused
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_j:
                    self._toggle_almanac()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                    self._toggle_inventory_overlay()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                    if event.mod & pygame.KMOD_SHIFT:
                        self._give_money_cheat(500)
                    else:
                        self._toggle_market_overlay()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_b:
                    self._toggle_boss(self.storm_titan)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                    self._toggle_boss(self.cyclone_titan)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_x:
                    self._toggle_boss(self.drought_titan)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_f:
                    self._toggle_boss(self.frost_titan)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_i:
                    self._toggle_boss(self.inferno_titan)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_v:
                    self.squirrel.force_spawn(field_rect=self._field_rect, ground_rect=self._ground_rect)
                    self._market.mark_threat(THREAT_GROUND_CRITTER)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_n:
                    self.snake.force_spawn(field_rect=self._field_rect, ground_rect=self._ground_rect)
                    self._market.mark_threat(THREAT_GROUND_CRITTER)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_u:
                    self._unlock_all_cheat()
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    _mb = {pygame.K_1: "mole", pygame.K_2: "locust", pygame.K_3: "glare", pygame.K_4: "vine"}[event.key]
                    self._minibosses.force_spawn(_mb, slots=self.slots, clouds=self.clouds,
                                                 field_rect=self._field_rect, ground_rect=self._ground_rect)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_g:
                    self._crows.force_spawn(slots=self.slots, field_rect=self._field_rect, ground_rect=self._ground_rect)
                    self._market.mark_threat(THREAT_FLYING_CROW)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_t:
                    self._ring_bell()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_h:
                    if self.auto_worker.hire(self):
                        self._play_sfx(self._sfx_worker_hire, key="worker_hire", debounce=0.2)
                    else:
                        self._play_sfx(self._sfx_ui_error, key="worker_hire_error", debounce=0.15)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_o:
                    update_prime_slots(self.slots, PRIME_MAX_SECONDS)

                if self._show_inventory_overlay or self._show_market_overlay:
                    self._handle_farm_event(event)
                    continue

                if not self.paused and self._handle_crow_click(event):
                    continue
                if self._handle_critter_event(event):
                    continue
                if self._handle_miniboss_event(event):
                    continue
                if not self.paused:
                    for c in self.clouds:
                        c.handle_event(event)
                if self.paused:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self._pause_resume_btn.collidepoint(event.pos):
                            self.paused = False
                        if self._pause_quit_btn.collidepoint(event.pos):
                            running = False
                self._handle_farm_event(event)

            self._update()
            self._draw()

        self._stop_ambient_sounds()

    def _stop_ambient_sounds(self):
        if self._sfx_crickets and self._crickets_playing:
            self._sfx_crickets.stop()
            self._crickets_playing = False
        if self._sfx_nature and self._nature_playing:
            self._sfx_nature.stop()
            self._nature_playing = False
        if self._sfx_rain and self._rain_sfx_playing:
            self._sfx_rain.stop()
            self._rain_sfx_playing = False
        if self._sfx_squirrel and self._squirrel_sfx_playing:
            self._sfx_squirrel.stop()
            self._squirrel_sfx_playing = False
        if self._sfx_snake and self._snake_sfx_playing:
            self._sfx_snake.stop()
            self._snake_sfx_playing = False
        if self._sfx_will_die:
            self._sfx_will_die.stop()

    def _load_sfx(self, filename: str):
        """Load a one-shot from passthegame_audio/ if present, else None."""
        try:
            path = os.path.join(os.path.dirname(__file__), "passthegame_audio", filename)
            if os.path.exists(path) and pygame.mixer.get_init():
                return pygame.mixer.Sound(path)
        except Exception:
            pass
        return None

    def _load_sfx_variants(self, prefix: str, count: int = 5, volume: float | None = None):
        """Load prefix_v0..prefix_v{count-1}.wav as pre-pitched one-shot variants so
        repeated actions do not fatigue the ear. Returns [] if none are present, so
        callers fall back to the single sound. Plain WAVs, so runtime stays numpy-free."""
        out = []
        for i in range(count):
            snd = self._load_sfx(f"{prefix}_v{i}.wav")
            if snd is not None:
                if volume is not None:
                    snd.set_volume(volume)
                out.append(snd)
        return out

    def _play_varied(self, variants, single, base_volume: float = 1.0) -> None:
        """Play a random pitch variant (or the single fallback) with volume jitter."""
        snd = self._rng.choice(variants) if variants else single
        if snd is None:
            return
        snd.set_volume(max(0.0, base_volume * (1.0 + self._rng.uniform(-SFX_VOLUME_JITTER, SFX_VOLUME_JITTER))))
        snd.play()

    def _play_sfx(self, snd, *, key: str | None = None, debounce: float = 0.0) -> None:
        if snd is None:
            return
        now = pygame.time.get_ticks() / 1000.0
        if key is not None and debounce > 0.0:
            if now - self._sfx_debounce.get(key, -999.0) < debounce:
                return
            self._sfx_debounce[key] = now
        snd.play()

    def _make_tone(self, freq: float, dur: float, *, kind: str = "thud", volume: float = 0.5):
        """Synthesize a short cue (no audio asset needed). Returns None if unavailable.

        kind="thud" is a low, body-heavy decaying note for a crop dying; "chime" is a
        bright two-note ring for a rescued crop. Built once at startup with numpy.
        """
        try:
            import numpy as np
            init = pygame.mixer.get_init()
            if not init:
                return None
            rate, _size, channels = init
            n = max(1, int(rate * dur))
            t = np.linspace(0.0, dur, n, endpoint=False)
            if kind == "chime":
                wave = 0.6 * np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * freq * 1.5 * t)
                env = np.exp(-4.0 * t)
            elif kind == "charge":
                # Rising heat-shimmer swell: the pitch sweeps up and the volume
                # grows, a telegraph that the Drought Titan is charging its flare.
                sweep = freq * (1.0 + 1.4 * (t / max(dur, 1e-6)))
                phase = 2 * np.pi * np.cumsum(sweep) / float(rate)
                shimmer = 1.0 + 0.12 * np.sin(2 * np.pi * 7.0 * t)
                wave = (np.sin(phase) + 0.3 * np.sin(2.0 * phase)) * shimmer
                ramp = np.clip(t / (0.85 * dur), 0.0, 1.0)
                rel = np.clip((dur - t) / (0.12 * dur), 0.0, 1.0)
                env = ramp * rel
            else:  # thud
                body = np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * freq * 0.5 * t)
                noise = (np.random.RandomState(7).rand(n) - 0.5) * 0.3 * np.exp(-30.0 * t)
                wave = body + noise
                env = np.exp(-9.0 * t)
            samples = (wave * env)
            peak = float(np.max(np.abs(samples))) or 1.0
            samples = (samples / peak) * volume * 32767.0
            samples = samples.astype(np.int16)
            if channels == 2:
                samples = np.column_stack([samples, samples])
            return pygame.sndarray.make_sound(np.ascontiguousarray(samples))
        except Exception:
            return None

    # ── update ────────────────────────────────────────────────────────────────
    def _frame_dt(self) -> float:
        # Real seconds since the last frame, clamped so one slow frame can't apply
        # a giant simulation step (see MAX_FRAME_DT).
        return min(self.clock.get_time() / 1000.0, float(MAX_FRAME_DT))

    def _update(self):
        self.all_sprites.update()

        dt = self._frame_dt()
        self._ui_dt = dt

        # Forget a modal's open-time once it closes so it fades in fresh next time.
        for name, shown in (("purchase", self._show_purchase_confirm),
                            ("sell", self._show_sell_confirm),
                            ("inventory", self._show_inventory_overlay),
                            ("market", self._show_market_overlay),
                            ("almanac", self._show_almanac),
                            ("report", self._show_report_card)):
            if not shown and name not in self._modal_close_at:
                self._modal_open_at.pop(name, None)

        if self._money_flash_timer > 0:
            self._money_flash_timer -= 1
        if self._save_flash_timer > 0:
            self._save_flash_timer -= 1
        if self._sell_feedback_timer > 0:
            self._sell_feedback_timer -= 1

        # Money counter eases toward the real balance (number ticker).
        if self._money_display != self.money:
            self._money_display += (self.money - self._money_display) * min(1.0, 9.0 * dt)
            if abs(self._money_display - self.money) < 0.5:
                self._money_display = float(self.money)
        if self._money_bump > 0.0:
            self._money_bump = max(0.0, self._money_bump - dt * 3.2)
        self._update_fly_coins(dt)

        # Periodic autosave (silent, no "Saved!" flash).
        self._autosave_timer += dt
        if self._autosave_timer >= AUTOSAVE_INTERVAL_SECONDS:
            self._autosave_timer = 0.0
            self.save_game(flash=False)

        if self._day_banner_t > 0.0:
            self._day_banner_t = max(0.0, self._day_banner_t - dt)

        # Update juice (particles, floating text, screen-shake decay).
        if JUICE_ENABLED:
            for p in self._particles:
                p.update(dt)
            self._particles = [p for p in self._particles if p.life > 0.0]
            if len(self._particles) > MAX_PARTICLES:
                self._particles = self._particles[-MAX_PARTICLES:]
            for f in self._float_texts:
                f.update(dt)
            self._float_texts = [f for f in self._float_texts if f.life > 0.0]
            self._shake_remaining = max(0.0, self._shake_remaining - dt)
            self._zoom_remaining = max(0.0, self._zoom_remaining - dt)
            self._ouch_flash_t = max(0.0, self._ouch_flash_t - dt)
            for key in list(self._boss_arrivals.keys()):
                self._boss_arrivals[key] = max(0.0, self._boss_arrivals[key] - dt)
                if self._boss_arrivals[key] <= 0.0:
                    self._boss_arrivals.pop(key, None)
            self._update_ambient(dt)

        # lerp sky colour toward target. A cloud over the sun darkens it most;
        # otherwise drizzle paints a grayer overcast over the clear-day blue.
        if any(c.covers_sun(self.sun.circle_rect) for c in self.clouds):
            target = SKY_DARK
        elif self._weather_event == "Drizzle":
            target = SKY_DRIZZLE
        else:
            target = SKY_DAY
        for i in range(3):
            diff = target[i] - self._sky_color[i]
            self._sky_color[i] += diff * 0.04   # smooth transition speed

        #derive darkness level (uses red)
        denominator = max(1, SKY_DAY[0] - SKY_DARK[0])
        self._darkness = max(0.0, min(1.0, (SKY_DAY[0] - self._sky_color[0])/denominator ))

        if self.paused:
            self._stop_ambient_sounds()
        else:
            if self._sfx_crickets:
                is_night = self._darkness >= 0.5
                if is_night and not self._crickets_playing:
                    self._sfx_crickets.play(-1)
                    self._crickets_playing = True
                elif not is_night and self._crickets_playing:
                    self._sfx_crickets.stop()
                    self._crickets_playing = False

            if self._sfx_nature:
                if not self._crickets_playing and not self._nature_playing:
                    self._sfx_nature.play(-1)
                    self._nature_playing = True
                elif self._crickets_playing and self._nature_playing:
                    self._sfx_nature.stop()
                    self._nature_playing = False

            if self._sfx_rain:
                raining = any(c.raining for c in self.clouds)
                if raining and not self._rain_sfx_playing:
                    self._sfx_rain.play(-1)
                    self._rain_sfx_playing = True
                elif not raining and self._rain_sfx_playing:
                    self._sfx_rain.stop()
                    self._rain_sfx_playing = False

            if self._sfx_squirrel:
                if self.squirrel.active and not self._squirrel_sfx_playing:
                    self._sfx_squirrel.play(-1)
                    self._squirrel_sfx_playing = True
                elif not self.squirrel.active and self._squirrel_sfx_playing:
                    self._sfx_squirrel.stop()
                    self._squirrel_sfx_playing = False

            if self._sfx_snake:
                if self.snake.active and not self._snake_sfx_playing:
                    self._sfx_snake.play(-1)
                    self._snake_sfx_playing = True
                elif not self.snake.active and self._snake_sfx_playing:
                    self._sfx_snake.stop()
                    self._snake_sfx_playing = False

        if self._hitstop_remaining > 0.0:
            self._hitstop_remaining = max(0.0, self._hitstop_remaining - dt)

        if not self.paused and not self._show_report_card and self._hitstop_remaining <= 0.0:
            self._update_world_time(dt)
            self._update_weather(dt)
            self._drain_almanac()

            # Weather can temporarily amplify wind.
            wind_mult = float(WEATHER_GUSTS_WIND_MULT) if self._weather_event == "Gusts" else 1.0
            for c in self.clouds:
                c.sway_amplitude = float(WIND_SWAY_AMPLITUDE) * wind_mult
                c.update_movement(dt)
            # Crops sway harder during Gusts and while a Cyclone is on the field.
            cyclone_active = self.cyclone_titan.state == StormTitan.STATE_ACTIVE
            set_wind_factor(2.0 if (self._weather_event == "Gusts" or cyclone_active) else 1.0)

            self._update_bosses(dt)
            for boss in self._bosses:
                prev = self._prev_bolt_flashes.get(id(boss), 0.0)
                curr = float(getattr(boss, "_bolt_flash_remaining", 0.0))
                if curr > 0.0 and prev == 0.0:
                    if getattr(boss, "plays_lightning_sfx", True):
                        self._market.mark_threat(THREAT_LIGHTNING)
                    if self._sfx_lightning and getattr(boss, "plays_lightning_sfx", True):
                        self._sfx_lightning.play()
                    if boss is self.drought_titan and self._sfx_drought_strike:
                        self._sfx_drought_strike.play()   # sun-flare burst on overheat
                    if JUICE_ENABLED:
                        # A blocked strike is still an impact, so it bumps, but the heavy
                        # slam + long hitstop are reserved for an unblocked, crop-hurting hit.
                        result = getattr(boss, "_last_strike_result", "hit")
                        if result == "hit":
                            self._trigger_shake(SHAKE_CYCLONE_MAG if isinstance(boss, CycloneTitan) else SHAKE_BOSS_MAG)
                            self._ouch_flash_t = max(self._ouch_flash_t, 0.32)
                            self._hitstop_remaining = max(
                                self._hitstop_remaining,
                                HITSTOP_HEAVY if isinstance(boss, CycloneTitan) else HITSTOP_SECONDS,
                            )
                        else:
                            self._play_sfx(self._sfx_perfect_block if result == "perfect" else self._sfx_boss_block,
                                           key=f"boss_block:{id(boss)}", debounce=0.08)
                            self._trigger_shake(SHAKE_BLOCK_MAG)
                            self._hitstop_remaining = max(self._hitstop_remaining, HITSTOP_BLOCK)
                            if result == "perfect":
                                pos = getattr(boss, "_last_perfect_pos", None)
                                if pos is not None:
                                    self._spawn_perfect_block(pos)
                self._prev_bolt_flashes[id(boss)] = curr

                # Drought has no thunderclap; give it a rising charge cue the moment
                # it begins telegraphing a strike, so the player can react by ear.
                warn_prev = self._prev_warn.get(id(boss), 0.0)
                warn_curr = float(getattr(boss, "_warning_remaining", 0.0))
                if ((boss is self.drought_titan or
                     (boss is self.inferno_titan and getattr(boss, "current_phase", None) == PHASE_DROUGHT))
                        and warn_curr > 0.0 and warn_prev <= 0.0
                        and self._sfx_drought_windup):
                    self._sfx_drought_windup.play()
                self._prev_warn[id(boss)] = warn_curr
                combo = int(getattr(boss, "block_combo", 0))
                crossed = bool(self._combo_crossed.get(id(boss), False))
                if combo >= int(BOSS_COMBO_THRESHOLD) and not crossed:
                    self._combo_crossed[id(boss)] = True
                    self._spawn_combo_crossover(boss)
                elif combo < int(BOSS_COMBO_THRESHOLD):
                    self._combo_crossed[id(boss)] = False
            self._update_critters(dt)
            self._update_bees(dt)
            self._crows.set_raid_active(any(b.state == StormTitan.STATE_ACTIVE for b in self._bosses))
            self._crows.update(dt, slots=self.slots, field_rect=self._field_rect, ground_rect=self._ground_rect)
            self._drain_crow_events()
            if any(getattr(c, "active", False) for c in self._critters):
                self._market.mark_threat(THREAT_GROUND_CRITTER)
            if self._crows.active_count > 0:
                self._market.mark_threat(THREAT_FLYING_CROW)
            self._bell.update(dt)
            # Apply the early-game grace to mini-boss spawns too (the director reads
            # the module-level chance), then restore it so nothing else is affected.
            _mb_base = minibosses_module.MINIBOSS_SPAWN_CHANCE
            minibosses_module.MINIBOSS_SPAWN_CHANCE = _mb_base * getattr(self, "_early_threat_grace_scale", 1.0)
            try:
                self._minibosses.update(
                    dt, slots=self.slots, clouds=self.clouds,
                    field_rect=self._field_rect, ground_rect=self._ground_rect,
                )
            finally:
                minibosses_module.MINIBOSS_SPAWN_CHANCE = _mb_base
            self._drain_miniboss_events()
            self._update_plants()
            update_prime_slots(self.slots, dt)
            worker_was_active = self.auto_worker.active
            worker_prev_x = self.auto_worker.x
            self.auto_worker.update(dt, self, ground_pests=self._critters)
            if worker_was_active and self.auto_worker.killed:
                self._play_sfx(self._sfx_miniboss_resolve_fail, key="worker_kill", debounce=0.25)
                self._spawn_worker_kill_juice(self.auto_worker.rect.center)
            elif self.auto_worker.active and worker_prev_x is not None and self.auto_worker.x is not None:
                moved = abs(float(self.auto_worker.x) - float(worker_prev_x))
                if moved > 0.01:
                    self._worker_foot_accum += moved
                    if self._worker_foot_accum >= 24.0:
                        self._worker_foot_accum = 0.0
                        self._spawn_worker_foot_dust(self.auto_worker.rect.midbottom)
        self.stars.update(dt)

    def _update_world_time(self, dt: float) -> None:
        if dt <= 0.0:
            return

        self._world_seconds += dt
        day_index = int(self._world_seconds // float(IN_GAME_DAY_SECONDS))
        week_index = int(day_index // int(IN_GAME_DAYS_PER_WEEK))

        self._day_index = day_index
        if day_index != self._last_day_index:
            self._last_day_index = day_index
            self._on_new_day(day_index)

        if week_index != self._week_index:
            prev_year = self._week_index // len(SEASON_NAMES) if SEASON_NAMES else 0
            self._week_index = week_index
            if SEASON_NAMES:
                self._season_index = week_index % len(SEASON_NAMES)
            else:
                self._season_index = 0
            self._on_new_week(week_index, prev_year)

    def _roll_market_for_day(self) -> None:
        # Pick a daily featured item and a discounted item from sellable items.
        sellable: list[str] = [
            name for name, item in self.items.items() if int(getattr(item, "sell_price", 0)) > 0
        ]
        if len(sellable) < 2:
            self._market_featured_item = None
            self._market_discounted_item = None
            return

        featured = self._rng.choice(sellable)
        discounted_pool = [n for n in sellable if n != featured]
        discounted = self._rng.choice(discounted_pool) if discounted_pool else None

        self._market_featured_item = featured
        self._market_discounted_item = discounted
        self._market.roll_daily_stock(self._day_index, self.seeds, self._unlocked_seeds)

    def _on_new_day(self, day_index: int, grant_stipend: bool = True) -> None:
        # I keep daily rolls in one place so future systems can hook in cleanly.
        # The stipend is skipped when this runs from a save load (no real new day).
        if grant_stipend:
            self._grant_daily_stipend()
        self._roll_market_for_day()
        self._roll_weather_for_day(day_index)
        # Fresh market each day: flooding decay resets.
        self._units_sold_today.clear()
        self._announce_day(day_index)
        if grant_stipend:
            self._play_sfx(self._sfx_new_day, key="new_day", debounce=0.5)

    def _grant_daily_stipend(self) -> None:
        # A small daily allowance so a broke, wiped-out player can always afford to
        # replant and is never hardlocked. Announced only when low, to avoid noise.
        was_low = self.money < int(DAILY_STIPEND_NOTICE_BELOW)
        self.money += int(DAILY_STIPEND)
        if was_low and JUICE_ENABLED:
            self._float_texts.append(FloatText(
                self._field_rect.width + 150, 110, f"+{int(DAILY_STIPEND)}g", color=(196, 232, 168)))

    def _announce_day(self, day_index: int) -> None:
        # A short non-blocking banner naming the day's weather, so each day has a
        # character the player notices ("Scorcher", "Rainy Day").
        names = {
            "None": ("Clear Skies", "A calm day on the farm."),
            "Heatwave": ("Scorcher", "Blazing hot. Sun-lovers thrive, water drains fast."),
            "Drizzle": ("Rainy Day", "Gentle rain waters the whole field."),
            "Gusts": ("Blustery", "Strong winds buffet your clouds."),
        }
        title, sub = names.get(self._weather_event, ("Clear Skies", ""))
        self._day_banner_title = title
        self._day_banner_sub = sub
        self._day_banner_t = 4.0

    def _on_new_week(self, week_index: int, prev_year: int) -> None:
        # Activate the new season's goals, then fire any year capstones we
        # crossed (loop handles large dt skips safely).
        self._almanac.set_season(self._season_index)
        self._coexist_latched = False
        # Blight is a within-season cost: a fresh season heals the whole field.
        for slot in self.slots:
            if hasattr(slot, "clear_blight"):
                slot.clear_blight()
        seasons = len(SEASON_NAMES) if SEASON_NAMES else 4
        new_year = week_index // seasons
        for y in range(prev_year + 1, new_year + 1):
            self._apply_year_capstone(self._almanac.on_year_boundary(y))
        # Refresh the early-game grace each week so the first-year ramp is gradual.
        self._apply_threat_difficulty(int(getattr(self._almanac, "difficulty", 1)))

        # The Year's End Tempest runs through the final season (Winter): the titans
        # converge and spawn faster. Announce it (overriding the weather banner).
        was_tempest = self._tempest_active
        self._tempest_active = (self._season_index == seasons - 1)
        if self._tempest_active and not was_tempest:
            self._day_banner_title = "Year's End Tempest"
            self._day_banner_sub = "The titans converge. Survive to the new year."
            self._day_banner_t = 5.0
            # Once unlocked, the Inferno Titan opens the Tempest as its finale.
            if self.inferno_titan.enabled and not getattr(self.inferno_titan, "visible", False):
                self._toggle_boss(self.inferno_titan)
            for boss in self._bosses:
                if hasattr(boss, "enabled"):
                    boss.enabled = True

    def _apply_threat_difficulty(self, level: int) -> None:
        """Scale thieves and crows with the difficulty level so a long game keeps
        getting more dangerous (bosses are scaled separately via set_difficulty).
        An early-game grace softens the very first weeks so a new player can learn,
        then ramps to full strength over the first couple of years."""
        level = max(1, int(level))
        grace = early_threat_grace_scale(
            int(getattr(self._almanac, "year_index", 0)),
            int(getattr(self, "_season_index", 0)),
            len(SEASON_NAMES) if SEASON_NAMES else 4,
        )
        self._early_threat_grace_scale = float(grace)
        scale = (float(CRITTER_DIFFICULTY_SPAWN_MULT_PER_LEVEL) ** (level - 1)) * float(grace)
        for critter in self._critters:
            setter = getattr(critter, "set_spawn_scale", None)
            if callable(setter):
                setter(scale)
        self._crows.set_difficulty_scale(scale)

    def _apply_year_capstone(self, cap) -> None:
        if cap is None:
            return
        if cap.money:
            self.money += int(cap.money)
        # Guaranteed crop drip: unlock the first tier crop not yet owned.
        for name in YEAR_UNLOCK_ORDER:
            if name not in self._unlocked_seeds:
                self._unlocked_seeds.add(name)
                break
        # New year: let next year's completed goals re-announce in the journal.
        self._almanac_seen.clear()
        # Escalate bosses to match the new difficulty level.
        for boss in self._bosses:
            setter = getattr(boss, "set_difficulty", None)
            if callable(setter):
                setter(int(cap.new_difficulty))
        self._apply_threat_difficulty(int(cap.new_difficulty))
        # The Inferno Titan finale unlocks in the late game.
        self.inferno_titan.enabled = int(cap.new_difficulty) >= 4
        self.save_game(flash=False)
        self._queue_report_card(cap)

    def _queue_report_card(self, cap) -> None:
        self._report_queue.append(cap)
        if not self._show_report_card:
            self._promote_report_card()

    def _promote_report_card(self) -> None:
        if self._report_queue:
            self._pending_report = self._report_queue.pop(0)
            self._show_report_card = True
            self._play_sfx(self._sfx_report_card_open, key="report_open", debounce=0.2)
        else:
            self._pending_report = None
            self._show_report_card = False

    def _dismiss_report_card(self) -> None:
        self._play_sfx(self._sfx_report_card_close, key="report_close", debounce=0.2)
        self._promote_report_card()

    def _drain_almanac(self) -> None:
        # Apply queued goal rewards and surface celebration toasts.
        rewarded = False
        for c in self._almanac.pop_rewards():
            r = c.reward
            if r.money:
                self.money += int(r.money)
            if r.item_name and r.item_count:
                self.inventory[r.item_name] = self.inventory.get(r.item_name, 0) + int(r.item_count)
            if r.unlock_seed:
                self._unlocked_seeds.add(r.unlock_seed)
            rewarded = True
        for msg in self._almanac.pop_celebrations():
            self._show_sell_feedback(msg)
        # Persist immediately so a reload can't re-grant the same rewards.
        if rewarded:
            self.save_game(flash=False)
            if JUICE_ENABLED:
                self._spawn_celebration()

    def _spawn_perfect_block(self, pos) -> None:
        # A crisp white pop plus a radial spark burst at the spot a perfect block
        # landed, so the highest-skill moment gets a kinetic payoff.
        if not JUICE_ENABLED:
            return
        x, y = int(pos[0]), int(pos[1])
        self._perfect_flashes.append([x, y, pygame.time.get_ticks() / 1000.0])
        for _ in range(12):
            ang = self._rng.uniform(0.0, math.tau)
            spd = self._rng.uniform(120.0, 260.0)
            self._particles.append(Particle(
                x, y, vx=math.cos(ang) * spd, vy=math.sin(ang) * spd,
                life=0.25, max_life=0.25, size=self._rng.randint(2, 3),
                color=(255, 248, 200), gravity=0.0))
        if len(self._particles) > MAX_PARTICLES:
            self._particles = self._particles[-MAX_PARTICLES:]

    def _spawn_celebration(self) -> None:
        # A gold sparkle burst near the Almanac/Farm Status corner on a goal reward.
        cx, cy = 90, 120
        for _ in range(int(GOLDEN_SPARKLE_COUNT)):
            self._particles.append(Particle(
                cx + self._rng.uniform(-30, 30), cy,
                vx=self._rng.uniform(-90, 90), vy=self._rng.uniform(-170, -40),
                life=1.0, max_life=1.0, image=self._golden_sparkle_img,
                color=GOLDEN_COLOR, size=self._rng.randint(2, 4)))

    def _roll_weather_for_day(self, day_index: int) -> None:
        # Weighted random pick from WEATHER_EVENT_WEIGHTS.
        # day_index is currently unused, but I keep it here so later contributors
        # can do day-based patterns if they want.
        _ = day_index

        total = 0.0
        for w in WEATHER_EVENT_WEIGHTS.values():
            total += max(0.0, float(w))
        if total <= 0.0:
            self._weather_event = "None"
            self._weather_remaining = 0.0
            return

        roll = self._rng.random() * total
        acc = 0.0
        chosen = "None"
        for name, w in WEATHER_EVENT_WEIGHTS.items():
            acc += max(0.0, float(w))
            if roll <= acc:
                chosen = str(name)
                break

        self._weather_event = chosen
        self._weather_remaining = float(WEATHER_EVENT_DURATION_SECONDS) if chosen != "None" else 0.0

    def _update_weather(self, dt: float) -> None:
        if dt <= 0.0:
            return
        if self._weather_event == "None":
            return
        self._weather_remaining = max(0.0, self._weather_remaining - dt)
        if self._weather_remaining <= 0.0:
            self._weather_event = "None"

    def _market_mult_for_item(self, name: str) -> float:
        if self._market_featured_item and name == self._market_featured_item:
            return float(MARKET_FEATURED_MULT)
        if self._market_discounted_item and name == self._market_discounted_item:
            return float(MARKET_DISCOUNT_MULT)
        return 1.0

    def _market_decay_for_unit(self, units_before: int) -> float:
        # Each unit already sold today pushes the next unit's price down a bit,
        # bottoming out at MARKET_DECAY_FLOOR of the base price.
        return max(float(MARKET_DECAY_FLOOR), float(MARKET_DECAY_PER_UNIT) ** max(0, int(units_before)))

    def _sale_value_for(self, name, qty, *, golden=False, commit=False) -> int:
        # Price qty units of one product at current market rate with per-unit
        # flooding decay (golden units priced at GOLDEN_VALUE_MULT x base).
        item = self.items.get(name)
        if not item or qty <= 0:
            return 0
        market_mult = self._market_mult_for_item(name)
        if golden:
            market_mult *= float(GOLDEN_VALUE_MULT)
        prior = self._units_sold_today.get(name, 0)
        total = 0
        for i in range(int(qty)):
            decay = self._market_decay_for_unit(prior + i)
            total += max(1, int(round(item.sell_price * market_mult * decay)))
        if commit:
            self._units_sold_today[name] = prior + int(qty)
        return total

    def _compute_sale_total(self, *, commit: bool) -> int:
        # Normal + golden units of each product share one flooding counter; the
        # normal units price first, golden units continue the same decay curve.
        total = 0
        names = set(self.inventory) | set(self._golden_inventory)
        for name in names:
            item = self.items.get(name)
            if not item:
                continue
            normal = max(0, int(self.inventory.get(name, 0)))
            golden = max(0, int(self._golden_inventory.get(name, 0)))
            if normal + golden <= 0:
                continue
            market_mult = self._market_mult_for_item(name)
            prior = self._units_sold_today.get(name, 0)
            unit = 0
            for _ in range(normal):
                total += max(1, int(round(item.sell_price * market_mult * self._market_decay_for_unit(prior + unit))))
                unit += 1
            for _ in range(golden):
                total += max(1, int(round(item.sell_price * GOLDEN_VALUE_MULT * market_mult * self._market_decay_for_unit(prior + unit))))
                unit += 1
            if commit:
                self._units_sold_today[name] = prior + normal + golden
        return total

    def _trigger_shake(self, mag: float) -> None:
        base = self._shake_mag if self._shake_remaining > 0.0 else 0.0
        self._shake_mag = max(base, float(mag))
        self._shake_remaining = float(SHAKE_DURATION)

    def _trigger_zoom(self, mag: float = 0.05) -> None:
        self._zoom_mag = max(self._zoom_mag if self._zoom_remaining > 0.0 else 0.0, float(mag))
        self._zoom_remaining = float(self._zoom_dur)

    def _apply_screen_shake(self) -> None:
        if not JUICE_ENABLED or SHAKE_INTENSITY <= 0.0:
            return
        # A zoom punch takes precedence over shake so the two never stack (nausea).
        if self._zoom_remaining > 0.0:
            prog = self._zoom_remaining / max(1e-6, self._zoom_dur)
            z = 1.0 + self._zoom_mag * effects.ease_out_quad(prog)
            try:
                field = self.screen.subsurface(self._field_rect).copy()
            except (ValueError, pygame.error):
                return
            fw, fh = self._field_rect.size
            sw, sh = max(1, int(fw * z)), max(1, int(fh * z))
            scaled = pygame.transform.scale(field, (sw, sh))
            prev_clip = self.screen.get_clip()
            self.screen.set_clip(self._field_rect)
            self.screen.blit(scaled, (self._field_rect.left - (sw - fw) // 2,
                                      self._field_rect.top - (sh - fh) // 2))
            self.screen.set_clip(prev_clip)
            return
        if self._shake_remaining <= 0.0:
            return
        # Eased falloff (trauma-like) plus a smooth summed-sine offset, so the shake
        # reads as an organic jolt rather than a jittery per-frame vibration.
        decay = (self._shake_remaining / float(SHAKE_DURATION)) ** 1.5
        amp = self._shake_mag * decay * float(SHAKE_INTENSITY)
        t = pygame.time.get_ticks() * 0.001
        ox = int(amp * (math.sin(t * 38.0) * 0.6 + math.sin(t * 23.0) * 0.4))
        oy = int(amp * (math.sin(t * 41.0 + 1.7) * 0.6 + math.sin(t * 29.0 + 0.5) * 0.4))
        if ox == 0 and oy == 0:
            return
        try:
            field = self.screen.subsurface(self._field_rect).copy()
        except (ValueError, pygame.error):
            return
        # Repaint the exposed band with sky, then re-blit the field offset. The
        # UI panel/HUD are drawn afterward, so they never shake.
        self.screen.fill(tuple(int(c) for c in self._sky_color), self._field_rect)
        self.screen.blit(field, (ox, oy))

    def _draw_particles(self, surf: pygame.Surface) -> None:
        for p in self._particles:
            p.draw(surf)

    def _update_ambient(self, dt: float) -> None:
        # Drift + cull the seasonal ambience, then top it up at a season-based rate.
        fw = self._field_rect.width
        for p in self._ambient:
            p.update(dt)
        self._ambient = [p for p in self._ambient
                         if p.life > 0.0 and -24 <= p.x <= fw + 24 and p.y <= SCREEN_H + 24]
        interval, factory = self._ambient_spawn_spec()
        if interval <= 0.0 or factory is None:
            self._ambient_accum = 0.0
            return
        self._ambient_accum += dt
        while self._ambient_accum >= interval:
            self._ambient_accum -= interval
            if len(self._ambient) < AMBIENT_MAX:
                self._ambient.append(factory())

    def _ambient_spawn_spec(self):
        # Returns (seconds-between-spawns, factory) for the current season / time.
        fw = self._field_rect.width
        gy = self._ground_rect.top
        rng = self._rng

        if self._darkness > 0.6:  # fireflies at night, any season
            def firefly():
                ml = rng.uniform(2.6, 4.6)
                img = effects.radial_glow(5, (255, 232, 130), 150)
                return Particle(rng.uniform(20, fw - 20), rng.uniform(gy - 130, gy + 12),
                                vx=rng.uniform(-13, 13), vy=rng.uniform(-11, 6),
                                life=ml, max_life=ml, image=img, gravity=0.0)
            return (0.5, firefly)

        season = self._season_index % 4
        if season == 0:  # spring petals
            def petal():
                return Particle(rng.uniform(0, fw), -8.0,
                                vx=rng.uniform(-16, 6), vy=rng.uniform(16, 26),
                                life=16.0, max_life=16.0, color=(245, 182, 206),
                                size=rng.randint(2, 3), gravity=0.0)
            return (0.55, petal)
        if season == 1:  # summer pollen motes drifting up
            def mote():
                return Particle(rng.uniform(0, fw), rng.uniform(gy - 150, gy),
                                vx=rng.uniform(-9, 9), vy=rng.uniform(-11, -2),
                                life=5.5, max_life=5.5, color=(250, 240, 178),
                                size=2, gravity=0.0)
            return (0.7, mote)
        if season == 2:  # fall leaves
            def leaf():
                col = rng.choice([(214, 124, 52), (196, 96, 40), (182, 142, 60)])
                return Particle(rng.uniform(0, fw), -8.0,
                                vx=rng.uniform(-24, 10), vy=rng.uniform(18, 30),
                                life=14.0, max_life=14.0, color=col,
                                size=rng.randint(3, 4), gravity=0.0)
            return (0.5, leaf)

        def snow():  # winter
            return Particle(rng.uniform(0, fw), -8.0,
                            vx=rng.uniform(-11, 11), vy=rng.uniform(10, 20),
                            life=18.0, max_life=18.0, color=(238, 244, 255),
                            size=rng.randint(2, 3), gravity=0.0)
        return (0.45, snow)

    def _draw_ambient(self, surf: pygame.Surface) -> None:
        for p in self._ambient:
            p.draw(surf)

    def _draw_drizzle_rain(self, surf: pygame.Surface) -> None:
        # "Rainy Day" (Drizzle) should actually look rainy: a gentle translucent
        # sheet of falling streaks across the field, matching the weather banner.
        if self._weather_event != "Drizzle":
            return
        fw = self._field_rect.width
        if getattr(self, "_drizzle_surf", None) is None or self._drizzle_surf.get_width() != fw:
            self._drizzle_surf = pygame.Surface((fw, SCREEN_H), pygame.SRCALPHA)
        rain = self._drizzle_surf
        rain.fill((0, 0, 0, 0))
        t = pygame.time.get_ticks() / 1000.0
        col = (158, 198, 236, 115)
        span = SCREEN_H + 60
        for i in range(48):
            x = (i * 167) % fw
            speed = 300 + (i * 53) % 150
            phase = (i * 97) % span
            y = (t * speed + phase) % span - 30
            pygame.draw.line(rain, col, (x, y), (x - 3, y + 11), 1)
        surf.blit(rain, (0, 0))

    def _draw_float_texts(self, surf: pygame.Surface) -> None:
        for f in self._float_texts:
            a = max(0, int(255 * f.life / f.max_life)) if f.max_life > 0 else 0
            s = self._small_font.render(f.text, True, f.color)
            s.set_alpha(a)
            sh = self._small_font.render(f.text, True, (20, 20, 20))
            sh.set_alpha(a)
            surf.blit(sh, sh.get_rect(center=(int(f.x) + 1, int(f.y) + 1)))
            surf.blit(s, s.get_rect(center=(int(f.x), int(f.y))))

    def _spawn_harvest_juice(self, slot: PlantSlot, seed: PlantType, *, golden: bool = False) -> None:
        cx, cy = slot.rect.center
        img = self._phase_image_for_slot(slot)  # capture before clear/regrow
        if img is not None:
            self._particles.append(Particle(cx, cy, vy=-40.0, life=POP_LIFE, max_life=POP_LIFE,
                                            image=img, gravity=0.0, scale_pop=POP_OVERSHOOT))
        for _ in range(int(HARVEST_COIN_COUNT)):
            self._particles.append(Particle(
                cx, cy, vx=self._rng.uniform(-70, 70), vy=self._rng.uniform(-210, -120),
                life=0.7, max_life=0.7, image=self._coin_particle_img, size=4))
        for _ in range(int(HARVEST_LEAF_COUNT)):
            self._particles.append(Particle(
                cx, cy, vx=self._rng.uniform(-90, 90), vy=self._rng.uniform(-150, -60),
                life=0.6, max_life=0.6, color=LEAF_COLOR, size=self._rng.randint(2, 4)))
        if golden:
            # A juicy golden burst (no screen zoom): extra gold sparkles flying out.
            gx, gy = slot.rect.centerx, slot.rect.bottom - 16
            for _ in range(int(GOLDEN_SPARKLE_COUNT) * 2):
                ang = self._rng.uniform(0.0, math.tau)
                spd = self._rng.uniform(60.0, 200.0)
                self._particles.append(Particle(
                    gx, gy, vx=math.cos(ang) * spd, vy=math.sin(ang) * spd - 60.0,
                    life=self._rng.uniform(0.6, 1.0), max_life=1.0,
                    image=self._golden_sparkle_img, color=GOLDEN_COLOR,
                    size=self._rng.randint(2, 4), gravity=0.0))
            for _ in range(int(GOLDEN_SPARKLE_COUNT)):
                self._particles.append(Particle(
                    cx, cy, vx=self._rng.uniform(-120, 120), vy=self._rng.uniform(-210, -40),
                    life=0.9, max_life=0.9, image=self._golden_sparkle_img,
                    color=GOLDEN_COLOR, size=self._rng.randint(2, 4)))
            for _ in range(int(GOLDEN_COIN_BONUS)):
                self._particles.append(Particle(
                    cx, cy, vx=self._rng.uniform(-80, 80), vy=self._rng.uniform(-230, -130),
                    life=0.8, max_life=0.8, image=self._coin_particle_img, size=4))
            self._float_texts.append(FloatText(
                slot.rect.centerx, slot.rect.top - 10,
                f"+{seed.harvest_yield} Golden {seed.product_name}", color=GOLDEN_COLOR))
        else:
            self._float_texts.append(FloatText(
                slot.rect.centerx, slot.rect.top - 10,
                f"+{seed.harvest_yield} {seed.product_name}", color=(235, 245, 225)))

    def _spawn_plant_juice(self, slot: PlantSlot, seed: PlantType) -> None:
        # A satisfying soil burst from the base (no duplicate sprite, which used to
        # leave a ghost seedling floating over the real plant).
        cx = slot.rect.centerx
        by = slot.rect.bottom - 6
        for _ in range(11):
            self._particles.append(Particle(
                cx + self._rng.uniform(-10, 10), by,
                vx=self._rng.uniform(-75, 75), vy=self._rng.uniform(-135, -45),
                life=self._rng.uniform(0.4, 0.6), max_life=0.6,
                color=(122, 92, 66), size=self._rng.randint(2, 4)))

    def _spawn_ready_sparkle(self, slot: PlantSlot) -> None:
        # A one-shot green sparkle when a crop first becomes harvestable.
        trigger = getattr(slot, "trigger_ready_pop", None)
        if callable(trigger):
            trigger()
        cx = slot.rect.centerx
        ty = slot.rect.top + 6
        for _ in range(7):
            self._particles.append(Particle(
                cx + self._rng.uniform(-12, 12), ty,
                vx=self._rng.uniform(-40, 40), vy=self._rng.uniform(-130, -55),
                life=0.7, max_life=0.7, color=(150, 230, 150), size=self._rng.randint(2, 3)))

    def _spawn_rain_splash(self, slot: PlantSlot) -> None:
        cx = slot.rect.centerx + self._rng.uniform(-slot.rect.width * 0.28, slot.rect.width * 0.28)
        y = slot.rect.bottom - self._rng.uniform(8, 20)
        for _ in range(3):
            self._particles.append(Particle(
                cx, y,
                vx=self._rng.uniform(-34, 34), vy=self._rng.uniform(-52, -20),
                life=0.28, max_life=0.28, color=(112, 178, 238), size=self._rng.randint(1, 2),
                gravity=180.0))

    def _cap_particles(self) -> None:
        if len(self._particles) > MAX_PARTICLES:
            self._particles = self._particles[-MAX_PARTICLES:]

    def _burst(self, pos, count: int, colors, *, vx=(-80, 80), vy=(-120, -35), life=(0.35, 0.65),
               size=(2, 4), gravity=160.0) -> None:
        if not JUICE_ENABLED:
            return
        x, y = pos
        palette = tuple(colors)
        for _ in range(int(count)):
            ml = self._rng.uniform(float(life[0]), float(life[1]))
            self._particles.append(Particle(
                x + self._rng.uniform(-7, 7), y + self._rng.uniform(-5, 5),
                vx=self._rng.uniform(float(vx[0]), float(vx[1])),
                vy=self._rng.uniform(float(vy[0]), float(vy[1])),
                life=ml, max_life=ml, color=self._rng.choice(palette),
                size=self._rng.randint(int(size[0]), int(size[1])), gravity=float(gravity)))
        self._cap_particles()

    def _spawn_crow_shoo(self, pos: tuple[int, int], *, play_sfx: bool = True) -> None:
        if play_sfx:
            self._play_sfx(self._sfx_crow_shoo, key="crow_shoo", debounce=0.06)
        if not JUICE_ENABLED:
            return
        x, y = pos
        feather_colors = ((42, 43, 50), (68, 70, 78), (210, 208, 188))
        for _ in range(10):
            self._particles.append(Particle(
                x + self._rng.uniform(-6, 6), y + self._rng.uniform(-5, 5),
                vx=self._rng.uniform(-115, 115), vy=self._rng.uniform(-150, -45),
                life=self._rng.uniform(0.42, 0.72), max_life=0.72,
                color=self._rng.choice(feather_colors), size=self._rng.randint(2, 4),
                gravity=90.0))
        self._cap_particles()

    def _spawn_critter_steal_juice(self, pos) -> None:
        self._burst(pos, 12, ((122, 92, 66), (92, 150, 70)),
                    vx=(-95, 95), vy=(-150, -45), life=(0.45, 0.75), gravity=180.0)

    def _spawn_critter_scare_juice(self, pos) -> None:
        self._burst(pos, 9, ((190, 165, 125),), vx=(-85, 85), vy=(-95, -25), life=(0.32, 0.56), gravity=120.0)

    def _spawn_critter_spawn_juice(self, pos) -> None:
        self._burst(pos, 7, ((135, 108, 78),), vx=(-60, 60), vy=(-75, -20), life=(0.28, 0.48), gravity=140.0)

    def _spawn_worker_kill_juice(self, pos) -> None:
        self._burst(pos, 10, ((190, 165, 125),), vx=(-95, 95), vy=(-130, -35), life=(0.38, 0.65), gravity=150.0)
        self._burst(pos, 5, ((125, 62, 48),), vx=(-75, 75), vy=(-110, -30), life=(0.34, 0.58), gravity=140.0)

    def _spawn_worker_foot_dust(self, pos) -> None:
        self._burst(pos, 2, ((135, 108, 78),), vx=(-18, 18), vy=(-28, -8), life=(0.22, 0.36), size=(1, 2), gravity=80.0)

    def _spawn_crow_steal_juice(self, pos, target: str) -> None:
        if target == "scarecrow":
            self._burst(pos, 10, ((210, 175, 85), (180, 135, 64)), vx=(-105, 105), vy=(-150, -40), gravity=150.0)
        else:
            self._burst(pos, 8, ((122, 92, 66), (92, 150, 70)), vx=(-95, 95), vy=(-145, -45), gravity=170.0)

    def _spawn_tool_juice(self, slot: PlantSlot, tool_id: str) -> None:
        pos = (slot.rect.centerx, slot.rect.bottom - 10)
        if tool_id == TOOL_COMPOST:
            self._burst(pos, 10, ((108, 78, 52), (142, 108, 72)), vx=(-70, 70), vy=(-105, -30), gravity=150.0)
        elif tool_id == TOOL_SCARECROW:
            self._burst(pos, 10, ((210, 175, 85), (174, 132, 62)), vx=(-80, 80), vy=(-125, -35), gravity=130.0)
        elif tool_id == TOOL_LIGHTNING_ROD:
            self._burst((slot.rect.centerx, slot.rect.centery), 10, ((110, 190, 255), (190, 230, 255)),
                        vx=(-90, 90), vy=(-135, -35), life=(0.25, 0.45), gravity=40.0)

    def _spawn_blight_juice(self, slot: PlantSlot) -> None:
        self._burst((slot.rect.centerx, slot.rect.bottom - 8), 9, ((112, 80, 132), (118, 150, 72)),
                    vx=(-70, 70), vy=(-95, -25), life=(0.38, 0.62), gravity=120.0)

    def _spawn_miniboss_juice(self, name: str, kind: str, pos) -> None:
        lname = str(name).lower()
        if "mole" in lname:
            colors = ((135, 108, 78), (104, 78, 54)) if kind != "fail" else ((225, 230, 210), (180, 170, 140))
        elif "locust" in lname:
            colors = ((130, 180, 70), (215, 230, 160))
        elif "glare" in lname:
            colors = ((255, 188, 80), (240, 132, 64))
        else:
            colors = ((74, 165, 78), (138, 214, 104))
        self._burst(pos, 12 if kind == "fail" else 8, colors,
                    vx=(-95, 95), vy=(-130, -35), life=(0.34, 0.62), gravity=120.0)

    def _spawn_combo_crossover(self, boss) -> None:
        if self._sfx_combo_chime:
            self._sfx_combo_chime.play()
        if not JUICE_ENABLED:
            return
        cx = int(getattr(getattr(boss, "rect", None), "centerx", self._field_rect.width // 2))
        cy = int(getattr(getattr(boss, "rect", None), "bottom", 90)) + 16
        for _ in range(16):
            ang = self._rng.uniform(0.0, math.tau)
            spd = self._rng.uniform(45.0, 150.0)
            self._particles.append(Particle(
                cx, cy, vx=math.cos(ang) * spd, vy=math.sin(ang) * spd,
                life=self._rng.uniform(0.45, 0.8), max_life=0.8,
                image=self._golden_sparkle_img, color=(255, 218, 94),
                size=self._rng.randint(2, 4), gravity=0.0))

    def _money_counter_anchor(self) -> tuple[int, int]:
        return (self._field_rect.width + 26, 56)

    def _spawn_fly_coins(self, start_pos, n: int = 6) -> None:
        # Coins arc from a sell point up to the money counter, bumping it on arrival.
        if not JUICE_ENABLED:
            return
        tx, ty = self._money_counter_anchor()
        n = max(1, min(int(n), 8))
        for i in range(n):
            self._fly_coins.append({
                "sx": float(start_pos[0]), "sy": float(start_pos[1]),
                "tx": float(tx), "ty": float(ty),
                "tw": effects.Tween(0.0, 1.0, self._rng.uniform(0.42, 0.62), effects.ease_in_out_quad),
                "delay": i * 0.04,
                "arc": self._rng.uniform(-50, -95),
            })

    def _update_fly_coins(self, dt: float) -> None:
        if not self._fly_coins:
            return
        landed = 0
        still = []
        for fc in self._fly_coins:
            if fc["delay"] > 0.0:
                fc["delay"] -= dt
                still.append(fc)
                continue
            fc["tw"].update(dt)
            if fc["tw"].done:
                landed += 1
            else:
                still.append(fc)
        self._fly_coins = still
        if landed:
            self._money_bump = min(1.2, self._money_bump + 0.45 * landed)
            if self._sfx_sell:
                pass  # the sell sound already played; keep landings silent to avoid spam

    def _draw_fly_coins(self) -> None:
        if not self._fly_coins or not self._coin_particle_img:
            return
        img = self._coin_particle_img
        for fc in self._fly_coins:
            if fc["delay"] > 0.0:
                continue
            e = fc["tw"].value
            x = fc["sx"] + (fc["tx"] - fc["sx"]) * e
            y = fc["sy"] + (fc["ty"] - fc["sy"]) * e + fc["arc"] * math.sin(math.pi * min(1.0, e))
            self.screen.blit(img, img.get_rect(center=(int(x), int(y))))

    def _build_mountain_masks(self) -> None:
        fw = self._field_rect.width
        h = SCREEN_H
        wide = fw * 2
        base = max(80, self._ground_rect.top - 26)
        specs = (
            (base - 92, 56, 0.010, 0.6, 50, 0.018),
            (base - 54, 42, 0.014, 2.1, 68, 0.030),
            (base - 22, 30, 0.020, 4.0, 82, 0.050),
        )
        masks: list[tuple[pygame.Surface, float]] = []
        for base_y, amp, freq, phase, alpha, speed in specs:
            surf = pygame.Surface((wide, h), pygame.SRCALPHA)
            pts = [(0, h)]
            x = 0
            while x <= wide:
                ridge = math.sin(x * freq + phase) * amp
                ridge += math.sin(x * freq * 0.43 + phase * 1.7) * amp * 0.45
                y = int(base_y + ridge)
                pts.append((x, y))
                x += 18
            pts.extend([(wide, h), (0, h)])
            pygame.draw.polygon(surf, (255, 255, 255, alpha), pts)
            for px in range(70, wide, 180):
                peak = (px, int(base_y - amp * 1.25 + math.sin(px * 0.017 + phase) * 16))
                left = (px - 58, int(base_y + amp * 0.35))
                right = (px + 64, int(base_y + amp * 0.30))
                pygame.draw.polygon(surf, (255, 255, 255, max(0, alpha - 28)), [left, peak, right])
            masks.append((surf, speed))
        self._mountain_masks = masks

    def _draw_mountains(self) -> None:
        if self._mountain_masks is None:
            self._build_mountain_masks()
        sky = tuple(int(c) for c in self._sky_color)
        key = (tuple((c // 8) * 8 for c in sky), int(self._darkness * 16))
        if key != self._mountain_tint_key:
            dusk = ui_theme.lerp_col((88, 128, 126), (34, 42, 62), self._darkness)
            near = ui_theme.lerp_col((105, 146, 114), (38, 48, 56), self._darkness)
            far = ui_theme.lerp_col((142, 168, 154), (46, 54, 72), self._darkness)
            cols = (
                ui_theme.lerp_col(far, sky, 0.24),
                ui_theme.lerp_col(dusk, sky, 0.18),
                ui_theme.lerp_col(near, sky, 0.12),
            )
            tinted = []
            assert self._mountain_masks is not None
            for (mask, _speed), col in zip(self._mountain_masks, cols):
                layer = pygame.Surface(mask.get_size(), pygame.SRCALPHA)
                layer.fill((*col, 255))
                layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                tinted.append(layer)
            self._mountain_tinted = tinted
            self._mountain_tint_key = key
        fw = self._field_rect.width
        assert self._mountain_masks is not None
        for layer, (_mask, speed) in zip(self._mountain_tinted, self._mountain_masks):
            off = int((self._world_seconds * speed) % fw)
            self.screen.blit(layer, (-off, 0), area=pygame.Rect(0, 0, fw, SCREEN_H))
            if off:
                self.screen.blit(layer, (fw - off, 0), area=pygame.Rect(fw, 0, off, SCREEN_H))

    # ── draw ──────────────────────────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(tuple(int(c) for c in self._sky_color))

        # Warm sunrise/sunset glow over the field during the day<->night fade.
        warm = max(0.0, 1.0 - abs(self._darkness - SKY_WARM_CENTER) / SKY_WARM_HALFWIDTH)
        if warm > 0.0:
            if self._warm_glow_surf is None:
                s = pygame.Surface((self._field_rect.width, SCREEN_H))
                s.fill(SKY_WARM_TINT)
                self._warm_glow_surf = s
            self._warm_glow_surf.set_alpha(int(SKY_WARM_MAX_ALPHA * warm))
            self.screen.blit(self._warm_glow_surf, (0, 0))

        # Cool night colour grading over the field (cached; alpha tracks darkness).
        if self._darkness > 0.05:
            if self._night_wash_surf is None:
                s = pygame.Surface((self._field_rect.width, SCREEN_H))
                s.fill(SKY_NIGHT_TINT)
                self._night_wash_surf = s
            self._night_wash_surf.set_alpha(int(SKY_NIGHT_MAX_ALPHA * self._darkness))
            self.screen.blit(self._night_wash_surf, (0, 0))

        self._draw_mountains()
        self.stars.draw(self.screen, self._darkness)
        sun_alpha = int(255 *(1 - self._darkness))
        moon_alpha = int (255 * self._darkness)
        if sun_alpha > 0:
            self.sun.image.set_alpha(sun_alpha)
            self.screen.blit(self.sun.image, self.sun.rect)
        if moon_alpha > 0:
            self.moon.image.set_alpha(moon_alpha)
            self.screen.blit(self.moon.image, self.moon.rect)

        for boss in self._bosses:
            self._draw_boss_body(boss)

        for i, c in enumerate(self.clouds):
            c.draw_rain(self.screen)
            # A gentle vertical idle-bob so the clouds feel alive (free: position only).
            bob = int(round(3.0 * math.sin(pygame.time.get_ticks() * 0.0019 + i * 1.7))) if JUICE_ENABLED else 0
            self.screen.blit(c.image, c.image.get_rect(topleft=(c.rect.x, c.rect.y + bob)))
            c.draw_control_label(self.screen)

        self._draw_ground()
        self._draw_slots()
        draw_prime_overlays(self.screen, self.slots)
        self._draw_shadow()
        self._draw_critters()
        self.auto_worker.draw(self.screen)
        self._minibosses.draw(self.screen)
        # Second cool pass AFTER the field is drawn so the ground and crops darken with
        # the sky at night (the earlier wash only covered the sky behind them). Kept
        # under the ambient particles and HUD so fireflies still glow and panels read.
        if self._darkness > 0.05:
            if self._field_night_surf is None:
                s = pygame.Surface((self._field_rect.width, SCREEN_H))
                s.fill(SKY_NIGHT_TINT)
                self._field_night_surf = s
            self._field_night_surf.set_alpha(int(SKY_NIGHT_FIELD_ALPHA * self._darkness))
            self.screen.blit(self._field_night_surf, (0, 0))
        if JUICE_ENABLED:
            self._draw_ambient(self.screen)
            self._draw_drizzle_rain(self.screen)
            self._draw_particles(self.screen)

        self.storm_titan.draw_bolt(self.screen)
        self.storm_titan.draw_warning(self.screen, slots=self.slots)

        self.cyclone_titan.draw_bolt(self.screen)
        self.cyclone_titan.draw_warning(self.screen, slots=self.slots)

        self.drought_titan.draw_bolt(self.screen)
        self.drought_titan.draw_warning(self.screen, slots=self.slots)

        self.frost_titan.draw_bolt(self.screen)
        self.frost_titan.draw_warning(self.screen, slots=self.slots)

        self.inferno_titan.draw_bolt(self.screen)
        self.inferno_titan.draw_warning(self.screen, slots=self.slots)
        self._draw_reticle_icons()

        self._draw_perfect_flashes()

        self._apply_screen_shake()

        self._draw_boss_health_bar()
        self._draw_sky_forecast()

        if JUICE_ENABLED and self._darkness > 0.02:
            # Vignette is a night-time mood cue: fully off in daylight, fading in
            # with darkness so the field stays bright and readable during the day.
            v_strength = int(VIGNETTE_STRENGTH * self._darkness)
            if v_strength > 0:
                self.screen.blit(effects.vignette(self._field_rect.width, SCREEN_H, v_strength), (0, 0))
        self._draw_ouch_flash()

        self._draw_ui_panel()
        self._draw_hover_tooltip()
        self._draw_drag_seed()
        self._draw_hud()
        if JUICE_ENABLED:
            self._draw_float_texts(self.screen)
            self._draw_fly_coins()
        self._draw_day_banner()
        if self.paused:
            self._draw_pause_window()
        if self._show_almanac or "almanac" in self._modal_close_at:
            self._draw_almanac_overlay()
        if self._show_inventory_overlay or "inventory" in self._modal_close_at:
            self._draw_inventory_overlay()
        if self._show_market_overlay or "market" in self._modal_close_at:
            self._draw_market_overlay()
        if self._show_sell_confirm:
            self._draw_sell_confirm()
        if self._show_purchase_confirm:
            self._draw_purchase_confirm()
        if not (self._show_inventory_overlay or self._show_market_overlay):
            self._draw_main_menu_button()
        if self._show_report_card:
            self._draw_report_card()
        pygame.display.flip()

    def _draw_boss_body(self, boss) -> None:
        if not getattr(boss, "visible", False):
            return
        remaining = float(self._boss_arrivals.get(id(boss), 0.0))
        if remaining <= 0.0:
            boss.draw_body(self.screen)
            return
        dur = 0.48
        p = 1.0 - max(0.0, min(1.0, remaining / dur))
        ease = effects.ease_out_back(p)
        rect = getattr(boss, "rect", None)
        image = getattr(boss, "image", None)
        if not isinstance(rect, pygame.Rect) or image is None:
            boss.draw_body(self.screen)
            return
        scale = max(0.1, 0.78 + 0.22 * ease)
        w = max(1, int(image.get_width() * scale))
        h = max(1, int(image.get_height() * scale))
        frame = pygame.transform.smoothscale(image, (w, h))
        frame.set_alpha(int(255 * min(1.0, p * 1.7)))
        draw_rect = frame.get_rect(center=(rect.centerx, rect.centery - int((1.0 - min(1.0, ease)) * 58)))
        self.screen.blit(frame, draw_rect)

    def _draw_reticle_icons(self) -> None:
        for boss in self._bosses:
            if not getattr(boss, "visible", False) or getattr(boss, "state", None) != StormTitan.STATE_ACTIVE:
                continue
            if float(getattr(boss, "_warning_remaining", 0.0)) <= 0.0:
                continue
            kind = self._boss_block_icon_kind(boss)
            rects = self._boss_warning_rects(boss)
            self._draw_block_rule_cues(boss, kind, rects)
            targets = self._boss_warning_centers(boss)
            for pos in targets:
                cue_pos = (pos[0], pos[1] - 28) if kind != "sun_cover" else pos
                self._draw_block_icon(cue_pos, kind)
            self._draw_block_rule_label(boss, kind, targets)

    def _boss_block_icon_kind(self, boss) -> str:
        if boss is self.cyclone_titan:
            return "rain"
        if boss is self.drought_titan:
            return "sun_cover"
        if boss is self.frost_titan:
            return "cloud"
        if boss is self.inferno_titan:
            phase = getattr(boss, "current_phase", PHASE_STORM)
            if phase == PHASE_CYCLONE:
                return "rain"
            if phase == PHASE_DROUGHT:
                return "sun_cover"
            if phase in (PHASE_FROST, PHASE_INFERNO):
                return "cloud"
        return "cloud"

    def _boss_warning_centers(self, boss) -> list[tuple[int, int]]:
        phase = getattr(boss, "current_phase", None)
        if boss is self.drought_titan or (boss is self.inferno_titan and phase == PHASE_DROUGHT):
            rect = getattr(self.sun, "circle_rect", None)
            return [rect.center] if isinstance(rect, pygame.Rect) else []
        mark_indices = getattr(boss, "_mark_indices", None)
        if mark_indices:
            out = []
            for idx in mark_indices:
                if 0 <= int(idx) < len(self.slots):
                    out.append(self.slots[int(idx)].rect.center)
            return out
        idx = getattr(boss, "_target_slot_index", None)
        if idx is None or int(idx) < 0 or int(idx) >= len(self.slots):
            return []
        return [self.slots[int(idx)].rect.center]

    def _boss_warning_rects(self, boss) -> list[pygame.Rect]:
        phase = getattr(boss, "current_phase", None)
        if boss is self.drought_titan or (boss is self.inferno_titan and phase == PHASE_DROUGHT):
            rect = getattr(self.sun, "circle_rect", None)
            return [rect] if isinstance(rect, pygame.Rect) else []
        mark_indices = getattr(boss, "_mark_indices", None)
        if mark_indices:
            return [self.slots[int(i)].rect for i in mark_indices
                    if 0 <= int(i) < len(self.slots) and isinstance(getattr(self.slots[int(i)], "rect", None), pygame.Rect)]
        idx = getattr(boss, "_target_slot_index", None)
        if idx is None or int(idx) < 0 or int(idx) >= len(self.slots):
            return []
        rect = getattr(self.slots[int(idx)], "rect", None)
        return [rect] if isinstance(rect, pygame.Rect) else []

    def _draw_block_rule_cues(self, boss, kind: str, rects: list[pygame.Rect]) -> None:
        if not rects:
            return
        now = pygame.time.get_ticks() / 1000.0
        pulse = 0.55 + 0.45 * math.sin(now * math.tau * 2.2)
        phase = getattr(boss, "current_phase", None)
        fire_ability = getattr(boss, "_fire_ability", None)
        is_firestorm = boss is self.inferno_titan and phase == PHASE_INFERNO and fire_ability == FIRE_FIRESTORM
        is_lava = boss is self.inferno_titan and phase == PHASE_INFERNO and fire_ability == FIRE_LAVA
        color = PHASE_COLORS.get(phase, (255, 235, 120)) if boss is self.inferno_titan else {
            "rain": (96, 180, 255),
            "sun_cover": (255, 180, 70),
            "cloud": (230, 242, 250),
        }.get(kind, (230, 242, 250))

        if kind == "sun_cover":
            rect = rects[0].inflate(28, 28)
            glow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*color, 70), (rect.w // 2, rect.h // 2), rect.w // 2)
            self.screen.blit(glow, rect.topleft)
            pygame.draw.circle(self.screen, (255, 248, 218), rect.center, rect.w // 2, 2)
            return

        band = rects[0].unionall(rects[1:]).inflate(18 if is_firestorm else 12, 18)
        haze = pygame.Surface((band.w, band.h), pygame.SRCALPHA)
        haze.fill((*color, int((58 if is_firestorm else 42) + 34 * pulse)))
        self.screen.blit(haze, band.topleft)
        pygame.draw.rect(self.screen, color, band, 2, border_radius=10)

        label = "Cover marked tiles" if is_firestorm else ("Cover this tile" if is_lava else "")
        if label:
            chip = pygame.Rect(0, 0, self._small_bold.size(label)[0] + 22, 26)
            chip.midbottom = (band.centerx, max(28, band.top - 8))
            ui_theme.button_plate(self.screen, chip, style="primary", hover=pulse * 0.45,
                                  radius=10, glow=0.25 if is_firestorm else 0.1)
            ui_theme.draw_text(self.screen, self._small_bold, label, ui_theme.INK,
                               chip.center, anchor="center", shadow=(255, 236, 170), dy=1)

        for rect in rects:
            rr = rect.inflate(10, 10)
            pygame.draw.rect(self.screen, (*color, 255), rr, 3, border_radius=8)
            top = rect.top - int(18 + 5 * pulse)
            pts = [(rect.centerx, top + 18), (rect.centerx - 12, top), (rect.centerx + 12, top)]
            pygame.draw.polygon(self.screen, (255, 248, 218), pts)
            pygame.draw.polygon(self.screen, color, pts, 2)

    def _draw_block_rule_label(self, boss, kind: str, targets: list[tuple[int, int]]) -> None:
        if not targets:
            return
        phase = getattr(boss, "current_phase", None)
        fire_ability = getattr(boss, "_fire_ability", None)
        if boss is self.inferno_titan and phase == PHASE_INFERNO:
            rule = "firestorm" if fire_ability == FIRE_FIRESTORM else "lava"
        else:
            rule = kind
        now = pygame.time.get_ticks() / 1000.0
        if rule not in self._seen_block_rules:
            self._seen_block_rules.add(rule)
            self._block_rule_label_until[rule] = now + 3.0
        if now > self._block_rule_label_until.get(rule, 0.0):
            return
        label = {
            "rain": "Rain cloud blocks",
            "sun_cover": "Cloud covers sun",
            "cloud": "Cloud blocks",
            "firestorm": "Clouds cover marked tiles",
            "lava": "Cloud covers the tile",
        }.get(rule, "Cloud blocks")
        x = sum(p[0] for p in targets) // len(targets)
        y = min(p[1] for p in targets) - 72
        rect = pygame.Rect(0, 0, self._small_bold.size(label)[0] + 24, 28)
        rect.midbottom = (x, max(36, y))
        ui_theme.panel_with_shadow(self.screen, rect, top=(58, 52, 60), bottom=(40, 36, 44),
                                   border=(250, 224, 150), radius=10, shadow_lift=4,
                                   shadow_alpha=52)
        ui_theme.draw_text(self.screen, self._small_bold, label, ui_theme.CREAM,
                           rect.center, anchor="center", shadow=(0, 0, 0), dy=1)

    def _draw_block_icon(self, pos: tuple[int, int], kind: str) -> None:
        cx, cy = int(pos[0]), int(pos[1])
        pygame.draw.circle(self.screen, (28, 30, 36), (cx, cy), 19)
        pygame.draw.circle(self.screen, (255, 248, 218), (cx, cy), 19, 3)
        if kind == "rain":
            pygame.draw.circle(self.screen, (78, 168, 245), (cx, cy + 4), 7)
            pygame.draw.polygon(self.screen, (78, 168, 245), [(cx - 7, cy + 4), (cx + 7, cy + 4), (cx, cy - 11)])
            pygame.draw.circle(self.screen, (170, 220, 255), (cx - 3, cy), 3)
            for dx in (-6, 0, 6):
                pygame.draw.line(self.screen, (150, 214, 255), (cx + dx, cy + 10), (cx + dx - 2, cy + 16), 2)
        elif kind == "sun_cover":
            pygame.draw.circle(self.screen, (248, 198, 74), (cx, cy), 9)
            pygame.draw.arc(self.screen, (235, 240, 245), pygame.Rect(cx - 15, cy - 7, 30, 18), math.pi, math.tau, 5)
            pygame.draw.circle(self.screen, (245, 248, 250), (cx - 5, cy - 7), 5)
            pygame.draw.circle(self.screen, (245, 248, 250), (cx + 2, cy - 9), 6)
        else:
            pygame.draw.ellipse(self.screen, (235, 240, 245), pygame.Rect(cx - 13, cy - 3, 26, 14))
            pygame.draw.circle(self.screen, (245, 248, 250), (cx - 7, cy - 4), 7)
            pygame.draw.circle(self.screen, (245, 248, 250), (cx + 3, cy - 7), 8)
            pygame.draw.line(self.screen, (140, 200, 255), (cx, cy + 8), (cx, cy + 15), 2)

    def _draw_ouch_flash(self) -> None:
        if self._ouch_flash_t <= 0.0:
            return
        t = max(0.0, min(1.0, self._ouch_flash_t / 0.32))
        surf = effects.edge_flash(self._field_rect.width, SCREEN_H, (220, 48, 42), 24)
        surf.set_alpha(int(145 * t))
        self.screen.blit(surf, (0, 0))

    def _draw_hud(self):
        rows: list[tuple[str, str, tuple[int, int, int]]] = []

        day_in_week = (self._day_index % int(IN_GAME_DAYS_PER_WEEK)) + 1
        week = self._week_index + 1
        season = SEASON_NAMES[self._season_index] if SEASON_NAMES else "Season"
        rows.append(("day", f"Day {day_in_week}/{IN_GAME_DAYS_PER_WEEK}   Week {week}   {season}", (255, 255, 255)))

        a_done = self._almanac.season_completed_count()
        a_total = self._almanac.season_goal_count()
        rows.append(("almanac", f"Almanac {a_done}/{a_total}   Year {self._almanac.year_index + 1}   [J]", (210, 225, 180)))

        if self._market_featured_item and self._market_discounted_item:
            rows.append((
                "market",
                f"Hot {self._market_featured_item} x{MARKET_FEATURED_MULT:g}   "
                f"Cold {self._market_discounted_item} x{MARKET_DISCOUNT_MULT:g}",
                (235, 220, 160),
            ))

        if self._weather_event != "None":
            remaining = max(0, int(self._weather_remaining) + 1)
            rows.append(("weather", f"{self._weather_event}  ({remaining}s)", (200, 225, 255)))

        # Boss status rows (loop over _bosses so new bosses appear automatically;
        # disabled bosses are hidden until a progression year enables them).
        for boss in self._bosses:
            kind = getattr(boss, "boss_id", "storm")
            label = getattr(boss, "display_name", "Boss")
            if boss.state == StormTitan.STATE_ACTIVE:
                rows.append((kind, f"{label} HP {boss.hp}/{boss.max_hp}", (255, 170, 150)))
            elif boss.state == StormTitan.STATE_RETREATING:
                rows.append((kind, f"{label} leaves in {max(0, int(boss.seconds_until_leave) + 1)}s", (225, 225, 225)))
            elif getattr(boss, "enabled", True):
                rows.append((kind, f"Next {label} {self._format_mmss(boss.seconds_until_spawn)}", (210, 210, 210)))

        # Layout: an icon column + text column inside a rounded panel.
        pad = 10
        icon_sz = 16
        gap = 8
        row_h = 24
        title_text = "FARM STATUS"
        title_h = self._font.get_height() + 6

        text_w = max((self._small_font.size(t)[0] for _, t, _ in rows), default=0)
        # The amber header chip carries the title; size the plaque so the chip
        # (10px inset each side) and the widest row both fit.
        title_w = self._head_font.size(title_text)[0] + 26
        inner_w = max(icon_sz + gap + text_w, title_w)
        panel_w = pad + inner_w + pad
        panel_h = pad + title_h + len(rows) * row_h + pad

        ox, oy = 8, 8
        panel_rect = pygame.Rect(ox, oy, panel_w, panel_h)
        cloud_behind = any(c.rect.colliderect(panel_rect) for c in self.clouds)

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        ui_theme.soft_shadow(self.screen, panel_rect, radius=14, lift=5, pad=10,
                             layers=3, alpha=24 if cloud_behind else 48)
        panel.blit(ui_theme.rounded_panel(panel_w, panel_h, top=(58, 52, 60),
                                          bottom=(40, 36, 44), border=(120, 112, 124),
                                          radius=14), (0, 0))
        local = pygame.Rect(0, 0, panel_w, panel_h)
        chip = pygame.Rect(pad - 3, pad - 3, panel_w - 2 * (pad - 3), title_h)
        ui_theme.section_header(panel, chip, title_text, self._head_font,
                                style="primary", shadow=False)

        y = pad + title_h
        for kind, text, color in rows:
            row_rect = pygame.Rect(pad - 4, y + 2, panel_w - pad * 2 + 8, row_h - 3)
            pygame.draw.rect(panel, (255, 255, 255, 18), row_rect, border_radius=6)
            irect = pygame.Rect(pad, y + (row_h - icon_sz) // 2, icon_sz, icon_sz)
            self._draw_hud_icon(kind, irect, panel)
            ty = y + (row_h - self._small_font.get_height()) // 2
            ui_theme.draw_text(panel, self._small_font, text, color,
                               (irect.right + gap, ty), anchor="topleft",
                               shadow=(28, 16, 8), dx=1, dy=1)
            y += row_h
        if cloud_behind:
            panel.set_alpha(HUD_UNDERCLOUD_ALPHA)
        self.screen.blit(panel, (ox, oy))

        # Flash 'Perfect Block!' when a perfect block was recently registered
        now = pygame.time.get_ticks() / 1000.0
        flash_duration = 1.2
        perfect_shown = False
        for boss in self._bosses:
            t = getattr(boss, "_last_perfect_at", None)
            if t is not None and now - float(t) <= flash_duration:
                msg = "Perfect Block!"
                surf = self._font.render(msg, True, (255, 215, 0))
                shadow = self._font.render(msg, True, (0, 0, 0))
                # Pop in with an ease-out-back overshoot over the first 0.18s.
                age = now - float(t)
                pop = effects.ease_out_back(min(1.0, age / 0.18))
                scale = 0.4 + 0.6 * pop
                if scale < 0.999:
                    surf = pygame.transform.rotozoom(surf, 0, scale)
                    shadow = pygame.transform.rotozoom(shadow, 0, scale)
                sx = (self._field_rect.width - surf.get_width()) // 2
                sy = 40
                self.screen.blit(shadow, (sx + 2, sy + 2))
                self.screen.blit(surf, (sx, sy))
                perfect_shown = True
                break

    def _draw_perfect_flashes(self) -> None:
        if not (JUICE_ENABLED and self._perfect_flashes):
            return
        now = pygame.time.get_ticks() / 1000.0
        dur = 0.18
        alive = []
        for fx, fy, t0 in self._perfect_flashes:
            age = now - t0
            if age >= dur:
                continue
            a = int(170 * (1.0 - age / dur))
            a = (a // 20) * 20  # quantize so the cached-glow set stays tiny
            if a > 0:
                glow = effects.radial_glow(40, (255, 255, 255), a)
                self.screen.blit(glow, glow.get_rect(center=(fx, fy)))
            alive.append([fx, fy, t0])
        self._perfect_flashes = alive

    def _draw_day_banner(self) -> None:
        if self._day_banner_t <= 0.0:
            return
        # Alpha envelope over the 4s life: quick fade in, hold, fade out the last 0.8s.
        age = 4.0 - self._day_banner_t
        if age < 0.3:
            a = age / 0.3
        elif self._day_banner_t < 0.8:
            a = self._day_banner_t / 0.8
        else:
            a = 1.0
        a = max(0.0, min(1.0, a))
        if a <= 0.0:
            return
        # A slim pill: a small gold "DAY n" chip plus the weather name. Compact, not a
        # big panel, and tucked just below the forecast strip.
        chip = self._small_bold.render(f"DAY {self._day_index + 1}", True, (28, 30, 38))
        name = self._font.render(self._day_banner_title, True, (255, 246, 220))
        pad, gap, cpx = 9, 8, 6
        chip_w = chip.get_width() + cpx * 2
        w = pad + chip_w + gap + name.get_width() + pad
        h = max(name.get_height(), chip.get_height() + 4) + 10
        cx = self._field_rect.width // 2
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        rr = panel.get_rect()
        pygame.draw.rect(panel, (22, 24, 32, int(205 * a)), rr, border_radius=h // 2)
        pygame.draw.rect(panel, (250, 208, 96, int(150 * a)), rr, 1, border_radius=h // 2)
        chip_rect = pygame.Rect(pad, (h - (chip.get_height() + 4)) // 2, chip_w, chip.get_height() + 4)
        pygame.draw.rect(panel, (250, 208, 96, int(230 * a)), chip_rect, border_radius=4)
        c = chip.copy(); c.set_alpha(int(255 * a))
        panel.blit(c, (chip_rect.x + cpx, chip_rect.y + 2))
        nimg = name.copy(); nimg.set_alpha(int(255 * a))
        panel.blit(nimg, (pad + chip_w + gap, (h - name.get_height()) // 2))
        self.screen.blit(panel, panel.get_rect(midtop=(cx, 46)))

    def _draw_hud_icon(self, kind: str, rect: pygame.Rect, surface: pygame.Surface | None = None) -> None:
        s = surface or self.screen
        cx, cy = rect.center
        if kind == "day":
            pygame.draw.rect(s, (235, 235, 235), rect, border_radius=3)
            top = pygame.Rect(rect.left, rect.top, rect.width, 5)
            pygame.draw.rect(s, (200, 80, 70), top, border_top_left_radius=3, border_top_right_radius=3)
            for gx in range(3):
                for gy in range(2):
                    pygame.draw.rect(s, (120, 120, 120), (rect.left + 3 + gx * 4, rect.top + 8 + gy * 4, 2, 2))
        elif kind == "market":
            r = rect.width // 2
            pygame.draw.circle(s, (230, 195, 90), (cx, cy), r)
            pygame.draw.circle(s, (180, 150, 60), (cx, cy), r, 1)
            sign = self._small_font.render("$", True, (120, 90, 30))
            s.blit(sign, sign.get_rect(center=(cx, cy)))
        elif kind == "weather":
            ev = self._weather_event
            if ev == "Heatwave":
                for a in range(0, 360, 45):
                    ex = cx + math.cos(math.radians(a)) * 8
                    ey = cy + math.sin(math.radians(a)) * 8
                    pygame.draw.line(s, (240, 170, 60), (cx, cy), (ex, ey), 2)
                pygame.draw.circle(s, (245, 200, 70), (cx, cy), 5)
            elif ev == "Gusts":
                for yy in (-3, 1, 5):
                    pygame.draw.arc(s, (210, 225, 235), (rect.left, cy + yy - 4, rect.width, 9), 3.6, 6.1, 2)
            else:  # Drizzle (and any other) → rain cloud
                pygame.draw.circle(s, (200, 205, 210), (cx - 2, cy - 1), 5)
                pygame.draw.circle(s, (200, 205, 210), (cx + 3, cy - 1), 4)
                pygame.draw.rect(s, (200, 205, 210), (cx - 6, cy - 1, 11, 5))
                for dx in (-4, 0, 4):
                    pygame.draw.line(s, (120, 170, 230), (cx + dx, cy + 5), (cx + dx, cy + 8), 1)
        elif kind == "storm":
            pygame.draw.circle(s, (120, 125, 135), (cx - 3, cy - 1), 5)
            pygame.draw.circle(s, (120, 125, 135), (cx + 3, cy - 2), 4)
            pygame.draw.rect(s, (120, 125, 135), (cx - 7, cy - 2, 13, 5))
            pygame.draw.polygon(s, (245, 220, 80), [(cx - 1, cy + 1), (cx + 3, cy + 1), (cx, cy + 8)])
        elif kind == "cyclone":
            for i, r in enumerate((7, 5, 3)):
                yy = cy - 6 + i * 5
                pygame.draw.arc(s, (180, 200, 220), (cx - r, yy - 3, 2 * r, 8), 3.4, 6.2, 2)
            pygame.draw.line(s, (180, 200, 220), (cx, cy + 5), (cx - 2, cy + 9), 2)
        elif kind == "drought":
            for a in range(0, 360, 45):
                ex = cx + math.cos(math.radians(a)) * 7
                ey = cy + math.sin(math.radians(a)) * 7
                pygame.draw.line(s, (240, 150, 50), (cx, cy), (ex, ey), 2)
            pygame.draw.circle(s, (245, 170, 60), (cx, cy), 5)
            pygame.draw.circle(s, (120, 60, 20), (cx, cy), 5, 1)
        elif kind == "frost":
            for a in range(0, 360, 60):
                ex = cx + math.cos(math.radians(a)) * 7
                ey = cy + math.sin(math.radians(a)) * 7
                pygame.draw.line(s, (170, 210, 240), (cx, cy), (int(ex), int(ey)), 2)
            pygame.draw.circle(s, (225, 240, 255), (cx, cy), 2)
        elif kind == "almanac":
            book = pygame.Rect(rect.left + 2, rect.top + 2, rect.width - 4, rect.height - 4)
            pygame.draw.rect(s, (185, 150, 95), book, border_radius=2)
            pygame.draw.rect(s, (120, 90, 50), book, 1, border_radius=2)
            pygame.draw.line(s, (120, 90, 50), (cx, book.top), (cx, book.bottom), 1)
            pygame.draw.circle(s, (245, 230, 150), (cx, cy), 2)

    def _toggle_almanac(self) -> None:
        if self._show_almanac:
            self._close_almanac()
            return
        self._show_almanac = True
        self._play_sfx(self._sfx_ui_open, key="almanac_open", debounce=0.12)
        self._almanac_open_time = pygame.time.get_ticks() / 1000.0
        self._show_inventory_overlay = False
        self._show_market_overlay = False

    def _close_almanac(self) -> None:
        if not self._show_almanac:
            return
        self._start_modal_close("almanac")
        self._show_almanac = False
        self._play_sfx(self._sfx_ui_close, key="almanac_close", debounce=0.12)
        for gdef, gstate in self._almanac.active_goals():
            if gstate.completed:
                self._almanac_seen.add(gdef.id)

    def _toggle_inventory_overlay(self) -> None:
        if self._show_inventory_overlay:
            self._start_modal_close("inventory")
            self._show_inventory_overlay = False
            self._play_sfx(self._sfx_ui_close, key="inventory_close", debounce=0.12)
            return
        self._show_inventory_overlay = True
        self._play_sfx(self._sfx_ui_open, key="inventory_open", debounce=0.12)
        if self._show_market_overlay:
            self._start_modal_close("market")
            self._play_sfx(self._sfx_ui_close, key="market_close", debounce=0.12)
        self._show_market_overlay = False
        self._show_almanac = False

    def _toggle_market_overlay(self) -> None:
        if self._show_market_overlay:
            self._start_modal_close("market")
            self._show_market_overlay = False
            self._play_sfx(self._sfx_ui_close, key="market_close", debounce=0.12)
            return
        self._show_market_overlay = True
        self._play_sfx(self._sfx_ui_open, key="market_open", debounce=0.12)
        if self._show_inventory_overlay:
            self._start_modal_close("inventory")
            self._play_sfx(self._sfx_ui_close, key="inventory_close", debounce=0.12)
        self._show_inventory_overlay = False
        self._show_almanac = False

    def _close_overlays(self) -> bool:
        closed = False
        if self._show_inventory_overlay:
            self._start_modal_close("inventory")
            self._show_inventory_overlay = False
            self._play_sfx(self._sfx_ui_close, key="inventory_close", debounce=0.12)
            closed = True
        if self._show_market_overlay:
            self._start_modal_close("market")
            self._show_market_overlay = False
            self._play_sfx(self._sfx_ui_close, key="market_close", debounce=0.12)
            closed = True
        if self._show_almanac:
            self._close_almanac()
            closed = True
        return closed

    def _start_modal_close(self, name: str) -> None:
        self._modal_close_at[name] = pygame.time.get_ticks() / 1000.0

    def _draw_almanac_overlay(self) -> None:
        intro = self._modal_intro("almanac", dur=0.18)
        if intro <= 0.0:
            return
        now = pygame.time.get_ticks() / 1000.0
        t_open = now - self._almanac_open_time

        scrim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        scrim.fill((10, 10, 16, int(118 * intro)))
        self.screen.blit(scrim, (0, 0))

        # Decide which goal cards are visible this frame (and their fade alpha)
        # before sizing the panel, so the plaque always fits its goals tidily.
        card_h = 74
        card_gap = 8
        visible: list[tuple[object, object, int]] = []
        for gdef, gstate in self._almanac.active_goals():
            alpha = 255
            if gstate.completed:
                if gdef.id in self._almanac_seen:
                    continue  # already watched this one fade away
                fade = max(0.0, 1.0 - t_open / ALMANAC_COMPLETED_FADE_SECONDS)
                if fade <= 0.0:
                    self._almanac_seen.add(gdef.id)
                    continue
                alpha = int(255 * fade)
            visible.append((gdef, gstate, alpha))

        pad = 18
        n = len(visible)
        cards_h = n * card_h + max(0, n - 1) * card_gap
        w = 560
        h = max(200, 56 + cards_h + 40)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (SCREEN_W // 2, SCREEN_H // 2)
        rect = ui_theme.scaled_rect(rect, 0.94 + 0.06 * intro)
        self._almanac_overlay_rect = rect

        ui_theme.panel_with_shadow(self.screen, rect, top=(70, 62, 54),
                                   bottom=(48, 41, 34), border=(156, 124, 82),
                                   radius=16, shadow_lift=10, shadow_alpha=80)

        title = f"Almanac  {self._almanac.season_name()}, Year {self._almanac.year_index + 1}"
        ui_theme.draw_text(self.screen, self._font_bold, title, ui_theme.CREAM,
                           (rect.left + 18, rect.top + 16), anchor="topleft",
                           shadow=ui_theme.SHADOW_INK, dy=1)
        self._draw_overlay_money_plaque(rect)
        self._almanac_close_button = self._draw_overlay_close(rect, "almanac")

        card_y = rect.top + 58
        card_w = rect.w - pad * 2
        for gdef, gstate, alpha in visible:
            surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            if gstate.completed:
                top_c, bot_c, bord_c, txt_c = (86, 132, 78), (54, 92, 52), (150, 196, 140), (236, 248, 228)
                fill_c = (150, 196, 120)
            else:
                top_c, bot_c, bord_c, txt_c = (62, 70, 78), (42, 48, 56), (120, 140, 152), (245, 240, 224)
                fill_c = (250, 196, 104)
            surf.blit(ui_theme.rounded_panel(card_w, card_h, top=top_c, bottom=bot_c,
                                             border=bord_c, radius=10), (0, 0))
            ui_theme.draw_text(surf, self._small_bold, gdef.description, txt_c,
                               (12, 8), anchor="topleft", shadow=(22, 16, 12), dy=1)

            target = max(1, int(gdef.target))
            ratio = max(0.0, min(1.0, gstate.progress / target))
            bar = pygame.Rect(12, 33, card_w - 24, 14)
            ui_theme.progress_bar(surf, bar, ratio, radius=7, track=(28, 22, 18),
                                 fill=fill_c, border=(224, 218, 196))
            ui_theme.draw_text(surf, self._small_font, f"{min(gstate.progress, target)}/{target}",
                               (245, 245, 245), bar.center, anchor="center",
                               shadow=(0, 0, 0), dy=1)

            if gstate.completed:
                rtxt, rcol = "Completed!", (180, 244, 178)
            else:
                rtxt = f"Reward: {gdef.reward.label}" if gdef.reward.label else "Reward"
                rcol = (250, 214, 140)
            ui_theme.draw_text(surf, self._small_font, rtxt, rcol,
                               (12, card_h - 21), anchor="topleft", shadow=(22, 16, 12), dy=1)

            if alpha < 255:
                surf.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.screen.blit(surf, (rect.left + pad, card_y))
            card_y += card_h + card_gap

        done = self._almanac.season_completed_count()
        total = self._almanac.season_goal_count()
        foot = f"{self._almanac.season_name()} goals {done}/{total}    J closes"
        ui_theme.draw_text(self.screen, self._small_font, foot, (228, 222, 202),
                           (rect.centerx, rect.bottom - 12), anchor="midbottom",
                           shadow=(30, 22, 14), dy=1)

    def _wood_panel(self, w: int, h: int) -> pygame.Surface:
        """A rounded wooden plaque matching the seed panel's wood texture.

        Cached by size: this used to smoothscale the panel image and allocate
        four surfaces every single frame for the Farm Status plaque.
        """
        key = (int(w), int(h))
        cached = self._wood_panel_cache.get(key)
        if cached is not None:
            return cached
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        if self._ui_panel_image:
            wood = pygame.transform.smoothscale(self._ui_panel_image, (w, h)).convert_alpha()
            panel.blit(wood, (0, 0))
        else:
            panel.fill((165, 103, 52, 255))
            for i in range(5):
                x = int((i + 0.5) / 5 * w)
                pygame.draw.line(panel, (150, 92, 46), (x - 6, 0), (x + 4, h), 2)
        # Slight darkening so the text stays readable on the warm wood.
        dark = pygame.Surface((w, h), pygame.SRCALPHA)
        dark.fill((40, 24, 10, 70))
        panel.blit(dark, (0, 0))
        # Round the corners by multiplying through a rounded alpha mask.
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=12)
        panel.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self._wood_panel_cache[key] = panel
        return panel

    @staticmethod
    def _format_mmss(seconds: float) -> str:
        total = max(0, int(seconds))
        minutes, secs = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    # ── bosses ─────────────────────────────────────────────────────────────
    def _visible_boss(self):
        for boss in self._bosses:
            if getattr(boss, "visible", False):
                return boss
        return None

    def _toggle_boss(self, boss):
        if getattr(boss, "visible", False):
            boss.despawn_now()
            return

        # Ensure only one boss is on-screen at a time.
        for other in self._bosses:
            if other is boss:
                continue
            other.despawn_now()
        boss.force_spawn_now()

    # ── cheats (dev helpers; see README controls) ────────────────────────
    def _give_money_cheat(self, amount: int) -> None:
        self.money += int(amount)
        if JUICE_ENABLED:
            self._float_texts.append(FloatText(self._field_rect.width + 150, 86, f"+{int(amount)}g", color=(250, 235, 140)))

    def _unlock_all_cheat(self) -> None:
        for s in self.seeds:
            self._unlocked_seeds.add(type(s).__name__)
        self._unlocked_tools.update((TOOL_COMPOST, TOOL_SCARECROW, TOOL_LIGHTNING_ROD, TOOL_BELL))
        # Grant resources so the boss-reward crop/tools are immediately usable.
        self.inventory["Storm Crystal"] = self.inventory.get("Storm Crystal", 0) + 5
        self.inventory["Compost"] = self.inventory.get("Compost", 0) + 5
        self._show_sell_feedback("Cheat: all seeds and tools unlocked (+5 Storm Crystal, +5 Compost)")

    def _update_bosses(self, dt: float) -> None:
        visible = self._visible_boss()
        # A boss visit is one "fight": reset the per-visit blight tally on arrival.
        active_now = visible is not None
        if active_now and not self._boss_was_active:
            self._fight_blight_hits = 0
            self._fight_blight_spreads = 0
        self._boss_was_active = active_now

        if visible is not None:
            visible.update_battle(dt, slots=self.slots, clouds=self.clouds)
            spawn_dt = dt * (TEMPEST_SPAWN_MULT if self._tempest_active else 1.0)
            for boss in self._bosses:
                if boss is visible:
                    continue
                boss.tick_spawn_timer(spawn_dt)
        else:
            # No boss on screen; allow a single boss to spawn (faster during the Tempest).
            spawn_dt = dt * (TEMPEST_SPAWN_MULT if self._tempest_active else 1.0)
            for boss in self._bosses:
                boss.update_battle(spawn_dt, slots=self.slots, clouds=self.clouds)
                if boss.visible:
                    break

        active_ids = {id(b) for b in self._bosses if getattr(b, "state", None) == StormTitan.STATE_ACTIVE}
        for boss in self._bosses:
            if id(boss) in active_ids and id(boss) not in self._prev_active_boss_ids:
                self._boss_arrivals[id(boss)] = 0.48
                self._combo_crossed[id(boss)] = False
                self._play_sfx(self._sfx_boss_spawn, key="boss_spawn", debounce=0.25)
        self._prev_active_boss_ids = active_ids

        # Deliver boss rewards + feed block/survive events to the Almanac.
        for boss in self._bosses:
            for name, count in boss.pop_reward():
                self.inventory[name] = self.inventory.get(name, 0) + count
            for _ in range(boss.pop_blocks() if hasattr(boss, "pop_blocks") else 0):
                self._almanac.on_event(GoalKind.BLOCK_BOSS)
            for _ in range(boss.pop_survived() if hasattr(boss, "pop_survived") else 0):
                self._almanac.on_event(GoalKind.SURVIVE_BOSS, product=getattr(boss, "boss_id", None))
                self._almanac.on_titan_defeated()
            if hasattr(boss, "pop_unblocked_hits"):
                for idx in boss.pop_unblocked_hits():
                    self._apply_blight_hit(idx)

    def _apply_blight_hit(self, idx: int) -> None:
        # The struck plot is blighted. From the 2nd unblocked hit of a fight on,
        # the blight also creeps to one healthy neighbor (capped), so a sloppy
        # defense visibly eats the field. It all heals at the season boundary.
        if not (0 <= idx < len(self.slots)):
            return
        self.slots[idx].apply_blight(1.0)
        self._spawn_blight_juice(self.slots[idx])
        self._fight_blight_hits += 1
        if self._fight_blight_hits >= 2 and self._fight_blight_spreads < 4:
            neighbors = [j for j in (idx - 1, idx + 1)
                         if 0 <= j < len(self.slots) and self.slots[j].blight <= 0.0]
            if neighbors:
                self.slots[self._rng.choice(neighbors)].apply_blight(1.0)
                self._fight_blight_spreads += 1

    def _draw_sky_forecast(self) -> None:
        # Glanceable telegraph: when the next titan is within the forecast window and
        # no boss is active, show an "incoming" pill that fills and reddens as it nears,
        # so escalation is something you see coming, not a surprise.
        if not JUICE_ENABLED:
            return
        if any(b.state == StormTitan.STATE_ACTIVE for b in self._bosses):
            return
        upcoming = [b for b in self._bosses
                    if getattr(b, "enabled", True) and b.state == StormTitan.STATE_WAITING]
        if not upcoming:
            return
        nearest = min(upcoming, key=lambda b: b.seconds_until_spawn)
        secs = float(nearest.seconds_until_spawn)
        if secs <= 0.0 or secs > SKY_FORECAST_WINDOW_SECONDS:
            return
        p = 1.0 - secs / float(SKY_FORECAST_WINDOW_SECONDS)   # 0 (far) -> 1 (imminent)
        col = (240, int(200 - 120 * p), int(80 - 60 * p))     # amber -> red as it nears
        name = getattr(nearest, "display_name", "Boss")
        label = self._small_bold.render(f"{name} incoming   {self._format_mmss(secs)}", True, (255, 240, 224))
        w = label.get_width() + 28
        h = 32
        x = self._field_rect.width // 2 - w // 2
        y = 8
        pill = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(pill, (22, 24, 32, 205), pill.get_rect(), border_radius=9)
        pygame.draw.rect(pill, (*col, 225), pill.get_rect(), 2, border_radius=9)
        pill.blit(label, (14, 5))
        bw = w - 16
        pygame.draw.rect(pill, (48, 52, 60, 220), (8, h - 8, bw, 4), border_radius=2)
        pygame.draw.rect(pill, col, (8, h - 8, int(bw * p), 4), border_radius=2)
        self.screen.blit(pill, (x, y))

    def _draw_boss_health_bar(self) -> None:
        boss = self._visible_boss()
        if boss is None:
            return

        max_hp = max(1, int(getattr(boss, "max_hp", 1)))
        hp = max(0, int(getattr(boss, "hp", 0)))
        ratio = max(0.0, min(1.0, hp / max_hp))

        cfg = getattr(boss, "config", None)
        width = int(getattr(cfg, "health_bar_width", 360))
        height = int(getattr(cfg, "health_bar_height", 18))

        field_w = self._field_rect.width
        width = max(180, min(width, field_w - 20))
        height = max(12, min(height, 32))

        bar = pygame.Rect(0, 0, width, height)
        bar.midtop = (field_w // 2, 9)

        # Clean rounded pill: soft shadow, dark track, two-tone red fill + gloss.
        radius = height // 2
        ui_theme.soft_shadow(self.screen, bar, radius=radius, lift=4, pad=8,
                             layers=3, alpha=52)
        ui_theme.progress_bar(self.screen, bar, ratio, radius=radius,
                              track=(30, 20, 18), fill=(212, 64, 60),
                              fill_hi=(255, 126, 110), border=(255, 238, 226))

        if boss is self.inferno_titan:
            phase = getattr(boss, "current_phase", PHASE_STORM)
            fire = getattr(boss, "_fire_ability", None)
            if phase == PHASE_INFERNO:
                name = "FIRESTORM" if fire == FIRE_FIRESTORM else "LAVA SURGE"
                rule = "clouds cover marks" if fire == FIRE_FIRESTORM else "cloud covers tile"
            else:
                name = str(phase).upper()
                rule = {
                    PHASE_STORM: "cloud blocks bolt",
                    PHASE_CYCLONE: "rain cloud blocks",
                    PHASE_DROUGHT: "cloud covers sun",
                    PHASE_FROST: "clouds cover marks",
                }.get(phase, "cloud blocks")
            phase_color = PHASE_COLORS.get(phase, (255, 235, 120))
            text = f"{name}: {rule}"
            chip = pygame.Rect(0, 0, self._small_bold.size(text)[0] + 28, 28)
            chip.midtop = (field_w // 2, bar.bottom + 6)
            ui_theme.panel_with_shadow(self.screen, chip,
                                      top=ui_theme.lerp_col(phase_color, (40, 36, 44), 0.55),
                                      bottom=(34, 30, 38), border=phase_color,
                                      radius=11, shadow_lift=4, shadow_alpha=48)
            ui_theme.draw_text(self.screen, self._small_bold, text, ui_theme.CREAM,
                              chip.center, anchor="center", shadow=(0, 0, 0), dy=1)

        # Block-streak multiplier: show the consecutive-block combo building toward
        # the bonus-damage threshold, so clean fights feel visibly rewarded.
        combo = int(getattr(boss, "block_combo", 0))
        if combo > 0:
            at_bonus = combo >= int(BOSS_COMBO_THRESHOLD)
            color = (255, 215, 90) if at_bonus else (235, 235, 245)
            scale = 1.0 + (0.18 if at_bonus else 0.0)
            font = self._font
            label = f"x{combo} STREAK" + ("  BONUS!" if at_bonus else "")
            surf = font.render(label, True, color)
            if scale != 1.0:
                surf = pygame.transform.rotozoom(surf, 0, scale)
            sh = font.render(label, True, (25, 20, 20))
            combo_y = bar.bottom + (38 if boss is self.inferno_titan else 4)
            rect = surf.get_rect(midtop=(field_w // 2, combo_y))
            self.screen.blit(sh, sh.get_rect(midtop=(field_w // 2 + 1, combo_y + 1)))
            self.screen.blit(surf, rect)

    # ── critters ─────────────────────────────────────────────────────────
    def _update_critters(self, dt: float) -> None:
        for critter in self._critters:
            critter.update(dt, slots=self.slots, field_rect=self._field_rect, ground_rect=self._ground_rect)
            for ev in getattr(critter, "pop_juice_events", lambda: [])():
                kind = ev.get("kind")
                name = str(ev.get("name", "")).lower()
                pos = ev.get("pos", getattr(critter, "rect", pygame.Rect(0, 0, 0, 0)).center)
                if kind == "spawn":
                    self._play_sfx(self._sfx_critter_spawn, key=f"critter_spawn:{name}", debounce=0.12)
                    self._play_sfx(self._sfx_snake_hiss if "snake" in name else self._sfx_squirrel_chirp,
                                   key=f"critter_species:{name}", debounce=0.25)
                    self._spawn_critter_spawn_juice(pos)
                elif kind == "scare":
                    self._play_sfx(self._sfx_critter_scare, key=f"critter_scare:{name}", debounce=0.08)
                    self._spawn_critter_scare_juice(pos)
                elif kind == "steal":
                    self._play_sfx(self._sfx_critter_steal, key=f"critter_steal:{name}", debounce=0.12)
                    self._spawn_critter_steal_juice(pos)
            # collect any drop produced by the critter (e.g., Fur, Venom)
            drop = getattr(critter, "_last_drop", None)
            if drop:
                try:
                    name, count = drop
                    self.inventory[name] = self.inventory.get(name, 0) + int(count)
                except Exception:
                    pass
                critter._last_drop = None

    def _update_bees(self, dt: float) -> None:
        # Bees only show up in fair weather, during the day, and only if there is
        # at least one flowering crop worth visiting. Otherwise active bees head
        # home. The gate is recomputed every frame so a harvest or nightfall ends
        # the visit naturally.
        is_day = self._darkness < 0.5
        weather_calm = self._weather_event in ("None", "Drizzle")
        has_flower = any(
            getattr(s.seed, "pollinatable", False) and not s.dead
            and float(getattr(s, "growth_ratio", 0.0)) >= 0.35
            for s in self.slots if s.seed is not None
        )
        can_spawn = is_day and weather_calm and has_flower
        for bee in self._bees:
            bee.set_can_spawn(can_spawn)
            if bee.active and not is_day:
                bee.dismiss(field_rect=self._field_rect)
            bee.update(dt, slots=self.slots, field_rect=self._field_rect, ground_rect=self._ground_rect)
            if bee.active and id(bee) not in self._prev_bee_active:
                self._play_sfx(self._sfx_bee_buzz, key=f"bee:{id(bee)}", debounce=1.0)
            idx = bee.serviced_slot_index
            if idx is not None and 0 <= idx < len(self.slots) and JUICE_ENABLED and self._rng.random() < dt * 7.0:
                sx, sy = self.slots[idx].rect.center
                glow = effects.radial_glow(3, (250, 230, 120), 120)
                self._particles.append(Particle(
                    sx + self._rng.uniform(-16, 16), sy + self._rng.uniform(-24, 2),
                    vx=self._rng.uniform(-12, 12), vy=self._rng.uniform(-24, -6),
                    life=0.65, max_life=0.65, image=glow, gravity=0.0))
                self._cap_particles()
        self._prev_bee_active = {id(bee) for bee in self._bees if bee.active}

    def _drain_crow_events(self) -> None:
        for ev in self._crows.pop_juice_events():
            kind = ev.get("kind")
            pos = ev.get("pos", (0, 0))
            if kind == "spawn":
                self._play_sfx(self._sfx_crow_caw, key="crow_spawn", debounce=0.18)
            elif kind == "dive":
                self._play_sfx(self._sfx_crow_dive_wings, key="crow_dive", debounce=0.12)
            elif kind == "steal":
                self._play_sfx(self._sfx_crow_grab, key="crow_grab", debounce=0.08)
                self._play_sfx(self._sfx_critter_steal, key="crow_steal", debounce=0.12)
                self._spawn_crow_steal_juice(pos, str(ev.get("target", "plant")))

    def _drain_miniboss_events(self) -> None:
        for ev in self._minibosses.pop_juice_events():
            kind = ev.get("kind")
            name = str(ev.get("name", ""))
            pos = ev.get("pos", (self._field_rect.centerx, self._ground_rect.top))
            if kind == "spawn":
                self._play_sfx(self._sfx_miniboss_spawn, key="miniboss_spawn", debounce=0.18)
            elif kind == "counter":
                self._play_sfx(self._sfx_miniboss_counter, key="miniboss_counter", debounce=0.06)
                self._spawn_miniboss_juice(name, "counter", pos)
            elif kind == "fail":
                self._play_sfx(self._sfx_miniboss_resolve_fail, key="miniboss_fail", debounce=0.10)
                self._spawn_miniboss_juice(name, "fail", pos)

    def _bee_growth_mult(self) -> list[float]:
        """Per-slot growth multiplier from bees servicing in-range flowers."""
        mult = [1.0] * len(self.slots)
        for bee in self._bees:
            idx = bee.serviced_slot_index
            if idx is None or idx < 0 or idx >= len(self.slots):
                continue
            slot = self.slots[idx]
            # Keystone guard: a bee only helps a crop you have already put in
            # its healthy band. It never rescues an out-of-band crop.
            if slot.seed is not None and not slot.dead and slot.in_range:
                mult[idx] = float(BEE_GROWTH_MULT)
        return mult

    def _draw_critters(self) -> None:
        for critter in self._critters:
            critter.draw(self.screen)
        self._crows.draw(self.screen)
        for bee in self._bees:
            bee.draw(self.screen)

    def _handle_critter_event(self, event: pygame.event.Event) -> bool:
        if self.paused:
            return False
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if event.pos[0] > self._field_rect.width:
            return False
        for critter in self._critters:
            if critter.active and critter.rect.collidepoint(event.pos):
                critter.scare_away(field_rect=self._field_rect)
                return True
        return False

    def _handle_miniboss_event(self, event: pygame.event.Event) -> bool:
        if self.paused:
            return False
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if event.pos[0] > self._field_rect.width:
            return False
        return self._minibosses.handle_click(event.pos)

    def _handle_crow_click(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        clicked = None
        for crow in self._crows:
            rect = getattr(crow, "rect", None)
            if getattr(crow, "active", False) and isinstance(rect, pygame.Rect) and rect.collidepoint(event.pos):
                clicked = crow
                break
        if not self._crows.handle_click(event, field_rect=self._field_rect):
            return False
        if clicked is not None:
            self._spawn_crow_shoo(clicked.rect.center)
        return True

    def _ring_bell(self) -> None:
        # The bell costs gold and goes on cooldown, so it is a timed, paid answer
        # to a crow raid rather than free spam. It only charges when there is at
        # least one crow to scare, so a mistaken empty ring is not punished.
        if not self._is_tool_unlocked(TOOL_BELL):
            self._play_sfx(self._sfx_ui_error, key="bell_error", debounce=0.15)
            return
        if not self._bell.ready:
            self._play_sfx(self._sfx_ui_error, key="bell_error", debounce=0.15)
            return
        if not any(c.active for c in self._crows):
            self._play_sfx(self._sfx_ui_error, key="bell_error", debounce=0.15)
            return
        if self.money < int(BELL_RING_COST):
            self._money_flash_timer = 20
            self._play_sfx(self._sfx_ui_error, key="bell_error", debounce=0.15)
            return
        crow_positions = [c.rect.center for c in self._crows if c.active]
        self._bell.ring(list(self._crows), field_rect=self._field_rect)
        self.money -= int(BELL_RING_COST)
        self._play_sfx(self._sfx_bell, key="bell_ring", debounce=0.2)
        for pos in crow_positions:
            self._spawn_crow_shoo(pos, play_sfx=False)

    def _create_slots(self) -> list[PlantSlot]:
        slots: list[PlantSlot] = []
        total_padding = SLOT_PADDING * (SLOT_COUNT + 1)
        slot_width = (self._field_rect.width - total_padding) // SLOT_COUNT
        slot_height = max(20, self._ground_height - SLOT_PADDING * 2)
        y = self._ground_rect.top + (self._ground_height - slot_height) // 2
        for i in range(SLOT_COUNT):
            x = SLOT_PADDING + i * (slot_width + SLOT_PADDING)
            rect = pygame.Rect(x, y, slot_width, slot_height)
            slots.append(PlantSlot(rect))
        return slots

    def _update_plants(self):
        sun_clear = not any(c.covers_sun(self.sun.circle_rect) for c in self.clouds)
        dt = self._frame_dt()
        # Water/sun constants are authored as "per frame at 60 FPS"; scale them by
        # dt*FPS so the watering challenge runs at the same real-time rate on any
        # hardware (= 1.0 at a true 60 FPS, so the tuned balance is unchanged).
        frame_scale = dt * float(FPS)

        season_idx = self._season_index
        growth_mult = float(SEASON_GROWTH_MULT[season_idx % len(SEASON_GROWTH_MULT)]) if SEASON_GROWTH_MULT else 1.0
        water_loss_mult = float(SEASON_WATER_LOSS_MULT[season_idx % len(SEASON_WATER_LOSS_MULT)]) if SEASON_WATER_LOSS_MULT else 1.0
        sun_gain_mult = float(SEASON_SUN_GAIN_MULT[season_idx % len(SEASON_SUN_GAIN_MULT)]) if SEASON_SUN_GAIN_MULT else 1.0

        event_water_loss_mult = 1.0
        event_sun_gain_mult = 1.0
        event_water_bonus = 0.0
        if self._weather_event == "Heatwave":
            event_water_loss_mult = float(WEATHER_HEATWAVE_WATER_LOSS_MULT)
            event_sun_gain_mult = float(WEATHER_HEATWAVE_SUN_GAIN_MULT)
        elif self._weather_event == "Drizzle":
            event_water_bonus = float(WEATHER_DRIZZLE_WATER_BONUS)
            event_sun_gain_mult = float(WEATHER_DRIZZLE_SUN_GAIN_MULT)

        # Adjacency + boss-state pre-pass (O(n)): a mature Sunflower warms its
        # immediate neighbors, and active bosses speed up storm-fed crops.
        n = len(self.slots)
        neighbor_sun_bonus = [0.0] * n
        neighbor_sun_penalty = [0.0] * n   # Fern canopy shades both neighbors (sun subtracted)
        neighbor_water_bonus = [0.0] * n   # Reed soaker waters both neighbors (water added)
        for i, s in enumerate(self.slots):
            sd = s.seed
            if sd is None or s.dead:
                continue
            bonus = getattr(sd, "neighbor_sun_bonus", 0.0)
            if bonus and s.harvestable:
                if i - 1 >= 0:
                    neighbor_sun_bonus[i - 1] += bonus
                if i + 1 < n:
                    neighbor_sun_bonus[i + 1] += bonus
            penalty = getattr(sd, "neighbor_sun_penalty", 0.0)
            if penalty and s.harvestable:
                if i - 1 >= 0:
                    neighbor_sun_penalty[i - 1] += penalty
                if i + 1 < n:
                    neighbor_sun_penalty[i + 1] += penalty
            water_share = getattr(sd, "neighbor_water_bonus", 0.0)
            if water_share and s.harvestable:
                if i - 1 >= 0:
                    neighbor_water_bonus[i - 1] += water_share
                if i + 1 < n:
                    neighbor_water_bonus[i + 1] += water_share
        boss_active = any(b.state == StormTitan.STATE_ACTIVE for b in self._bosses)
        bee_mult = self._bee_growth_mult()

        for i, slot in enumerate(self.slots):
            cloud_over_slot = any(c.rect.left <= slot.rect.centerx <= c.rect.right for c in self.clouds)
            raining_over_slot = any(c.raining and c.rect.left <= slot.rect.centerx <= c.rect.right for c in self.clouds)
            heavy_rain_over_slot = any(getattr(c, "heavy_rain", False) and c.rect.left <= slot.rect.centerx <= c.rect.right for c in self.clouds)
            water_delta = -WATER_LOSS * water_loss_mult * event_water_loss_mult
            water_delta += event_water_bonus
            water_delta += neighbor_water_bonus[i]  # Reed waters its neighbors
            sun_delta = -SUN_LOSS

            if heavy_rain_over_slot:
                water_delta += WATER_GAIN_RAIN_HEAVY
            elif raining_over_slot:
                water_delta += WATER_GAIN_RAIN_LIGHT
            _sid = id(slot)
            if raining_over_slot:
                self._slot_rain_secs[_sid] = self._slot_rain_secs.get(_sid, 0.0) + dt
            else:
                self._slot_rain_secs.pop(_sid, None)
            # Only splash once a drop has had time to fall from the cloud to the soil.
            if (JUICE_ENABLED and raining_over_slot and self._slot_rain_secs.get(_sid, 0.0) > 0.34
                    and self._rng.random() < dt * (10.0 if heavy_rain_over_slot else 5.5)):
                self._spawn_rain_splash(slot)
            if sun_clear and not cloud_over_slot:
                sun_gain = SUN_GAIN_CLEAR * sun_gain_mult * event_sun_gain_mult
                sun_delta += sun_gain
            sun_delta += neighbor_sun_bonus[i]  # Sunflower warms its neighbors
            sun_delta -= neighbor_sun_penalty[i]  # Fern shades its neighbors

            slot_growth_mult = growth_mult
            if heavy_rain_over_slot:
                slot_growth_mult *= float(HEAVY_RAIN_GROWTH_MULT)
            if self._weather_event == "Drizzle":
                slot_growth_mult *= float(WEATHER_DRIZZLE_GROWTH_MULT)
            if getattr(slot, "compost_boost_remaining", 0.0) > 0.0:
                slot_growth_mult *= float(COMPOST_GROWTH_MULT)
            if getattr(slot, "blight", 0.0) > 0.0:
                slot_growth_mult *= float(slot.growth_blight_mult)  # blighted soil grows slower
            if boss_active:
                slot_growth_mult *= float(getattr(slot.seed, "boss_growth_mult", 1.0))
            # Moonpetal only advances growth while the sky is dark (night/shade).
            if getattr(slot.seed, "grows_only_at_night", False) and self._darkness < 0.5:
                slot_growth_mult = 0.0
            water_delta *= frame_scale
            sun_delta *= frame_scale
            slot.update(
                water_delta,
                sun_delta,
                water_kill=OVERWATER_THRESHOLD,
                sun_kill=OVERSUN_THRESHOLD,
                bad_seconds_to_die=PLANT_BAD_SECONDS_TO_DIE,
                bad_recovery_rate=PLANT_BAD_RECOVERY_RATE,
                growth_rate_good=PLANT_GROWTH_RATE_GOOD * slot_growth_mult * bee_mult[i],
                growth_rate_bad=PLANT_GROWTH_RATE_BAD * slot_growth_mult,
                dt=dt,
            )

        currently_harvestable = {id(s) for s in self.slots if s.harvestable}
        newly_ready = currently_harvestable - self._prev_harvestable
        if newly_ready:
            if self._sfx_ready_harvest:
                self._sfx_ready_harvest.play()
            if JUICE_ENABLED:
                for s in self.slots:
                    if id(s) in newly_ready:
                        self._spawn_ready_sparkle(s)
        self._prev_harvestable = currently_harvestable

        # Three-act death telegraph. Act 1 (wilt) and Act 2 (last gasp + droop)
        # are drawn from bad_ratio in PlantSlot.draw. Here we fire the audio cue on
        # entering danger, the relief beat when a plant is rescued from Act 2, and
        # the loss beat the instant a plant dies.
        currently_shaking = {id(s) for s in self.slots if s.planted and not s.dead and s.bad_ratio > 0}
        if self._sfx_will_die and (currently_shaking - self._prev_shaking):
            self._sfx_will_die.play()
        self._prev_shaking = currently_shaking

        deep_danger = {id(s) for s in self.slots if s.planted and not s.dead and s.bad_ratio >= 0.5}
        rescued = self._danger_slots - deep_danger
        if rescued:
            for s in self.slots:
                if id(s) in rescued and s.planted and not s.dead and s.bad_ratio < 0.15:
                    self._spawn_relief(s)
        self._danger_slots = deep_danger

        currently_dead = {id(s) for s in self.slots if s.dead}
        newly_dead = currently_dead - self._prev_dead
        if newly_dead:
            for s in self.slots:
                if id(s) in newly_dead:
                    self._spawn_death(s)
        self._prev_dead = currently_dead

        # Spring "sun-lover and shade-lover happy at once" goal: latch once a season.
        if not self._coexist_latched:
            has_sun = any(s.planted and not s.dead and s.in_range
                          and getattr(s.seed, "sun_min", 0) >= 55 for s in self.slots)
            has_shade = any(s.planted and not s.dead and s.in_range
                            and getattr(s.seed, "sun_max", 100) <= 45 for s in self.slots)
            if has_sun and has_shade:
                self._coexist_latched = True
                self._almanac.on_event(GoalKind.COEXIST_SUN_SHADE, None, 1)

    def _spawn_relief(self, slot: PlantSlot) -> None:
        # A rescued crop springs back: a bright green ring of relief particles.
        if not JUICE_ENABLED:
            if self._sfx_relief:
                self._sfx_relief.play()
            return
        cx = slot.rect.centerx
        cy = slot.rect.centery
        for _ in range(8):
            self._particles.append(Particle(
                cx, cy, vx=self._rng.uniform(-60, 60), vy=self._rng.uniform(-90, -30),
                life=0.5, max_life=0.5, color=(150, 235, 150), size=self._rng.randint(2, 3)))
        if self._sfx_relief:
            self._sfx_relief.play()

    def _spawn_death(self, slot: PlantSlot) -> None:
        self._market.mark_threat(THREAT_CROP_DEATH)
        # The loss beat: micro-hitstop, a collapse pop, a soil puff, a dull thud,
        # and a red sinking loss text showing the seed value wasted.
        cost = int(getattr(slot.seed, "cost", 0)) if slot.seed else 0
        cx = slot.rect.centerx
        by = slot.rect.bottom - 6
        if JUICE_ENABLED:
            self._hitstop_remaining = max(self._hitstop_remaining, 0.04)
            img = self._phase_image_for_slot(slot)
            if img is not None:
                self._particles.append(Particle(cx, slot.rect.centery, vy=18.0, life=0.32, max_life=0.32,
                                                image=img, gravity=120.0))
            for _ in range(9):
                self._particles.append(Particle(
                    cx + self._rng.uniform(-10, 10), by,
                    vx=self._rng.uniform(-50, 50), vy=self._rng.uniform(-70, -20),
                    life=self._rng.uniform(0.4, 0.6), max_life=0.6,
                    color=(110, 95, 80), size=self._rng.randint(2, 4)))
            if cost > 0:
                self._float_texts.append(FloatText(cx, slot.rect.top - 4, f"-{cost}g",
                                                   color=(225, 90, 80), life=0.9, max_life=0.9))
        if self._sfx_death:
            self._sfx_death.play()

    def _draw_ground(self):
        if self._ground_surf is None:
            self._ground_surf = self._build_ground_surface()
        self.screen.blit(self._ground_surf, self._ground_rect.topleft)

    def _build_ground_surface(self) -> pygame.Surface:
        # Tilled-soil strip. Prefer the painted props/ground.png tile (scaled to the
        # strip), and fall back to the procedural fill if the asset is missing.
        w, h = self._ground_rect.size
        ground_png = os.path.join(PROPS_DIR, "ground.png")
        if os.path.exists(ground_png):
            try:
                raw = pygame.image.load(ground_png).convert_alpha()
                surf = pygame.Surface((w, h))
                surf.fill(GROUND_COLOR)
                surf.blit(pygame.transform.smoothscale(raw, (w, h)), (0, 0))
                return surf
            except Exception:
                pass
        # Built once: base soil, a darker topsoil line where it meets the field,
        # and a deterministic scatter of clods so the strip does not read flat.
        surf = pygame.Surface((w, h))
        surf.fill(GROUND_COLOR)
        top_dark = tuple(max(0, c - 30) for c in GROUND_COLOR)
        light = tuple(min(255, c + 16) for c in GROUND_COLOR)
        dark = tuple(max(0, c - 18) for c in GROUND_COLOR)
        pygame.draw.rect(surf, top_dark, (0, 0, w, 3))
        pygame.draw.line(surf, light, (0, 3), (w, 3))
        rng = random.Random(20240613)
        for _ in range(max(40, (w * h) // 1400)):
            x = rng.randint(0, w - 2)
            y = rng.randint(6, h - 2)
            col = dark if rng.random() < 0.62 else light
            size = 2 if rng.random() < 0.35 else 1
            pygame.draw.rect(surf, col, (x, y, size, size))
        return surf

    def _draw_shadow(self):
        for c in self.clouds:
            shadow_width = int(c.rect.width * 1.15)
            shadow_height = int(self._ground_height * 0.75)
            shadow_x = c.rect.centerx - shadow_width // 2
            shadow_y = self._ground_rect.top + (self._ground_height - shadow_height) // 2
            shadow_x = max(0, min(shadow_x, self._field_rect.width - shadow_width))

            key = (shadow_width, shadow_height)
            shadow = self._shadow_cache.get(key)
            if shadow is None:
                # A soft, feathered shadow: nested ellipses fading inward so it reads
                # as a gentle shade on the tilled soil, not a dark pit.
                shadow = pygame.Surface((shadow_width, shadow_height), pygame.SRCALPHA)
                steps = 6
                for i in range(steps, 0, -1):
                    f = i / steps
                    a = int(70 * (1.0 - f) + 14)
                    rw = max(2, int(shadow_width * f))
                    rh = max(2, int(shadow_height * f))
                    rx = (shadow_width - rw) // 2
                    ry = (shadow_height - rh) // 2
                    pygame.draw.ellipse(shadow, (12, 14, 18, a), (rx, ry, rw, rh))
                self._shadow_cache[key] = shadow
            self.screen.blit(shadow, (shadow_x, shadow_y))

    def _draw_slots(self):
        for slot in self.slots:
            phase_image = self._phase_image_for_slot(slot)
            slot.draw(
                self.screen,
                SLOT_COLOR,
                SLOT_BORDER_COLOR,
                phase_image=phase_image,
                dead_image=self._dead_plant_image,
            )
        self._draw_combo_tells()
        self._draw_scarecrow_zones()

    def _draw_combo_tells(self) -> None:
        # Surface the emergent combos that already exist in the sim but were invisible:
        # Sunflower's neighbor sun-buff, Lightning Vine's strike-surge, and blight spread.
        if not JUICE_ENABLED:
            return
        n = len(self.slots)
        boss_active = any(b.state == StormTitan.STATE_ACTIVE for b in self._bosses)
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.005)
        t = pygame.time.get_ticks() * 0.01
        for i, s in enumerate(self.slots):
            sd = s.seed
            if sd is None or s.dead:
                continue
            # Sunflower: warm aura on its two neighbours while it is mature (matches the
            # sim, which only adds neighbour sun once the Sunflower is harvestable).
            if getattr(sd, "neighbor_sun_bonus", 0.0) > 0.0 and s.harvestable:
                for j in (i - 1, i + 1):
                    if 0 <= j < n and self.slots[j].planted and not self.slots[j].dead:
                        nb = self.slots[j].rect
                        glow = effects.radial_glow(int(nb.width * 0.55), (255, 200, 90), int(38 + 26 * pulse))
                        self.screen.blit(glow, glow.get_rect(center=(nb.centerx, nb.centery - 6)))
            # Lightning Vine: during a boss raid it surges instead of dying, so crackle
            # to signal "you can let this one get hit."
            if getattr(sd, "lightning_surge_on_strike", False) and boss_active and not s.harvestable:
                r = s.rect
                glow = effects.radial_glow(int(r.width * 0.5), (90, 170, 255), int(46 + 40 * pulse))
                self.screen.blit(glow, glow.get_rect(center=(r.centerx, r.centery - 6)))
                for k in range(3):
                    bx = r.centerx + int(math.sin(t + k * 2.1) * r.width * 0.26)
                    by = r.top - 8 - k * 5
                    pygame.draw.line(self.screen, (150, 210, 255), (bx, by), (bx + 3, by - 6), 2)
        # Blight adjacency: a faint warning edge on healthy slots next to a blighted one.
        for i, s in enumerate(self.slots):
            if getattr(s, "blight", 0.0) > 0.0 or not s.planted or s.dead:
                continue
            if any(0 <= j < n and getattr(self.slots[j], "blight", 0.0) > 0.0 for j in (i - 1, i + 1)):
                r = s.rect.inflate(-4, -4)
                edge = pygame.Surface(r.size, pygame.SRCALPHA)
                pygame.draw.rect(edge, (120, 140, 70, int(46 + 30 * pulse)), edge.get_rect(), 2, border_radius=4)
                self.screen.blit(edge, r.topleft)

    def _draw_scarecrow_zones(self) -> None:
        scarecrows = [s for s in self.slots if getattr(s, "has_scarecrow", False)]
        if not scarecrows:
            return
        radius = max(0, int(CRITTER_SCARECROW_AVOID_RADIUS_SLOTS))
        active = (self.selected_tool == TOOL_SCARECROW) or any(getattr(c, "active", False) for c in self._critters)
        alpha = int(SCARECROW_ZONE_ALPHA_ACTIVE if active else SCARECROW_ZONE_ALPHA)
        covered: set[int] = set()
        for sc in scarecrows:
            srect = sc.rect
            if radius <= 0:
                covered.add(id(sc))
                continue
            reach = radius * max(srect.width, srect.height) * 1.4
            for slot in self.slots:
                trect = slot.rect
                if abs(srect.centerx - trect.centerx) <= reach and abs(srect.centery - trect.centery) <= reach:
                    covered.add(id(slot))
        for slot in self.slots:
            if id(slot) not in covered:
                continue
            r = slot.rect.inflate(-4, -4)
            overlay = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            overlay.fill((*SCARECROW_ZONE_COLOR, alpha))
            self.screen.blit(overlay, r.topleft)
            pygame.draw.rect(self.screen, SCARECROW_ZONE_COLOR, r, 1, border_radius=4)

    def _draw_shop_tile(self, rect, key, *, selected=False, affordable=True,
                        locked=False, t=0.0):
        """Draw a shop tile's plate with eased hover/press, return its draw rect.

        The source rect is the logical hit-test and is never mutated; only the
        returned (possibly scaled) draw rect moves, exactly like the titans keep
        self.rect stable while blitting a transformed copy.
        """
        hovered = rect.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pos()[0] >= self._field_rect.width
        pressed = hovered and bool(pygame.mouse.get_pressed()[0])
        hov, scl = self._ui_motion.tween(key, hovered, pressed, self._ui_dt,
                                         hover_scale=1.07, press_scale=0.93)
        draw_rect = ui_theme.scaled_rect(rect, scl)
        if locked:
            ui_theme.button_plate(self.screen, draw_rect, style="locked",
                                  hover=hov, pressed=pressed, radius=10)
        elif selected:
            glow = 0.55 + 0.3 * effects.pulse(t, 1.8)
            ui_theme.button_plate(self.screen, draw_rect, style="primary",
                                  hover=hov, pressed=pressed, radius=10, glow=glow)
        elif affordable:
            ui_theme.button_plate(self.screen, draw_rect, style="tile",
                                  hover=hov, pressed=pressed, radius=10)
        else:
            tile = ui_theme.style_colors("tile")
            colors = (ui_theme.lerp_col(tile[0], (78, 84, 92), 0.62),
                      ui_theme.lerp_col(tile[1], (56, 62, 70), 0.62),
                      ui_theme.lerp_col(tile[2], (98, 104, 112), 0.62))
            ui_theme.button_plate(self.screen, draw_rect, colors=colors,
                                  hover=hov, pressed=pressed, radius=10)
        return draw_rect

    def _draw_tile_cost(self, draw_rect, text, *, coin=True, dim=False):
        """Coin + cost (or quantity) badge along the bottom of a shop tile."""
        coin_small = self._coin_small
        color = (220, 224, 232) if dim else (255, 248, 224)
        cost_text = self._small_bold.render(text, True, color)
        cost_y = draw_rect.bottom - 11
        if coin and coin_small:
            coin_rect = coin_small.get_rect(center=(draw_rect.centerx - 9, cost_y + 1))
            shadow = cost_text.copy()
            shadow.fill((0, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self.screen.blit(coin_small, coin_rect)
            cr = cost_text.get_rect(midleft=(coin_rect.right + 3, coin_rect.centery))
            self.screen.blit(shadow, (cr.x + 1, cr.y + 1))
            self.screen.blit(cost_text, cr)
        else:
            cr = cost_text.get_rect(midbottom=(draw_rect.centerx, draw_rect.bottom - 3))
            shadow = cost_text.copy()
            shadow.fill((0, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self.screen.blit(shadow, (cr.x + 1, cr.y + 1))
            self.screen.blit(cost_text, cr)

    def _draw_ui_panel(self):
        panel_rect = pygame.Rect(self._field_rect.width, 0, UI_PANEL_W, SCREEN_H)
        if self._ui_panel_image:
            self.screen.blit(self._ui_panel_image, panel_rect)
        else:
            pygame.draw.rect(self.screen, (40, 45, 55), panel_rect)
            pygame.draw.line(self.screen, (70, 75, 90), (panel_rect.left, 0), (panel_rect.left, SCREEN_H), 2)

        left = panel_rect.left + 16
        t_now = pygame.time.get_ticks() / 1000.0
        mouse = pygame.mouse.get_pos()
        mouse_down = bool(pygame.mouse.get_pressed()[0])
        in_panel = mouse[0] >= panel_rect.left
        dt = self._ui_dt

        # Save button (top-right). Its LOGICAL rect is unchanged; hover/press
        # only transform the drawn copy, so the click target never moves.
        self._save_button = pygame.Rect(panel_rect.right - 16 - 66, 14, 66, 26)
        saving = self._save_flash_timer > 0
        save_hovered = in_panel and self._save_button.collidepoint(mouse)
        s_hov, s_scl = self._ui_motion.tween("save", save_hovered, save_hovered and mouse_down, dt)
        ui_theme.button(self.screen, ui_theme.scaled_rect(self._save_button, s_scl),
                        "Saved!" if saving else "Save", self._small_bold,
                        style="success" if saving else "secondary",
                        hover=s_hov, pressed=save_hovered and mouse_down,
                        radius=8, glow=0.6 if saving else 0.0)

        # Money plaque: a rounded ink plate with the rolling, bumping balance.
        bump = min(1.0, self._money_bump)
        money_plaque = pygame.Rect(left, 12 - int(4 * bump), self._save_button.left - 8 - left, 30)
        ui_theme.panel_with_shadow(self.screen, money_plaque,
                                   top=(70, 54, 36), bottom=(46, 34, 22),
                                   border=(150, 100, 55), radius=9, border_w=2,
                                   shadow_lift=4, shadow_alpha=60)
        money_color = (245, 230, 120)
        if self._money_flash_timer > 0:
            money_color = (236, 110, 96)
        elif self._money_bump > 0.0:
            money_color = ui_theme.lerp_col((245, 230, 120), (255, 255, 214), bump)
        money_text = f"{int(round(self._money_display))}"
        cx = money_plaque.x + 9
        if self._coin_icon:
            icon_rect = self._coin_icon.get_rect(midleft=(cx, money_plaque.centery))
            self.screen.blit(self._coin_icon, icon_rect)
            cx = icon_rect.right + 8
        ui_theme.draw_text(self.screen, self._font_bold, money_text, money_color,
                           (cx, money_plaque.centery), anchor="midleft", shadow=(28, 18, 8), dy=2)

        if self._coin_small is None and self._coin_icon:
            self._coin_small = pygame.transform.smoothscale(self._coin_icon, (12, 12))
        coin_small = self._coin_small

        visible_seeds = [seed for seed in self.seeds if self._is_seed_unlocked(seed)]
        seed_cols = 4
        button_size = 44
        padding = 6
        seed_rows = max(1, (len(visible_seeds) + seed_cols - 1) // seed_cols)
        seed_group = pygame.Rect(panel_rect.left + 10, 48, UI_PANEL_W - 20,
                                 38 + seed_rows * button_size + max(0, seed_rows - 1) * padding + 16)
        ui_theme.panel_with_shadow(self.screen, seed_group, top=(58, 52, 60),
                                   bottom=(40, 36, 44), border=(120, 112, 124),
                                   radius=13, shadow_lift=4, shadow_alpha=38)
        ui_theme.section_header(self.screen, pygame.Rect(left, seed_group.top + 10, 96, 24),
                                "Seeds", self._head_font, style="primary")

        self._seed_buttons = []
        self._locked_seed_buttons = []
        grid_w = seed_cols * button_size + (seed_cols - 1) * padding
        grid_x = panel_rect.left + (UI_PANEL_W - grid_w) // 2
        grid_y = seed_group.top + 44

        for i, seed in enumerate(visible_seeds):
            col = i % seed_cols
            row = i // seed_cols
            rect = pygame.Rect(
                grid_x + col * (button_size + padding),
                grid_y + row * (button_size + padding),
                button_size,
                button_size,
            )

            affordable = self._can_afford_seed(seed)
            selected = self.selected_seed == seed
            draw_rect = self._draw_shop_tile(rect, f"seed:{type(seed).__name__}",
                                             selected=selected, affordable=affordable,
                                             t=t_now)

            icon = self._seed_icons.get(seed.icon_filename)
            if icon:
                if not affordable and not selected:
                    icon = icon.copy()
                    icon.set_alpha(130)
                icon_rect = icon.get_rect(center=(draw_rect.centerx, draw_rect.centery - 6))
                self.screen.blit(icon, icon_rect)
            else:
                fallback = self._small_bold.render(seed.name[0], True, (255, 248, 224))
                self.screen.blit(fallback, fallback.get_rect(center=(draw_rect.centerx, draw_rect.centery - 8)))

            req = self._seed_item_requirement(seed)
            if req:
                _, count = req
                self._draw_tile_cost(draw_rect, f"{count}x", coin=False, dim=not affordable)
            else:
                self._draw_tile_cost(draw_rect, str(seed.cost), coin=True, dim=not affordable)

            self._seed_buttons.append((seed, rect))

        y = seed_group.bottom + 10

        self._tool_buttons = []
        all_tool_ids = (TOOL_COMPOST, TOOL_SCARECROW, TOOL_LIGHTNING_ROD, TOOL_BELL)
        tool_ids = [tool_id for tool_id in all_tool_ids if self._is_tool_unlocked(tool_id)]
        ghost_tool_ids = [
            tool_id for tool_id in all_tool_ids
            if tool_id not in tool_ids and TOOL_TRIGGER_FLAGS.get(tool_id) in self._market.threat_flags
        ]
        display_tool_ids = tool_ids + ghost_tool_ids
        tool_names = {
            TOOL_COMPOST: "Compost",
            TOOL_SCARECROW: "Scarecrow",
            TOOL_LIGHTNING_ROD: "Rod",
            TOOL_BELL: "Bell",
        }
        tool_costs = {
            TOOL_SCARECROW: int(SCARECROW_COST),
            TOOL_LIGHTNING_ROD: int(LIGHTNING_ROD_COST),
        }
        tool_cols = 4
        tool_grid_w = tool_cols * button_size + (tool_cols - 1) * padding
        tool_grid_x = panel_rect.left + (UI_PANEL_W - tool_grid_w) // 2
        tool_rows = max(1, (len(display_tool_ids) + tool_cols - 1) // tool_cols)
        tool_group = pygame.Rect(panel_rect.left + 10, y, UI_PANEL_W - 20,
                                 38 + tool_rows * button_size + max(0, tool_rows - 1) * padding + 16)
        ui_theme.panel_with_shadow(self.screen, tool_group, top=(58, 52, 60),
                                   bottom=(40, 36, 44), border=(120, 112, 124),
                                   radius=13, shadow_lift=4, shadow_alpha=38)
        ui_theme.section_header(self.screen, pygame.Rect(left, tool_group.top + 10, 96, 24),
                                "Tools", self._head_font, style="primary")
        y = tool_group.top + 44

        for i, tool_id in enumerate(display_tool_ids):
            col = i % tool_cols
            row = i // tool_cols
            rect = pygame.Rect(
                tool_grid_x + col * (button_size + padding),
                y + row * (button_size + padding),
                button_size,
                button_size,
            )

            unlocked = tool_id in tool_ids
            affordable = unlocked
            if unlocked and tool_id == TOOL_COMPOST:
                affordable = self.inventory.get(COMPOST_ITEM_NAME, 0) >= 1
            elif unlocked and tool_id == TOOL_BELL:
                affordable = self._bell.ready and self.money >= int(BELL_RING_COST)
            elif unlocked and tool_id in tool_costs:
                affordable = self.money >= int(tool_costs[tool_id])

            selected = unlocked and self.selected_tool == tool_id
            draw_rect = self._draw_shop_tile(rect, f"tool:{tool_id}",
                                             selected=selected, affordable=affordable,
                                             t=t_now)

            icon = self._tool_icons.get(tool_id)
            label = tool_names.get(tool_id, tool_id)
            if icon:
                if (not affordable and not selected) or not unlocked:
                    icon = icon.copy()
                    icon.set_alpha(90 if not unlocked else 130)
                icon_rect = icon.get_rect(center=(draw_rect.centerx, draw_rect.centery - 6))
                self.screen.blit(icon, icon_rect)
            else:
                fallback = self._small_bold.render(label[0], True, (255, 248, 224))
                self.screen.blit(fallback, fallback.get_rect(center=(draw_rect.centerx, draw_rect.centery - 8)))

            if not unlocked:
                self._draw_tile_cost(draw_rect, "Market", coin=False, dim=True)
            elif tool_id == TOOL_COMPOST:
                have = self.inventory.get(COMPOST_ITEM_NAME, 0)
                self._draw_tile_cost(draw_rect, f"{have}x", coin=False, dim=not affordable)
            elif tool_id == TOOL_BELL:
                if self._bell.ready:
                    self._draw_tile_cost(draw_rect, str(int(BELL_RING_COST)), coin=True, dim=not affordable)
                else:
                    self._draw_tile_cost(draw_rect, f"{math.ceil(self._bell.cooldown_remaining)}s", coin=False, dim=True)
            else:
                cost = int(tool_costs.get(tool_id, 0))
                self._draw_tile_cost(draw_rect, str(cost), coin=True, dim=not affordable)

            if unlocked:
                self._tool_buttons.append((tool_id, rect))

        if not tool_ids:
            ui_theme.draw_text(self.screen, self._small_font, "Market unlocks tools", (224, 210, 178),
                               (left, y + 8), anchor="topleft", shadow=(28, 18, 8), dy=1)

        y = tool_group.bottom + 10

        action_group = pygame.Rect(panel_rect.left + 10, y, UI_PANEL_W - 20, 142)
        ui_theme.panel_with_shadow(self.screen, action_group, top=(58, 52, 60),
                                  bottom=(40, 36, 44), border=(120, 112, 124),
                                  radius=13, shadow_lift=4, shadow_alpha=38)
        ui_theme.section_header(self.screen, pygame.Rect(left, action_group.top + 10, 112, 24),
                               "Worker", self._head_font, style="secondary")
        y = action_group.top + 42

        btn_w = (UI_PANEL_W - 38) // 2
        self._inventory_button = pygame.Rect(left, y, btn_w, 30)
        self._market_button = pygame.Rect(left + btn_w + 6, y, btn_w, 30)
        inv_hovered = in_panel and self._inventory_button.collidepoint(mouse)
        inv_hov, inv_scl = self._ui_motion.tween("inventory:panel", inv_hovered, inv_hovered and mouse_down, dt)
        ui_theme.button(self.screen, ui_theme.scaled_rect(self._inventory_button, inv_scl),
                        "Inv [E]", self._small_bold,
                        style="primary" if self._show_inventory_overlay else "secondary",
                        hover=inv_hov, pressed=inv_hovered and mouse_down, radius=9)
        market_hovered = in_panel and self._market_button.collidepoint(mouse)
        market_hov, market_scl = self._ui_motion.tween("market:panel", market_hovered, market_hovered and mouse_down, dt)
        ui_theme.button(self.screen, ui_theme.scaled_rect(self._market_button, market_scl),
                        "Market [M]", self._small_bold,
                        style="primary" if self._show_market_overlay else "secondary",
                        hover=market_hov, pressed=market_hovered and mouse_down, radius=9,
                        glow=0.35 if (not self._show_market_overlay and self._market_offers()) else 0.0)
        y += 38

        # Hire button for the auto-harvester worker (harvest-only helper).
        self._worker_button = pygame.Rect(left, y, UI_PANEL_W - 32, 28)
        draw_worker_hire_button(self.screen, self._worker_button, self._small_bold,
                                self.auto_worker, self.money)
        y += 36

        self._inventory_rows = []
        self._market_rows = []
        self._sell_button = pygame.Rect(left, SCREEN_H - 54, UI_PANEL_W - 32, 32)

        self._draw_panel_help(panel_rect.left, UI_PANEL_W)

    def _wrap_help_text(self, text: str, max_width: int) -> list[str]:
        words = text.split()
        if not words:
            return []
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if self._small_font.size(trial)[0] <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _seed_help_lines(self, seed: PlantType) -> list[str]:
        lines = [f"{seed.name}  (${seed.cost} seed)"]
        desc = getattr(seed, "description", "")
        if desc:
            lines.extend(self._wrap_help_text(desc, UI_PANEL_W - 40))
        item = self.items.get(seed.product_name)
        price = int(item.sell_price) if item else 0
        lines.append(f"Harvest → {seed.product_name} (${price} each)")
        unlock = int(getattr(seed, "unlock_at", 0))
        if unlock > 0 and not self._is_seed_unlocked(seed):
            lines.append(f"Locked - unlock for ${unlock}")
        req = self._seed_item_requirement(seed)
        if req:
            item_name, count = req
            lines.append(f"Needs {count}x {item_name} in inventory")
        return lines

    def _update_panel_hover(self, pos: tuple[int, int]) -> None:
        self._panel_help_lines = []
        if pos[0] < self._field_rect.width:
            return

        seed = self._seed_at_pos(pos)
        if seed:
            self._panel_help_lines = self._seed_help_lines(seed)
            return

        locked = self._locked_seed_at_pos(pos)
        if locked:
            self._panel_help_lines = self._seed_help_lines(locked)
            return

        tool_id = self._tool_at_pos(pos)
        if tool_id:
            help_text = TOOL_HELP.get(tool_id, tool_id)
            self._panel_help_lines = self._wrap_help_text(help_text, UI_PANEL_W - 40)
            return

        if self._save_button.collidepoint(pos):
            self._panel_help_lines = self._wrap_help_text(PANEL_SAVE_HELP, UI_PANEL_W - 40)
            return

        if self._inventory_button.collidepoint(pos):
            self._panel_help_lines = ["Open Inventory and sell harvested items. Key: E"]
            return

        if self._market_button.collidepoint(pos):
            self._panel_help_lines = ["Open Market for seed and tool unlocks. Key: M"]

    def _show_sell_feedback(self, message: str) -> None:
        self._sell_feedback_msg = message
        self._sell_feedback_timer = 120

    def _draw_panel_help(self, panel_left: int, panel_w: int) -> None:
        pad = 12
        box_w = panel_w - pad * 2
        box_x = panel_left + pad

        if self._sell_feedback_timer > 0 and self._sell_feedback_msg:
            lines = self._wrap_help_text(self._sell_feedback_msg, box_w - 16)
            line_h = self._small_font.get_height() + 2
            box_h = 12 + len(lines) * line_h
            box_y = self._sell_button.top - box_h - 8
            box = pygame.Rect(box_x, box_y, box_w, box_h)
            ui_theme.soft_shadow(self.screen, box, radius=10, lift=4, pad=8, layers=3, alpha=46)
            self.screen.blit(ui_theme.rounded_panel(box_w, box_h, top=(120, 66, 60),
                             bottom=(86, 44, 40), border=(206, 120, 104), radius=10), box.topleft)
            ty = box_y + 6
            for line in lines:
                ui_theme.draw_text(self.screen, self._small_font, line, (255, 224, 214),
                                   (box_x + 9, ty), shadow=(40, 16, 14), dy=1)
                ty += line_h
            return

        if not self._panel_help_lines:
            return

        line_h = self._small_font.get_height() + 2
        box_h = 12 + len(self._panel_help_lines) * line_h
        box_y = self._sell_button.top - box_h - 8
        box = pygame.Rect(box_x, box_y, box_w, box_h)
        ui_theme.soft_shadow(self.screen, box, radius=10, lift=4, pad=8, layers=3, alpha=46)
        top, bot, bord, _txt = ui_theme.style_colors("ink")
        self.screen.blit(ui_theme.rounded_panel(box_w, box_h, top=top, bottom=bot,
                         border=bord, radius=10), box.topleft)
        ty = box_y + 6
        for i, line in enumerate(self._panel_help_lines):
            color = (245, 242, 230) if i == 0 else (198, 202, 214)
            ui_theme.draw_text(self.screen, self._small_font, line, color,
                               (box_x + 9, ty), shadow=(0, 0, 0), dy=1)
            ty += line_h

    def _draw_hover_tooltip(self):
        if not self._hover_slot or not self._hover_slot.planted:
            return
        lines = self._hover_slot.stats_lines()
        if not lines:
            return
        line_h = 18
        width = 168
        height = 12 + len(lines) * line_h
        mouse_x, mouse_y = pygame.mouse.get_pos()
        x = min(mouse_x + 14, self._field_rect.width - width - 8)
        y = min(mouse_y + 14, SCREEN_H - height - 8)
        rect = pygame.Rect(x, y, width, height)
        ui_theme.soft_shadow(self.screen, rect, radius=10, lift=4, pad=8, layers=3, alpha=54)
        top, bot, bord, _txt = ui_theme.style_colors("ink")
        self.screen.blit(ui_theme.rounded_panel(width, height, top=top, bottom=bot,
                         border=bord, radius=10), rect.topleft)
        text_y = y + 7
        for i, line in enumerate(lines):
            col = (245, 240, 228) if i == 0 else (210, 214, 224)
            ui_theme.draw_text(self.screen, self._small_font, line, col,
                               (x + 10, text_y), shadow=(0, 0, 0), dy=1)
            text_y += line_h

    def _draw_drag_seed(self):
        if not self.drag_seed:
            return
        mouse_x, mouse_y = pygame.mouse.get_pos()
        rect = pygame.Rect(mouse_x - 26, mouse_y - 26, 52, 52)
        ui_theme.button_plate(self.screen, rect, style="tile", hover=1.0, radius=12)
        icon = self._seed_icons.get(self.drag_seed.icon_filename)
        if icon:
            icon_rect = icon.get_rect(center=rect.center)
            self.screen.blit(icon, icon_rect)
        else:
            ui_theme.draw_text(self.screen, self._small_bold, self.drag_seed.name[0],
                               ui_theme.CREAM, rect.center, anchor="center",
                               shadow=ui_theme.SHADOW_INK, dy=1)

    def _draw_pause_window(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        win_w, win_h = 300, 200
        window = pygame.Rect((SCREEN_W - win_w) // 2, (SCREEN_H - win_h) // 2, win_w, win_h)
        ui_theme.panel_with_shadow(self.screen, window, top=(72, 84, 106),
                                   bottom=(48, 58, 78), border=(152, 170, 198),
                                   radius=16, shadow_lift=10, shadow_alpha=80)

        win_font = getattr(self, "_pause_title_font", None)
        if win_font is None:
            win_font = self._pause_title_font = pygame.font.SysFont("arial", 30, bold=True)
        ui_theme.draw_text(self.screen, win_font, "Paused", ui_theme.CREAM,
                           (window.centerx, window.centery - 55), anchor="center",
                           shadow=ui_theme.SHADOW_INK, dy=2)

        mouse = pygame.mouse.get_pos()
        pressed_now = pygame.mouse.get_pressed()[0]
        for key, rectb, label, style, glow in (
            ("pause:resume", self._pause_resume_btn, "Resume", "primary", 0.4),
            ("pause:quit", self._pause_quit_btn, "Main Menu", "secondary", 0.0),
        ):
            hovered = rectb.collidepoint(mouse)
            pressed = hovered and pressed_now
            hov, scale = self._ui_motion.tween(key, hovered, pressed, self._ui_dt)
            ui_theme.button(self.screen, ui_theme.scaled_rect(rectb, scale), label,
                            self._font_bold, style=style, hover=hov, pressed=pressed, glow=glow)
        return

    def _main_menu_button_clicked(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if (self._show_sell_confirm or self._show_purchase_confirm
                or self._show_inventory_overlay or self._show_market_overlay):
            return False
        return self._main_menu_btn.collidepoint(event.pos)

    def _draw_main_menu_button(self) -> None:
        btn = self._main_menu_btn
        mouse = pygame.mouse.get_pos()
        hovered = btn.collidepoint(mouse)
        pressed = hovered and pygame.mouse.get_pressed()[0]
        hov, scale = self._ui_motion.tween("mainmenu", hovered, pressed, self._ui_dt)
        ui_theme.button(self.screen, ui_theme.scaled_rect(btn, scale), "Main Menu",
                        self._small_bold, style="secondary", hover=hov, pressed=pressed)

    def _handle_farm_event(self, event: pygame.event.Event):
        # The year-end report card is the top-most modal: only it gets clicks.
        if self._show_report_card:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                btn = self._report_card_buttons.get("dismiss")
                if btn and btn.collidepoint(event.pos):
                    self._dismiss_report_card()
            return

        # If a purchase confirmation overlay is active, limit interactions to it.
        if self._show_purchase_confirm:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                confirm = self._purchase_confirm_buttons.get("confirm")
                cancel = self._purchase_confirm_buttons.get("cancel")
                if confirm and confirm.collidepoint(pos):
                    self._play_sfx(self._sfx_ui_click, key="purchase_confirm_click", debounce=0.08)
                    self._confirm_purchase()
                    return
                if cancel and cancel.collidepoint(pos):
                    self._play_sfx(self._sfx_ui_close, key="purchase_cancel", debounce=0.08)
                    self._show_purchase_confirm = False
                    self._pending_purchase = None
                    return
            return

        # If a sell confirmation overlay is active, limit interactions to it.
        if self._show_sell_confirm:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                # Confirm
                confirm = self._sell_confirm_buttons.get("confirm")
                cancel = self._sell_confirm_buttons.get("cancel")
                if confirm and confirm.collidepoint(pos):
                    self._play_sfx(self._sfx_ui_click, key="sell_confirm_click", debounce=0.08)
                    self._do_sell_inventory()
                    self._show_sell_confirm = False
                    self._pending_sell_total = None
                    return
                if cancel and cancel.collidepoint(pos):
                    self._play_sfx(self._sfx_ui_close, key="sell_cancel", debounce=0.08)
                    self._show_sell_confirm = False
                    self._pending_sell_total = None
                    return
            return

        if self._show_almanac:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self._almanac_close_button.collidepoint(pos) or not self._almanac_overlay_rect.collidepoint(pos):
                    self._close_almanac()
            return

        if self._show_inventory_overlay or self._show_market_overlay:
            self._handle_overlay_event(event)
            return

        if event.type == pygame.MOUSEMOTION:
            self._hover_slot = self._slot_at_pos(event.pos)
            self._update_panel_hover(event.pos)
            return

        if self.paused:
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            seed = self._seed_at_pos(event.pos)
            if seed:
                if self._can_afford_seed(seed):
                    self._play_sfx(self._sfx_seed_select, key="seed_select", debounce=0.05)
                    self.selected_seed = seed
                    self.selected_tool = None
                    self.drag_seed = seed
                else:
                    self._money_flash_timer = 20
                    self._play_sfx(self._sfx_ui_error, key="seed_error", debounce=0.12)
                return

            locked = self._locked_seed_at_pos(event.pos)
            if locked:
                self._play_sfx(self._sfx_ui_click, key="locked_seed_click", debounce=0.08)
                self._pending_purchase = locked
                self._show_purchase_confirm = True
                return

            tool_id = self._tool_at_pos(event.pos)
            if tool_id:
                if tool_id == TOOL_BELL:
                    # The bell is an instant-use tool: ring it now, never a slot mode.
                    self._ring_bell()
                    self.selected_tool = None
                    return
                self._play_sfx(self._sfx_ui_click, key="tool_select", debounce=0.05)
                if self.selected_tool == tool_id:
                    self.selected_tool = None
                else:
                    self.selected_tool = tool_id
                    self.selected_seed = None
                    self.drag_seed = None
                return

            if self._save_button.collidepoint(event.pos):
                self._play_sfx(self._sfx_ui_click, key="save_click", debounce=0.08)
                self.save_game()
                return

            if self._worker_button.collidepoint(event.pos):
                if self.auto_worker.hire(self):
                    self._play_sfx(self._sfx_worker_hire, key="worker_hire", debounce=0.2)
                else:
                    self._play_sfx(self._sfx_ui_error, key="worker_hire_error", debounce=0.15)
                return

            if self._inventory_button.collidepoint(event.pos):
                self._toggle_inventory_overlay()
                return

            if self._market_button.collidepoint(event.pos):
                self._toggle_market_overlay()
                return

            row = self._inventory_row_at_pos(event.pos)
            if row is not None:
                name, golden = row
                self._play_sfx(self._sfx_ui_click, key="inventory_row", debounce=0.04)
                self._sell_item(name, 1, golden=golden, source_pos=event.pos)
                return

            slot = self._slot_at_pos(event.pos)
            if slot and slot.dead:
                # Clearing a dead husk is salvage, not a win: keep the compost but
                # drop the success chime and any celebration. The loss already
                # landed when the plant died (see _spawn_death).
                slot.clear()
                if COMPOST_FROM_DEAD_PLANT > 0:
                    self.inventory[COMPOST_ITEM_NAME] = self.inventory.get(COMPOST_ITEM_NAME, 0) + int(COMPOST_FROM_DEAD_PLANT)
                    if JUICE_ENABLED:
                        cx, by = slot.rect.centerx, slot.rect.bottom - 6
                        for _ in range(4):
                            self._particles.append(Particle(
                                cx + self._rng.uniform(-8, 8), by,
                                vx=self._rng.uniform(-30, 30), vy=self._rng.uniform(-45, -15),
                                life=0.4, max_life=0.4, color=(120, 100, 80), size=2))
                return
            if slot and slot.harvestable:
                self._harvest(slot)
                return

            if slot and self.selected_tool:
                self._apply_tool_to_slot(slot, self.selected_tool)
                return

            if slot and slot.salted and (not slot.planted) and (not slot.dead) and self.selected_seed:
                self._show_sell_feedback("Soil is salted - can't plant here yet.")
                self._play_sfx(self._sfx_ui_error, key="salted_seed", debounce=0.15)
                return

            if slot and (not slot.planted) and (not slot.has_scarecrow) and (not slot.salted) and self.selected_seed and self._can_afford_seed(self.selected_seed):
                self._plant_slot(slot, self.selected_seed)
                return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            row = self._inventory_row_at_pos(event.pos)
            if row is not None:
                name, golden = row
                store = self._golden_inventory if golden else self.inventory
                self._sell_item(name, int(store.get(name, 0)), golden=golden, source_pos=event.pos)
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            slot = self._slot_at_pos(event.pos)
            if self.drag_seed and slot and (not slot.planted) and (not slot.has_scarecrow) and (not slot.salted):
                self._plant_slot(slot, self.drag_seed)
            self.drag_seed = None
            return

    def _seed_at_pos(self, pos: tuple[int, int]) -> PlantType | None:
        for seed, rect in self._seed_buttons:
            if rect.collidepoint(pos):
                return seed
        return None

    def _locked_seed_at_pos(self, pos: tuple[int, int]) -> PlantType | None:
        for seed, rect in self._locked_seed_buttons:
            if rect.collidepoint(pos):
                return seed
        return None

    def _tool_at_pos(self, pos: tuple[int, int]) -> str | None:
        for tool_id, rect in self._tool_buttons:
            if rect.collidepoint(pos):
                return tool_id
        return None

    def _inventory_row_at_pos(self, pos: tuple[int, int]):
        for name, golden, rect in self._inventory_rows:
            if rect.collidepoint(pos):
                return (name, golden)
        return None

    def _handle_overlay_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN:
            return
        if event.button not in (1, 3):
            return
        pos = event.pos
        if self._show_inventory_overlay:
            if not self._inventory_overlay_rect.collidepoint(pos):
                self._start_modal_close("inventory")
                self._show_inventory_overlay = False
                self._play_sfx(self._sfx_ui_close, key="inventory_close", debounce=0.12)
                return
            if event.button == 1 and self._inventory_close_button.collidepoint(pos):
                self._start_modal_close("inventory")
                self._show_inventory_overlay = False
                self._play_sfx(self._sfx_ui_close, key="inventory_close", debounce=0.12)
                return
            if event.button == 1 and self._sell_button.collidepoint(pos):
                self._play_sfx(self._sfx_ui_click, key="sell_button", debounce=0.08)
                self._sell_inventory()
                return
            row = self._inventory_row_at_pos(pos)
            if row is not None:
                name, golden = row
                self._play_sfx(self._sfx_ui_click, key="inventory_row", debounce=0.04)
                store = self._golden_inventory if golden else self.inventory
                qty = 1 if event.button == 1 else int(store.get(name, 0))
                self._sell_item(name, qty, golden=golden, source_pos=pos)
            return

        if self._show_market_overlay:
            if not self._market_overlay_rect.collidepoint(pos):
                self._start_modal_close("market")
                self._show_market_overlay = False
                self._play_sfx(self._sfx_ui_close, key="market_close", debounce=0.12)
                return
            if event.button == 1 and self._market_close_button.collidepoint(pos):
                self._start_modal_close("market")
                self._show_market_overlay = False
                self._play_sfx(self._sfx_ui_close, key="market_close", debounce=0.12)
                return
            if event.button != 1:
                return
            for offer, rect in self._market_rows:
                if rect.collidepoint(pos):
                    self._play_sfx(self._sfx_ui_click, key="market_row", debounce=0.06)
                    self._buy_market_offer(offer)
                    return

    def _inventory_entries(self) -> list[tuple[str, bool, int]]:
        entries: list[tuple[str, bool, int]] = []
        for name in sorted(self.inventory.keys(), key=str.lower):
            cnt = int(self.inventory.get(name, 0))
            if cnt > 0:
                entries.append((name, False, cnt))
        for name in sorted(self._golden_inventory.keys(), key=str.lower):
            cnt = int(self._golden_inventory.get(name, 0))
            if cnt > 0:
                entries.append((name, True, cnt))
        return entries

    def _draw_inventory_overlay(self) -> None:
        intro = self._modal_intro("inventory", dur=0.18)
        if intro <= 0.0:
            return
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((10, 10, 16, int(118 * intro)))
        self.screen.blit(dim, (0, 0))

        w, h = 560, 430
        rect = pygame.Rect((SCREEN_W - w) // 2, (SCREEN_H - h) // 2, w, h)
        rect = ui_theme.scaled_rect(rect, 0.94 + 0.06 * intro)
        self._inventory_overlay_rect = rect
        ui_theme.panel_with_shadow(self.screen, rect, top=(70, 62, 54), bottom=(48, 41, 34),
                                   border=(156, 124, 82), radius=16, shadow_lift=10,
                                   shadow_alpha=80)
        ui_theme.draw_text(self.screen, self._font_bold, "Inventory", ui_theme.CREAM,
                           (rect.left + 18, rect.top + 16), anchor="topleft",
                           shadow=ui_theme.SHADOW_INK, dy=1)
        self._draw_overlay_money_plaque(rect)
        self._inventory_close_button = self._draw_overlay_close(rect, "inventory")
        ui_theme.draw_text(self.screen, self._small_font, "L: sell 1   R: sell stack",
                           (236, 222, 188), (rect.right - 60, rect.top + 20),
                           anchor="topright", shadow=(28, 18, 8), dy=1)

        self._inventory_rows = []
        entries = self._inventory_entries()
        y = rect.top + 58
        left = rect.left + 20
        right = rect.right - 20
        line_h = self.ITEM_ICON_SIZE + 8
        max_rows = max(0, (rect.bottom - 112 - y) // line_h)
        if not entries:
            ui_theme.draw_text(self.screen, self._font, "Empty. Harvest crops to fill this bag.",
                               (224, 210, 178), (left, y), anchor="topleft",
                               shadow=(28, 18, 8), dy=1)
        else:
            for name, golden, count in entries[:max_rows]:
                row = pygame.Rect(left, y, right - left, line_h - 2)
                ui_theme.button_plate(self.screen, row, style="secondary", radius=8)
                icon = self._golden_item_icon(name) if golden else self._item_icon(name)
                self.screen.blit(icon, (row.left + 6, row.top + 3))
                label = f"Golden {name}" if golden else name
                name_color = GOLDEN_COLOR if golden else (238, 230, 212)
                ui_theme.draw_text(self.screen, self._small_font, label, name_color,
                                   (row.left + self.ITEM_ICON_SIZE + 14, row.centery),
                                   anchor="midleft", shadow=(28, 18, 8), dy=1)
                ui_theme.draw_text(self.screen, self._small_font, f"x{count}", (250, 236, 154),
                                   (row.right - 12, row.centery), anchor="midright",
                                   shadow=(28, 18, 8), dy=1)
                self._inventory_rows.append((name, golden, row))
                y += line_h
            remaining = len(entries) - max_rows
            if remaining > 0:
                ui_theme.draw_text(self.screen, self._small_font, f"{remaining} more stacks hidden",
                                   (216, 200, 168), (left, y + 4), anchor="topleft",
                                   shadow=(28, 18, 8), dy=1)

        total = self._compute_sale_total(commit=False)
        self._sell_button = pygame.Rect(rect.right - 174, rect.bottom - 56, 154, 38)
        hovered = self._sell_button.collidepoint(pygame.mouse.get_pos())
        hov, scale = self._ui_motion.tween("inventory:sellall", hovered, hovered and pygame.mouse.get_pressed()[0], self._ui_dt)
        ui_theme.button(self.screen, ui_theme.scaled_rect(self._sell_button, scale),
                        f"Sell All {int(total)}g", self._font_bold,
                        style="primary" if total > 0 else "locked",
                        hover=hov, pressed=hovered and pygame.mouse.get_pressed()[0], radius=9)

    def _draw_overlay_money_plaque(self, rect: pygame.Rect) -> None:
        plaque = pygame.Rect(rect.centerx - 62, rect.top + 12, 124, 30)
        ui_theme.button_plate(self.screen, plaque, style="primary", radius=10, shadow=False, glow=0.15)
        if self._coin_icon:
            icon = pygame.transform.smoothscale(self._coin_icon, (18, 18))
            self.screen.blit(icon, icon.get_rect(midleft=(plaque.left + 12, plaque.centery)))
        ui_theme.draw_text(self.screen, self._font_bold, f"{int(round(self._money_display))}g",
                           ui_theme.INK, (plaque.right - 12, plaque.centery),
                           anchor="midright", shadow=(255, 236, 170), dx=0, dy=1)

    def _draw_overlay_close(self, rect: pygame.Rect, key: str) -> pygame.Rect:
        btn = pygame.Rect(rect.right - 44, rect.top + 10, 30, 30)
        mouse = pygame.mouse.get_pos()
        hovered = btn.collidepoint(mouse)
        pressed = hovered and pygame.mouse.get_pressed()[0]
        hov, scale = self._ui_motion.tween(f"{key}:close", hovered, pressed, self._ui_dt)
        ui_theme.button(self.screen, ui_theme.scaled_rect(btn, scale), "X", self._small_bold,
                        style="danger", hover=hov, pressed=pressed, radius=10)
        return btn

    def _everbloom_market_ready(self) -> bool:
        state = getattr(self, "_endgame", None)
        if state is None:
            return False
        return bool(state.everbloom.is_unlocked(state.legacy))

    def _market_offers(self) -> list[MarketOffer]:
        return self._market.offers(
            self.seeds,
            set(self._unlocked_seeds),
            set(self._unlocked_tools),
            int(self._total_earned),
            self._everbloom_market_ready(),
        )

    def _draw_market_overlay(self) -> None:
        intro = self._modal_intro("market", dur=0.18)
        if intro <= 0.0:
            return
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((10, 10, 16, int(118 * intro)))
        self.screen.blit(dim, (0, 0))

        w, h = 600, 430
        rect = pygame.Rect((SCREEN_W - w) // 2, (SCREEN_H - h) // 2, w, h)
        rect = ui_theme.scaled_rect(rect, 0.94 + 0.06 * intro)
        self._market_overlay_rect = rect
        ui_theme.panel_with_shadow(self.screen, rect, top=(60, 64, 58), bottom=(40, 44, 38),
                                   border=(128, 158, 102), radius=16, shadow_lift=10,
                                   shadow_alpha=80)
        ui_theme.draw_text(self.screen, self._font_bold, "Market", ui_theme.CREAM,
                           (rect.left + 18, rect.top + 16), anchor="topleft",
                           shadow=ui_theme.SHADOW_INK, dy=1)
        self._draw_overlay_money_plaque(rect)
        self._market_close_button = self._draw_overlay_close(rect, "market")

        y = rect.top + 56
        left = rect.left + 20
        right = rect.right - 20
        self._market_rows = []
        offers = self._market_offers()
        if self._market_featured_item or self._market_discounted_item:
            line = []
            if self._market_featured_item:
                line.append(f"Hot sell: {self._market_featured_item} x{MARKET_FEATURED_MULT:g}")
            if self._market_discounted_item:
                line.append(f"Cold sell: {self._market_discounted_item} x{MARKET_DISCOUNT_MULT:g}")
            ui_theme.draw_text(self.screen, self._small_font, "   ".join(line),
                               (235, 220, 160), (left, y), anchor="topleft",
                               shadow=(18, 24, 14), dy=1)
            y += 28

        if not offers:
            ui_theme.draw_text(self.screen, self._font, "No new licenses today.",
                               (224, 220, 190), (left, y), anchor="topleft",
                               shadow=(18, 24, 14), dy=1)
            ui_theme.draw_text(self.screen, self._small_font, "Threats and rare stock add offers over time.",
                               (190, 204, 176), (left, y + 30), anchor="topleft",
                               shadow=(18, 24, 14), dy=1)
            return

        row_h = 54
        for offer in offers[:6]:
            row = pygame.Rect(left, y, right - left, row_h)
            afford = self.money >= int(offer.cost)
            hovered = row.collidepoint(pygame.mouse.get_pos())
            pressed = hovered and pygame.mouse.get_pressed()[0]
            hov, scale = self._ui_motion.tween(f"market:offer:{offer.kind}:{offer.item_id}", hovered, pressed, self._ui_dt)
            draw_row = ui_theme.scaled_rect(row, scale)
            ui_theme.button_plate(self.screen, draw_row, style="secondary" if afford else "locked",
                                  hover=hov, pressed=pressed, radius=12, glow=0.14 if afford else 0.0)
            icon_rect = pygame.Rect(draw_row.left + 12, draw_row.top + 10, 32, 32)
            icon = None
            if offer.kind == "tool":
                icon = self._tool_icons.get(offer.item_id)
            else:
                for seed in self.seeds:
                    if type(seed).__name__ == offer.item_id:
                        icon = self._seed_icons.get(seed.icon_filename)
                        break
            if icon is not None:
                if not afford:
                    icon = icon.copy()
                    icon.set_alpha(120)
                self.screen.blit(icon, icon.get_rect(center=icon_rect.center))
            else:
                pygame.draw.circle(self.screen, (250, 224, 150) if afford else (130, 126, 134), icon_rect.center, 13)
                ui_theme.draw_text(self.screen, self._small_bold, offer.label[:1], ui_theme.INK,
                                   icon_rect.center, anchor="center", shadow=None)
            title = f"{offer.label} {'tool' if offer.kind == 'tool' else 'seed'}"
            ui_theme.draw_text(self.screen, self._small_bold, title, ui_theme.CREAM,
                               (draw_row.left + 52, draw_row.top + 8), anchor="topleft",
                               shadow=(18, 24, 14), dy=1)
            ui_theme.draw_text(self.screen, self._small_font, offer.reason,
                               (190, 214, 176), (draw_row.left + 52, draw_row.top + 30),
                               anchor="topleft", shadow=(18, 24, 14), dy=1)
            price_color = (250, 224, 150) if afford else (236, 150, 128)
            pill = pygame.Rect(draw_row.right - 86, draw_row.centery - 15, 72, 30)
            ui_theme.button_plate(self.screen, pill, style="primary" if afford else "locked",
                                  radius=10, shadow=False)
            ui_theme.draw_text(self.screen, self._font_bold, f"{int(offer.cost)}g",
                               price_color, pill.center, anchor="center", shadow=(18, 24, 14), dy=1)
            self._market_rows.append((offer, row))
            y += row_h + 8

    def _buy_market_offer(self, offer: MarketOffer) -> bool:
        cost = int(offer.cost)
        if self.money < cost:
            self._money_flash_timer = 20
            self._play_sfx(self._sfx_ui_error, key="market_buy_error", debounce=0.15)
            return False
        self.money -= cost
        if offer.kind == "tool":
            self._unlocked_tools.add(offer.item_id)
            self._show_sell_feedback(f"Unlocked {offer.label}.")
        elif offer.kind == "seed":
            self._unlocked_seeds.add(offer.item_id)
            self._show_sell_feedback(f"Unlocked {offer.label}.")
        else:
            return False
        self.save_game(flash=False)
        self._play_sfx(self._sfx_purchase_unlock, key="market_buy", debounce=0.15)
        return True

    def _load_seed_icons(self):
        for seed in self.seeds:
            path = os.path.join(PROPS_DIR, seed.icon_filename)
            if not os.path.exists(path):
                continue
            raw = pygame.image.load(path).convert_alpha()
            self._seed_icons[seed.icon_filename] = pygame.transform.smoothscale(raw, (32, 32))

    def _load_tool_icons(self):
        for tool_id, filename in TOOL_ICON_FILENAMES.items():
            path = os.path.join(PROPS_DIR, filename)
            if not os.path.exists(path):
                continue
            raw = pygame.image.load(path).convert_alpha()
            self._tool_icons[tool_id] = pygame.transform.smoothscale(raw, (32, 32))

    def _load_ui_panel(self):
        path = os.path.join(PROPS_DIR, "ui_panel.png")
        if not os.path.exists(path):
            return
        raw = pygame.image.load(path).convert_alpha()
        self._ui_panel_image = pygame.transform.smoothscale(raw, (UI_PANEL_W, SCREEN_H))

    def _load_coin_icon(self):
        path = os.path.join(PROPS_DIR, "coin.png")
        if not os.path.exists(path):
            return
        raw = pygame.image.load(path).convert_alpha()
        self._coin_icon = pygame.transform.smoothscale(raw, (20, 20))
        self._coin_particle_img = pygame.transform.smoothscale(raw, (14, 14))
        # Optional golden sparkle particle for star/quality harvests.
        spath = os.path.join(PROPS_DIR, "golden_sparkle.png")
        if os.path.exists(spath):
            try:
                self._golden_sparkle_img = pygame.transform.smoothscale(
                    pygame.image.load(spath).convert_alpha(), (12, 12))
            except Exception:
                self._golden_sparkle_img = None

    def _load_lock_icon(self):
        path = os.path.join(PROPS_DIR, "lock_icon.png")
        if not os.path.exists(path):
            return
        raw = pygame.image.load(path).convert_alpha()
        self._lock_icon = pygame.transform.smoothscale(raw, (26, 26))

    def _load_dead_plant(self):
        path = os.path.join(PROPS_DIR, "dead_plant.png")
        if not os.path.exists(path):
            return
        raw = pygame.image.load(path).convert_alpha()
        self._dead_plant_image = pygame.transform.smoothscale(raw, (PLANT_SPRITE_W, PLANT_SPRITE_H))

    # ── item icons (inventory) ───────────────────────────────────────────
    ITEM_ICON_SIZE = 18

    def _build_item_icons(self):
        size = self.ITEM_ICON_SIZE
        # Crop products reuse their seed icon.
        for seed in self.seeds:
            icon = self._seed_icons.get(seed.icon_filename)
            if icon and seed.product_name not in self._item_icons:
                self._item_icons[seed.product_name] = pygame.transform.smoothscale(icon, (size, size))
        # Any other item may supply a dedicated props/<name>_icon.png.
        for name in self.items:
            if name in self._item_icons:
                continue
            filename = name.lower().replace(" ", "_") + "_icon.png"
            path = os.path.join(PROPS_DIR, filename)
            if os.path.exists(path):
                raw = pygame.image.load(path).convert_alpha()
                self._item_icons[name] = pygame.transform.smoothscale(raw, (size, size))

    def _item_icon(self, name: str) -> pygame.Surface:
        cached = self._item_icons.get(name)
        if cached is not None:
            return cached
        # Generate a simple lettered placeholder for items without art.
        size = self.ITEM_ICON_SIZE
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        h = abs(hash(name))
        color = (70 + h % 130, 70 + (h // 7) % 130, 70 + (h // 13) % 130)
        pygame.draw.rect(surf, color, surf.get_rect(), border_radius=4)
        pygame.draw.rect(surf, (225, 225, 230), surf.get_rect(), 1, border_radius=4)
        letter = self._small_font.render(name[0].upper(), True, (245, 245, 245))
        surf.blit(letter, letter.get_rect(center=surf.get_rect().center))
        self._item_icons[name] = surf
        return surf

    def _golden_item_icon(self, name: str) -> pygame.Surface:
        cached = self._golden_item_icons.get(name)
        if cached is not None:
            return cached
        base = self._item_icon(name).copy()
        tint = pygame.Surface(base.get_size())
        tint.fill(GOLDEN_COLOR)
        base.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        pygame.draw.rect(base, GOLDEN_COLOR, base.get_rect(), 2, border_radius=4)
        self._golden_item_icons[name] = base
        return base

    # ── save / load ──────────────────────────────────────────────────────
    def _seed_lookup(self) -> dict:
        return {type(seed).__name__: seed for seed in self.seeds}

    def save_game(self, flash: bool = True):
        data = {
            "version": 2,
            "money": int(self.money),
            "total_earned": int(self._total_earned),
            "unlocked_seeds": sorted(self._unlocked_seeds),
            "unlocked_tools": sorted(self._unlocked_tools),
            "market_state": self._market.to_dict(),
            "inventory": {str(k): int(v) for k, v in self.inventory.items()},
            "golden_inventory": {str(k): int(v) for k, v in self._golden_inventory.items()},
            "world_seconds": float(self._world_seconds),
            "slots": [slot.to_dict() for slot in self.slots],
            "almanac": self._almanac.to_dict(),
            "worker_prime": {
                "worker": self.auto_worker.to_dict(),
                "prime_slots": prime_save_slots(self.slots),
            },
        }
        try:
            tmp_path = str(SAVE_PATH) + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, SAVE_PATH)  # atomic: never leaves a truncated save
            if flash:
                self._save_flash_timer = 90
                self._play_sfx(self._sfx_save_confirm, key="save_confirm", debounce=0.2)
        except OSError:
            pass

    def load_game(self):
        if not os.path.exists(SAVE_PATH):
            # No progress yet: create a fresh save from the starting state.
            self.save_game()
            return
        try:
            with open(SAVE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            return

        self.money = int(data.get("money", self.money))
        self._money_display = float(self.money)  # snap the ticker on load
        self._total_earned = int(data.get("total_earned", self._total_earned))

        # Seeds available with no purchase are always unlocked. Then layer on any
        # explicitly purchased seeds, and (for saves predating the purchase model)
        # migrate by unlocking anything the old total-earned threshold would have.
        unlocked = {
            type(s).__name__ for s in self.seeds if int(getattr(s, "unlock_at", 0)) <= 0
        }
        if "unlocked_seeds" in data:
            unlocked |= {str(n) for n in (data.get("unlocked_seeds") or [])}
        else:
            unlocked |= {
                type(s).__name__
                for s in self.seeds
                if self._total_earned >= int(getattr(s, "unlock_at", 0))
            }
        self._unlocked_seeds = unlocked
        self._unlocked_tools = {str(n) for n in (data.get("unlocked_tools") or [])}
        self._market.from_dict(data.get("market_state") or {})

        inv = data.get("inventory", {}) or {}
        self.inventory = {str(k): int(v) for k, v in inv.items() if int(v) > 0}
        ginv = data.get("golden_inventory", {}) or {}
        self._golden_inventory = {str(k): int(v) for k, v in ginv.items() if int(v) > 0}
        self._world_seconds = float(data.get("world_seconds", 0.0))

        # Almanac (save v2). Older saves have no "almanac" → init fresh in
        # _sync_time_after_load using the season derived from world_seconds.
        alm = data.get("almanac")
        if alm:
            self._almanac.from_dict(alm)
            self._almanac_loaded = True
        else:
            self._almanac_loaded = False

        lookup = self._seed_lookup()
        for slot, sdata in zip(self.slots, data.get("slots", []) or []):
            slot.from_dict(sdata, lookup)

        wp = data.get("worker_prime") or {}
        self.auto_worker.from_dict(wp.get("worker", {}) or {})
        prime_load_slots(self.slots, wp.get("prime_slots", []) or [])

        self._sync_time_after_load()

    def _sync_time_after_load(self):
        # Re-derive day/week/season from the restored world clock and roll a
        # fresh market/weather for the current day.
        day_index = int(self._world_seconds // float(IN_GAME_DAY_SECONDS))
        week_index = int(day_index // int(IN_GAME_DAYS_PER_WEEK))
        self._day_index = day_index
        self._last_day_index = day_index
        self._week_index = week_index
        self._last_week_index = week_index
        self._season_index = week_index % len(SEASON_NAMES) if SEASON_NAMES else 0
        year_index = week_index // len(SEASON_NAMES) if SEASON_NAMES else 0
        if getattr(self, "_almanac_loaded", False):
            self._almanac.set_season(self._season_index)
            self._almanac.year_index = year_index
        else:
            self._almanac.init_fresh(self._season_index, year_index)
        # Re-apply boss difficulty from the loaded/initialised almanac.
        for boss in self._bosses:
            setter = getattr(boss, "set_difficulty", None)
            if callable(setter):
                setter(int(self._almanac.difficulty))
        self._apply_threat_difficulty(int(self._almanac.difficulty))
        self._on_new_day(day_index, grant_stipend=False)

    def _load_plant_phases(self):
        for seed in self.seeds:
            w = seed.sprite_w if seed.sprite_w is not None else PLANT_SPRITE_W
            h = seed.sprite_h if seed.sprite_h is not None else PLANT_SPRITE_H
            for filename in seed.phase_filenames:
                if filename in self._plant_phase_icons:
                    continue
                path = os.path.join(PROPS_DIR, filename)
                if not os.path.exists(path):
                    continue
                raw = pygame.image.load(path).convert_alpha()
                self._plant_phase_icons[filename] = pygame.transform.smoothscale(raw, (w, h))

    def _phase_image_for_slot(self, slot: PlantSlot) -> pygame.Surface | None:
        if not slot.seed:
            return None
        stage = min(slot.growth_stage, slot.seed.growth_stages)
        index = min(stage, len(slot.seed.phase_filenames)) - 1
        if index < 0:
            return None
        filename = slot.seed.phase_filenames[index]
        return self._plant_phase_icons.get(filename)

    def _slot_at_pos(self, pos: tuple[int, int]) -> PlantSlot | None:
        if pos[0] > self._field_rect.width:
            return None
        for slot in self.slots:
            if slot.rect.collidepoint(pos):
                return slot
        return None

    def _seed_item_requirement(self, seed: PlantType) -> tuple[str, int] | None:
        item_name = getattr(seed, "seed_item_name", None)
        if not item_name:
            return None
        return (str(item_name), 1)

    def _draw_modal_button(self, surf, local_rect, margin, label, key, style,
                           mouse_local, pressed_now, font=None, glow=0.0):
        """Draw a themed dialog button with eased hover/press on the card surface.

        local_rect is the logical hit rect in panel-local coords; the screen rect
        the event handler tests is derived by the caller and never moves. Only the
        drawn copy scales on hover/press, exactly like the shop tiles and titans.
        """
        hovered = local_rect.collidepoint(mouse_local)
        pressed = hovered and pressed_now
        hov, scale = self._ui_motion.tween(key, hovered, pressed, self._ui_dt)
        draw_rect = ui_theme.scaled_rect(local_rect.move(margin, margin), scale)
        ui_theme.button(surf, draw_rect, label, font or self._small_bold,
                        style=style, hover=hov, pressed=pressed, glow=glow)

    def _modal_intro(self, name: str, dur: float = 0.16) -> float:
        """Eased visibility factor for a modal, including the close-out ease."""
        now = pygame.time.get_ticks() / 1000.0
        closing = self._modal_close_at.get(name)
        if closing is not None:
            t = max(0.0, min(1.0, (now - closing) / dur))
            if t >= 1.0:
                self._modal_close_at.pop(name, None)
                self._modal_open_at.pop(name, None)
                return 0.0
            return 1.0 - effects.ease_in_quad(t)
        t0 = self._modal_open_at.get(name)
        if t0 is None:
            t0 = self._modal_open_at[name] = now
        t = max(0.0, min(1.0, (now - t0) / dur))
        return max(0.001, 1.0 - (1.0 - t) * (1.0 - t))

    def _draw_sell_confirm(self):
        intro = self._modal_intro("sell")
        w, h = 430, 150
        rect = pygame.Rect((SCREEN_W - w) // 2, (SCREEN_H - h) // 2, w, h)

        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((10, 10, 16, int(118 * intro)))
        self.screen.blit(dim, (0, 0))

        mx, my = pygame.mouse.get_pos()
        pressed_now = pygame.mouse.get_pressed()[0]
        mouse_local = (mx - rect.left, my - rect.top)

        btn_w, btn_h = 142, 40
        spacing = 16
        bx = w - btn_w - 18
        by = h - btn_h - 18
        confirm = pygame.Rect(bx, by, btn_w, btn_h)
        cancel = pygame.Rect(bx - (btn_w + spacing), by, btn_w, btn_h)
        # Logical hit rects (screen coords) stay fixed; only drawn copies animate.
        self._sell_confirm_buttons["confirm"] = confirm.move(rect.left, rect.top)
        self._sell_confirm_buttons["cancel"] = cancel.move(rect.left, rect.top)

        m = 16
        card = pygame.Surface((w + 2 * m, h + 2 * m), pygame.SRCALPHA)
        panel = pygame.Rect(m, m, w, h)
        ui_theme.soft_shadow(card, panel, radius=16, lift=8, pad=12, layers=4, alpha=72)
        card.blit(ui_theme.rounded_panel(w, h, top=(70, 62, 54), bottom=(48, 41, 34),
                                         border=(156, 124, 82), radius=16), (m, m))

        ui_theme.draw_text(card, self._font_bold, "Sell everything?", ui_theme.CREAM,
                           (m + 18, m + 14), anchor="topleft", shadow=ui_theme.SHADOW_INK, dy=1)
        total_text = f"Total: {int(self._pending_sell_total or 0)}g"
        ui_theme.draw_text(card, self._font, total_text, (250, 224, 150),
                           (m + 18, m + 48), anchor="topleft", shadow=ui_theme.SHADOW_INK, dy=1)

        self._draw_modal_button(card, confirm, m, "Sell All", "sellc:confirm",
                                "primary", mouse_local, pressed_now, glow=0.5)
        self._draw_modal_button(card, cancel, m, "Cancel", "sellc:cancel",
                                "secondary", mouse_local, pressed_now)

        if intro < 1.0:
            card.fill((255, 255, 255, int(255 * intro)), special_flags=pygame.BLEND_RGBA_MULT)
        self.screen.blit(card, (rect.left - m, rect.top - m))

    def _grade_color(self, grade: str) -> tuple:
        return {
            "S": (255, 214, 92),
            "A": (140, 230, 140),
            "B": (140, 200, 240),
            "C": (220, 220, 160),
            "D": (220, 150, 130),
        }.get(str(grade), (220, 220, 220))

    def _draw_report_card(self) -> None:
        cap = self._pending_report
        if cap is None:
            self._show_report_card = False
            return

        title_font = getattr(self, "_report_title_font", None)
        if title_font is None:
            title_font = self._report_title_font = pygame.font.SysFont("arial", 30, bold=True)
        grade_font = getattr(self, "_report_grade_font", None)
        if grade_font is None:
            grade_font = self._report_grade_font = pygame.font.SysFont("arial", 44, bold=True)

        intro = self._modal_intro("report", dur=0.2)
        pop = 0.93 + 0.07 * intro

        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((10, 12, 20, int(184 * intro)))
        self.screen.blit(dim, (0, 0))

        w, h = 460, 410
        rect = pygame.Rect((SCREEN_W - w) // 2, (SCREEN_H - h) // 2, w, h)
        mx, my = pygame.mouse.get_pos()
        pressed_now = pygame.mouse.get_pressed()[0]
        mouse_local = (mx - rect.left, my - rect.top)

        m = 18
        card = pygame.Surface((w + 2 * m, h + 2 * m), pygame.SRCALPHA)
        panel = pygame.Rect(m, m, w, h)
        ui_theme.soft_shadow(card, panel, radius=18, lift=10, pad=14, layers=4, alpha=80)
        card.blit(ui_theme.rounded_panel(w, h, top=(60, 58, 70), bottom=(40, 38, 50),
                                         border=(132, 140, 170), radius=18), (m, m))

        ui_theme.draw_text(card, title_font, f"Year {int(getattr(cap, 'year', 0)) + 1} Report",
                           (248, 242, 222), (m + w // 2, m + 14), anchor="midtop",
                           shadow=ui_theme.SHADOW_INK, dy=2)

        grade = str(getattr(cap, "grade", "C"))
        gcolor = self._grade_color(grade)
        badge = pygame.Rect(0, 0, 86, 72)
        badge.center = (m + w // 2, m + 92)
        ui_theme.soft_glow(card, badge, radius=12, color=gcolor, alpha=120, spread=18)
        pygame.draw.rect(card, (18, 20, 28), badge, border_radius=12)
        pygame.draw.rect(card, gcolor, badge, 3, border_radius=12)
        ui_theme.draw_text(card, grade_font, grade, gcolor, badge.center,
                           anchor="center", shadow=(0, 0, 0), dy=2)

        rows = [
            ("Goals met", f"{int(getattr(cap, 'goals_done', 0))}/{int(getattr(cap, 'goals_total', 0))}"),
            ("Crops harvested", f"{int(getattr(cap, 'crops', 0))}"),
            ("Gold earned", f"{int(getattr(cap, 'gold', 0))}"),
            ("Titans defeated", f"{int(getattr(cap, 'titans', 0))}"),
            ("Capstone bonus", f"+{int(getattr(cap, 'money', 0))}g"),
        ]
        eg = getattr(self, "_endgame", None)
        if eg is not None:
            rows.append(("Farm legacy", f"{int(eg.legacy.percent())}%"))
        y = m + 146
        for label, value in rows:
            ui_theme.draw_text(card, self._font, label, (212, 216, 230),
                               (m + 32, y), anchor="topleft", shadow=ui_theme.SHADOW_INK, dy=1)
            ui_theme.draw_text(card, self._font, value, (250, 232, 158),
                               (m + w - 32, y), anchor="topright", shadow=ui_theme.SHADOW_INK, dy=1)
            y += 30

        # Next-Year preview: a short between-years heads-up of what is changing.
        preview = getattr(eg, "last_preview", None) if eg is not None else None
        if preview is not None:
            y += 4
            ui_theme.draw_text(card, self._small_bold, preview.title, (196, 224, 255),
                               (m + 32, y), anchor="topleft", shadow=ui_theme.SHADOW_INK, dy=1)
            y += 22
            for line in preview.lines[:2]:
                ui_theme.draw_text(card, self._small_font, line, (208, 214, 226),
                                   (m + 36, y), anchor="topleft", shadow=ui_theme.SHADOW_INK, dy=1)
                y += 18

        if bool(getattr(cap, "perfect", False)):
            ui_theme.draw_text(card, self._small_bold, "Perfect Year, every goal completed!",
                               GOLDEN_COLOR, (m + w // 2, y + 4), anchor="midtop",
                               shadow=ui_theme.SHADOW_INK, dy=1)

        btn = pygame.Rect(w // 2 - 84, h - 56, 168, 40)
        self._report_card_buttons["dismiss"] = btn.move(rect.left, rect.top)
        self._draw_modal_button(card, btn, m, "Onward!", "report:dismiss",
                                "primary", mouse_local, pressed_now,
                                font=self._font_bold, glow=0.6)

        if intro < 1.0:
            card.fill((255, 255, 255, int(255 * intro)), special_flags=pygame.BLEND_RGBA_MULT)
        if pop < 1.0:
            cw, ch = card.get_width(), card.get_height()
            scaled = pygame.transform.smoothscale(card, (max(1, int(cw * pop)), max(1, int(ch * pop))))
            self.screen.blit(scaled, scaled.get_rect(center=rect.center))
        else:
            self.screen.blit(card, card.get_rect(center=rect.center))

    def _confirm_purchase(self):
        seed = self._pending_purchase
        if seed is None:
            self._show_purchase_confirm = False
            return
        price = int(getattr(seed, "unlock_at", 0))
        if self.money >= price:
            self.money -= price
            self._unlocked_seeds.add(type(seed).__name__)
            self.save_game(flash=False)
            self._show_purchase_confirm = False
            self._pending_purchase = None
            self._play_sfx(self._sfx_purchase_unlock, key="seed_unlock", debounce=0.15)
        else:
            # Not enough money: flash the balance and keep the dialog open.
            self._money_flash_timer = 20
            self._play_sfx(self._sfx_ui_error, key="seed_unlock_error", debounce=0.15)

    def _draw_purchase_confirm(self):
        seed = self._pending_purchase
        if seed is None:
            return
        intro = self._modal_intro("purchase")
        w, h = 430, 168
        rect = pygame.Rect((SCREEN_W - w) // 2, (SCREEN_H - h) // 2, w, h)

        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((10, 10, 16, int(118 * intro)))
        self.screen.blit(dim, (0, 0))

        mx, my = pygame.mouse.get_pos()
        pressed_now = pygame.mouse.get_pressed()[0]
        mouse_local = (mx - rect.left, my - rect.top)
        cx = w // 2

        btn_w, btn_h = 142, 40
        spacing = 16
        by = h - btn_h - 18
        group_w = btn_w * 2 + spacing
        cancel = pygame.Rect(cx - group_w // 2, by, btn_w, btn_h)
        confirm = pygame.Rect(cancel.right + spacing, by, btn_w, btn_h)
        self._purchase_confirm_buttons["confirm"] = confirm.move(rect.left, rect.top)
        self._purchase_confirm_buttons["cancel"] = cancel.move(rect.left, rect.top)

        m = 16
        card = pygame.Surface((w + 2 * m, h + 2 * m), pygame.SRCALPHA)
        panel = pygame.Rect(m, m, w, h)
        ui_theme.soft_shadow(card, panel, radius=16, lift=8, pad=12, layers=4, alpha=72)
        card.blit(ui_theme.rounded_panel(w, h, top=(70, 62, 54), bottom=(48, 41, 34),
                                         border=(156, 124, 82), radius=16), (m, m))

        ui_theme.draw_text(card, self._font_bold, f"Buy {seed.name}?", ui_theme.CREAM,
                           (m + cx, m + 22), anchor="midtop", shadow=ui_theme.SHADOW_INK, dy=1)
        price = int(getattr(seed, "unlock_at", 0))
        afford = self.money >= price
        price_color = (250, 224, 150) if afford else (236, 150, 128)
        ui_theme.draw_text(card, self._font, f"Unlock cost: {price}g", price_color,
                           (m + cx, m + 58), anchor="midtop", shadow=ui_theme.SHADOW_INK, dy=1)
        if not afford:
            ui_theme.draw_text(card, self._small_bold, "Not enough money", (236, 150, 128),
                               (m + cx, m + 88), anchor="midtop", shadow=ui_theme.SHADOW_INK, dy=1)

        self._draw_modal_button(card, confirm, m, "Buy", "buy:confirm",
                                "primary" if afford else "locked", mouse_local,
                                pressed_now, glow=0.5 if afford else 0.0)
        self._draw_modal_button(card, cancel, m, "Cancel", "buy:cancel",
                                "secondary", mouse_local, pressed_now)

        if intro < 1.0:
            card.fill((255, 255, 255, int(255 * intro)), special_flags=pygame.BLEND_RGBA_MULT)
        self.screen.blit(card, (rect.left - m, rect.top - m))

    def _is_seed_unlocked(self, seed: PlantType) -> bool:
        if int(getattr(seed, "unlock_at", 0)) <= 0:
            return True
        return type(seed).__name__ in self._unlocked_seeds

    def _draw_lock_icon(self, center: tuple[int, int]) -> None:
        # Prefer the editable padlock image; fall back to a drawn one.
        if self._lock_icon is not None:
            self.screen.blit(self._lock_icon, self._lock_icon.get_rect(center=center))
            return

        surf = pygame.Surface((26, 30), pygame.SRCALPHA)
        gold = (244, 212, 120)
        dark = (88, 64, 28)

        pygame.draw.arc(surf, dark, (6, 1, 14, 18), 0.0, math.pi, 6)
        pygame.draw.arc(surf, gold, (7, 2, 12, 16), 0.0, math.pi, 4)
        for lx in (8, 18):
            pygame.draw.line(surf, gold, (lx, 9), (lx, 14), 4)

        body = pygame.Rect(3, 12, 20, 16)
        pygame.draw.rect(surf, dark, body, border_radius=5)
        inner = body.inflate(-4, -4)
        pygame.draw.rect(surf, gold, inner, border_radius=4)

        pygame.draw.circle(surf, dark, (13, 19), 3)
        pygame.draw.polygon(surf, dark, [(11, 26), (15, 26), (14, 20), (12, 20)])

        self.screen.blit(surf, surf.get_rect(center=center))

    def _can_afford_seed(self, seed: PlantType) -> bool:
        if self.money < seed.cost:
            return False
        req = self._seed_item_requirement(seed)
        if not req:
            return True
        item_name, count = req
        return self.inventory.get(item_name, 0) >= count

    def _pay_for_seed(self, seed: PlantType) -> bool:
        if not self._can_afford_seed(seed):
            return False

        self.money -= seed.cost
        req = self._seed_item_requirement(seed)
        if req:
            item_name, count = req
            remaining = self.inventory.get(item_name, 0) - count
            if remaining > 0:
                self.inventory[item_name] = remaining
            else:
                self.inventory.pop(item_name, None)
        return True

    def _plant_slot(self, slot: PlantSlot, seed: PlantType):
        if getattr(slot, "has_scarecrow", False):
            self._play_sfx(self._sfx_ui_error, key="plant_error", debounce=0.12)
            return
        if getattr(slot, "salted", False):
            self._play_sfx(self._sfx_ui_error, key="plant_error", debounce=0.12)
            return
        if not self._pay_for_seed(seed):
            self._play_sfx(self._sfx_ui_error, key="plant_error", debounce=0.12)
            return
        slot.plant(seed)
        self._almanac.on_plant(seed.product_name)
        if JUICE_ENABLED:
            self._spawn_plant_juice(slot, seed)
        if self._sfx_plant or self._sfx_plant_variants:
            self._play_varied(self._sfx_plant_variants, self._sfx_plant)

    def _is_tool_unlocked(self, tool_id: str) -> bool:
        return str(tool_id) in self._unlocked_tools

    def _apply_tool_to_slot(self, slot: PlantSlot, tool_id: str) -> None:
        if not self._is_tool_unlocked(tool_id):
            self._play_sfx(self._sfx_ui_error, key="tool_locked", debounce=0.15)
            return
        if tool_id == TOOL_COMPOST:
            if (not slot.planted) or slot.dead or slot.harvestable:
                self._play_sfx(self._sfx_ui_error, key="tool_invalid", debounce=0.12)
                return
            if slot.compost_boost_remaining > 0.0:
                self._show_sell_feedback(f"Already composted - {max(1, int(slot.compost_boost_remaining) + 1)}s left.")
                self._play_sfx(self._sfx_ui_error, key="tool_invalid", debounce=0.12)
                return
            have = self.inventory.get(COMPOST_ITEM_NAME, 0)
            if have < 1:
                self._play_sfx(self._sfx_ui_error, key="tool_invalid", debounce=0.12)
                return
            if have == 1:
                self.inventory.pop(COMPOST_ITEM_NAME, None)
            else:
                self.inventory[COMPOST_ITEM_NAME] = have - 1
            slot.apply_compost(COMPOST_BOOST_SECONDS)
            self._play_sfx(self._sfx_tool_place, key="tool_place", debounce=0.08)
            self._spawn_tool_juice(slot, tool_id)
            return

        if tool_id == TOOL_SCARECROW:
            if slot.planted or slot.dead:
                self._play_sfx(self._sfx_ui_error, key="tool_invalid", debounce=0.12)
                return
            if slot.has_scarecrow:
                self._spawn_tool_juice(slot, tool_id)
                slot.remove_scarecrow()
                self._play_sfx(self._sfx_tool_place, key="tool_place", debounce=0.08)
                return
            if self.money < int(SCARECROW_COST):
                self._money_flash_timer = 20
                self._play_sfx(self._sfx_ui_error, key="tool_invalid", debounce=0.12)
                return
            self.money -= int(SCARECROW_COST)
            slot.place_scarecrow(SCARECROW_DURATION_SECONDS)
            self._play_sfx(self._sfx_tool_place, key="tool_place", debounce=0.08)
            self._spawn_tool_juice(slot, tool_id)
            return

        if tool_id == TOOL_LIGHTNING_ROD:
            if (not slot.planted) or slot.dead:
                self._play_sfx(self._sfx_ui_error, key="tool_invalid", debounce=0.12)
                return
            if self.money < int(LIGHTNING_ROD_COST):
                self._money_flash_timer = 20
                self._play_sfx(self._sfx_ui_error, key="tool_invalid", debounce=0.12)
                return
            self.money -= int(LIGHTNING_ROD_COST)
            slot.add_lightning_rod_charges(LIGHTNING_ROD_CHARGES)
            self._play_sfx(self._sfx_tool_place, key="tool_place", debounce=0.08)
            self._spawn_tool_juice(slot, tool_id)
            return

    def _harvest(self, slot: PlantSlot):
        if not slot.seed:
            return
        seed = slot.seed
        name = seed.product_name
        golden = bool(getattr(slot, "is_golden", False))
        store = self._golden_inventory if golden else self.inventory
        store[name] = store.get(name, 0) + seed.harvest_yield
        self._almanac.on_harvest(name, seed.harvest_yield)
        if self._sfx_harvest or self._sfx_harvest_variants:
            self._play_varied(self._sfx_harvest_variants, self._sfx_harvest, base_volume=0.5)
        if JUICE_ENABLED:
            self._spawn_harvest_juice(slot, seed, golden=golden)
        if getattr(seed, "spreads_on_harvest", False):
            # Mushroom: seed a free, fresh plant into a random eligible neighbor.
            try:
                idx = self.slots.index(slot)
            except ValueError:
                idx = -1
            cands = []
            for j in (idx - 1, idx + 1):
                if 0 <= j < len(self.slots):
                    nb = self.slots[j]
                    if (not nb.planted) and (not nb.dead) and (not getattr(nb, "has_scarecrow", False)) and (not getattr(nb, "salted", False)):
                        cands.append(nb)
            if cands:
                self._rng.choice(cands).plant(seed)
        # Prime overripen pays its extra value as cash (inventory can't carry the
        # multiplier); the base crop already went to inventory above.
        prime_bonus = harvest_prime_bonus_to_money(self, slot)
        if prime_bonus and JUICE_ENABLED:
            self._float_texts.append(FloatText(slot.rect.centerx, slot.rect.top - 28, f"+{prime_bonus}g", color=(250, 235, 140)))
            self._spawn_fly_coins(slot.rect.center, n=min(8, 2 + prime_bonus // 25))
        reset_slot_prime(slot)
        if seed.regrow_to_stage is None:
            slot.clear()
        else:
            # Regrow timing now comes from seed.regrow_seconds_per_stage via the
            # slot's _regrowing flag - no more mutating the shared seed instance.
            slot.regrow(seed.regrow_to_stage)

    def _sell_inventory(self):
        # Compute the sell total (preview; doesn't commit market decay) and show
        # the confirmation overlay.
        total = self._compute_sale_total(commit=False)
        if total == 0:
            if not self.inventory and not self._golden_inventory:
                self._show_sell_feedback("Nothing to sell - harvest crops into Inventory first.")
            else:
                self._show_sell_feedback("Nothing sellable in Inventory.")
            self._play_sfx(self._sfx_ui_error, key="sell_empty", debounce=0.15)
            return
        self._pending_sell_total = int(total)
        combined: dict[str, int] = {}
        for n, c in self.inventory.items():
            combined[n] = combined.get(n, 0) + int(c)
        for n, c in self._golden_inventory.items():
            combined[n] = combined.get(n, 0) + int(c)
        self._pending_sell_items = combined
        self._show_sell_confirm = True

    def _do_sell_inventory(self):
        # Recompute at commit so market-flooding decay is applied and the
        # per-day units-sold counters advance.
        total = self._compute_sale_total(commit=True)
        if total <= 0:
            self._pending_sell_total = None
            return
        self.money += int(total)
        self._total_earned += int(total)
        self._almanac.on_money_earned(int(total))
        for item_name, cnt in self._pending_sell_items.items():
            self._almanac.on_item_sold(item_name, int(cnt))
        if JUICE_ENABLED:
            self._float_texts.append(FloatText(self._sell_button.centerx, self._sell_button.top - 6, f"+{int(total)}g", color=(250, 235, 140)))
            self._spawn_fly_coins(self._sell_button.center, n=min(8, 3 + int(total) // 25))
        if self._sfx_sell or self._sfx_sell_variants:
            self._play_varied(self._sfx_sell_variants, self._sfx_sell, base_volume=0.4)
        self.inventory = {}
        self._golden_inventory = {}
        self._pending_sell_items = {}
        self._pending_sell_total = None

    def _sell_item(self, name: str, qty: int, *, golden: bool = False, source_pos=None) -> None:
        # Instant sell of one product stack (no confirm). Reuses the market
        # decay model and advances today's units-sold counter.
        store = self._golden_inventory if golden else self.inventory
        have = int(store.get(name, 0))
        qty = max(0, min(int(qty), have))
        if qty <= 0:
            return
        if name not in self.items:
            self._show_sell_feedback(f"{name} can't be sold here.")
            return
        total = self._sale_value_for(name, qty, golden=golden, commit=True)
        if total <= 0:
            return
        self.money += int(total)
        self._total_earned += int(total)
        self._almanac.on_money_earned(int(total))
        self._almanac.on_item_sold(name, int(qty))
        remaining = have - qty
        if remaining > 0:
            store[name] = remaining
        else:
            store.pop(name, None)
        if JUICE_ENABLED:
            self._float_texts.append(FloatText(self._field_rect.width + 150, 86, f"+{int(total)}g", color=(250, 235, 140)))
            self._spawn_fly_coins(source_pos or self._sell_button.center, n=min(6, 2 + int(qty)))
        if self._sfx_sell or self._sfx_sell_variants:
            self._play_varied(self._sfx_sell_variants, self._sfx_sell, base_volume=0.4)


# Endgame meta-progression (Legacy %, Next-Year preview, opt-in challenge ladder,
# Everbloom quest crop). Installed here as method hooks so every Game instance is
# consistent. endgame.py defers its own "import game", so this does not cycle.
from endgame import install_game_hooks as _install_endgame_hooks  # noqa: E402
_install_endgame_hooks(Game)
