from __future__ import annotations

import math
import os
import random

import pygame
from plants import PlantType
from settings import (
    SALT_OVERLAY_COLOR, SALT_OVERLAY_ALPHA, WET_SOIL_COLOR, COMPOST_BOOST_SECONDS,
    STAR_QUALITY_THRESHOLD, STAR_MIN_ALIVE_SECONDS, SCORCH_WATER_DRAIN_PER_SEC,
)
import effects

PROPS_DIR = os.path.join(os.path.dirname(__file__), "props")

# Small cached font for slot badges (lightning-rod charge count).
_BADGE_FONT = None

# Soil tile (props/slot.png) cached per slot size. None once we know it is absent.
_SLOT_TILE_CACHE: dict = {}
_SLOT_TILE_MISSING = False


def _slot_tile(size: tuple[int, int]):
    """Return the painted soil tile scaled to `size`, or None if the asset is
    missing. Cached per size so we scale once."""
    global _SLOT_TILE_MISSING
    if _SLOT_TILE_MISSING:
        return None
    cached = _SLOT_TILE_CACHE.get(size)
    if cached is not None:
        return cached
    path = os.path.join(PROPS_DIR, "slot.png")
    if not os.path.exists(path):
        _SLOT_TILE_MISSING = True
        return None
    try:
        raw = pygame.image.load(path).convert_alpha()
        tile = pygame.transform.smoothscale(raw, size)
        _SLOT_TILE_CACHE[size] = tile
        return tile
    except Exception:
        _SLOT_TILE_MISSING = True
        return None


# Idle wind sway for healthy crops. Amplitude rises during Gusts and Cyclone
# fights; game.py sets the factor each frame.
WIND_SWAY_DEG = 3.0
_WIND_FACTOR = 1.0
RECOIL_SECONDS = 0.28   # harvest-recoil duration on a crop that re-fruits in place


def set_wind_factor(f: float) -> None:
    global _WIND_FACTOR
    _WIND_FACTOR = max(0.0, float(f))


def _sway_deg(x: int) -> int:
    # A slow per-crop sway, phase-offset by column x so the field is not in lockstep.
    deg = WIND_SWAY_DEG * _WIND_FACTOR * math.sin(pygame.time.get_ticks() * 0.0016 + x * 0.013)
    return int(round(deg))


def _glow_pulse() -> float:
    # One shared 0..1 pulse for every ready/golden glow, so a field full of them
    # breathes in unison instead of strobing as differently-timed pulses beat.
    return 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.0045)


def _badge_font():
    global _BADGE_FONT
    if _BADGE_FONT is None:
        _BADGE_FONT = pygame.font.SysFont(None, 14)
    return _BADGE_FONT


# ── plant meter visuals ──────────────────────────────────────────────────────
# The water/sun meters use a red→green→red gradient where the GREEN band lines
# up with the plant's healthy range (e.g. water_min..water_max) mapped onto the
# 0..100 axis, fading to red toward the extremes. The gradient depends only on
# the meter size and that range, so we cache one surface per (size, range) and
# reuse it for every slot/frame instead of rebuilding it 20+ times per frame.
_METER_GRADIENT_CACHE: dict[tuple[int, int, int, int], pygame.Surface] = {}

# Muted (not very bright) colors, drawn semi-transparently over the slot.
_METER_GREEN = (70, 175, 80)
_METER_RED = (200, 80, 70)
_METER_ALPHA = 150
_METER_CORNER_RADIUS = 4


def _build_meter_gradient(w: int, h: int, lo: float, hi: float) -> pygame.Surface:
    """Return a cached semi-transparent gradient.

    ``lo``/``hi`` are the healthy range as fractions of the 0..100 axis. Values
    inside the band are green; outside it fades to red toward the nearest
    extreme (0 on the left, 100/the right edge).
    """
    lo = max(0.0, min(1.0, lo))
    hi = max(0.0, min(1.0, hi))
    if hi < lo:
        lo, hi = hi, lo

    key = (w, h, round(lo * 1000), round(hi * 1000))
    cached = _METER_GRADIENT_CACHE.get(key)
    if cached is not None:
        return cached

    grad = pygame.Surface((w, h), pygame.SRCALPHA)
    span = max(1, w - 1)
    for x in range(w):
        frac = x / span
        if lo <= frac <= hi:
            dist = 0.0
        elif frac < lo:
            # 0 at the band edge, 1 at value 0 (left extreme).
            dist = (lo - frac) / lo if lo > 0.0 else 0.0
        else:
            # 0 at the band edge, 1 at value 100 (right extreme).
            dist = (frac - hi) / (1.0 - hi) if hi < 1.0 else 0.0
        dist = max(0.0, min(1.0, dist))
        r = int(_METER_GREEN[0] + (_METER_RED[0] - _METER_GREEN[0]) * dist)
        g = int(_METER_GREEN[1] + (_METER_RED[1] - _METER_GREEN[1]) * dist)
        b = int(_METER_GREEN[2] + (_METER_RED[2] - _METER_GREEN[2]) * dist)
        pygame.draw.line(grad, (r, g, b, _METER_ALPHA), (x, 0), (x, h - 1))

    # Round the corners by multiplying the gradient's alpha with a rounded mask.
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(
        mask, (255, 255, 255, 255), mask.get_rect(),
        border_radius=min(_METER_CORNER_RADIUS, h // 2),
    )
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    _METER_GRADIENT_CACHE[key] = grad
    return grad


class PlantSlot:
    """Runtime state for a single plant slot.

    Interface used by Game:
    - plant(seed): assign a PlantType and reset stats
    - clear(): remove plant and reset stats
    - update(...): evolve water/sun/growth and death state
    - draw(...): render slot and plant visuals
    - stats_lines(): tooltip content
    """
    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.seed: PlantType | None = None
        self.growth_stage = 0
        self._growth_frames = 0
        self.water = 50.0
        self.sun = 50.0
        self.dead = False
        self._bad_frames = 0.0
        # Seconds of "bad" conditions that would kill the plant. Recorded from
        # update() so the meters can vibrate harder as death approaches.
        self._bad_seconds_to_die = 6.0
        # True after the first harvest of a re-fruiting plant; switches growth
        # timing to seed.regrow_seconds_per_stage (if set) without mutating the
        # shared PlantType instance.
        self._regrowing = False
        # Per-slot cache for the idle wind-sway rotation (recomputed only when the
        # sprite or the rounded sway angle changes, not every frame).
        self._sway_key = None
        self._sway_surf = None
        self._recoil_t = 0.0   # >0 = playing the harvest recoil bounce
        self._ready_pop_t = 0.0
        self._frozen_seconds = 0.0   # >0 = Frost Titan froze this slot: growth stalls
        self._scorch_seconds = 0.0   # >0 = Glare Mote scorched this slot: soil keeps drying

        # ── slot effects / tools ─────────────────────────────────────────
        # Scarecrow occupies an empty slot and protects nearby slots. It wears
        # out over time (durability), then breaks and frees the slot.
        self.has_scarecrow = False
        self._scarecrow_seconds_remaining = 0.0
        self._scarecrow_total_seconds = 0.0

        # Lightning rod protects a planted slot from boss lightning.
        self.lightning_rod_charges = 0

        # Compost temporarily boosts growth speed.
        self._compost_boost_remaining = 0.0

        # Salted soil: an unblocked boss strike locks this slot from being
        # replanted until the timer runs out.
        self._salted_seconds_remaining = 0.0

        # Blight: a within-season soil sickness from unblocked titan hits. It tints
        # the soil, slows growth, can spread to a neighbor, and heals at the season
        # boundary. Unlike salt it does not block planting; it persists across
        # replanting until the season turns.
        self._blight = 0.0

        # Crop quality: time spent in the healthy range over the growing life.
        # A high ratio yields a Golden (2x) harvest.
        self._alive_seconds = 0.0
        self._in_range_seconds = 0.0
        self._quality_eligible = True

    @property
    def planted(self) -> bool:
        return self.seed is not None

    @property
    def harvestable(self) -> bool:
        return self.seed is not None and self.growth_stage >= self.seed.growth_stages

    @property
    def growth_ratio(self) -> float:
        """0.0 at planting → 1.0 when ready to harvest."""
        if not self.seed or self.dead:
            return 0.0
        if self.harvestable:
            return 1.0
        stages = int(self.seed.growth_stages)
        if stages <= 1:
            return 1.0
        per_stage = max(0.001, self._active_seconds_per_stage)
        stage_progress = (self.growth_stage - 1) + min(1.0, self._growth_frames / per_stage)
        return max(0.0, min(1.0, stage_progress / (stages - 1)))

    @property
    def _active_seconds_per_stage(self) -> float:
        """Per-stage time, using the slower regrow time after the first harvest."""
        s = self.seed
        if s is None:
            return 1.0
        if self._regrowing and getattr(s, "regrow_seconds_per_stage", None) is not None:
            return float(s.regrow_seconds_per_stage)
        return float(s.seconds_per_stage)

    @property
    def quality_ratio(self) -> float:
        """Fraction of growing life spent within the seed's water+sun range."""
        if self._alive_seconds <= 0.0:
            return 0.0
        return max(0.0, min(1.0, self._in_range_seconds / self._alive_seconds))

    @property
    def is_golden(self) -> bool:
        """True if this plant has earned a Golden harvest right now."""
        return (self._quality_eligible
                and self._alive_seconds >= STAR_MIN_ALIVE_SECONDS
                and self.quality_ratio >= STAR_QUALITY_THRESHOLD)

    @property
    def bad_ratio(self) -> float:
        """0.0 when healthy, approaching 1.0 as the plant nears death."""
        if not self.seed or self.dead or self.harvestable:
            return 0.0
        threshold = self._bad_seconds_to_die if self._bad_seconds_to_die > 0 else 6.0
        return max(0.0, min(1.0, self._bad_frames / threshold))

    @property
    def in_range(self) -> bool:
        """True while a growing plant's water and sun are both in its healthy bands."""
        if not self.seed or self.dead:
            return False
        s = self.seed
        return (s.water_min <= self.water <= s.water_max
                and s.sun_min <= self.sun <= s.sun_max)

    def plant(self, seed: PlantType):
        if self.salted:
            return
        self.seed = seed
        self.growth_stage = 1
        self._growth_frames = 0
        # Start in the middle of the plant's healthy range so it begins happy
        # instead of already drifting toward a bad value.
        self.water = (seed.water_min + seed.water_max) / 2.0
        self.sun = (seed.sun_min + seed.sun_max) / 2.0
        self.dead = False
        self._bad_frames = 0.0
        self.lightning_rod_charges = 0
        self._compost_boost_remaining = 0.0
        self._regrowing = False
        self._alive_seconds = 0.0
        self._in_range_seconds = 0.0
        self._quality_eligible = True
        self._recoil_t = RECOIL_SECONDS   # plop-in: spring up from a squash when planted
        self._ready_pop_t = 0.0

    def clear(self):
        self.seed = None
        self.growth_stage = 0
        self._growth_frames = 0
        self.water = 50.0
        self.sun = 50.0
        self.dead = False
        self._bad_frames = 0.0
        self.lightning_rod_charges = 0
        self._compost_boost_remaining = 0.0
        self._regrowing = False
        self._alive_seconds = 0.0
        self._in_range_seconds = 0.0
        self._quality_eligible = True
        self._ready_pop_t = 0.0
    
    def regrow(self, stage):
        #reset to a specific grow stage, but keep seed planted
        # Clamp below growth_stages so a re-fruit never lands already
        # harvestable (which would be an infinite-harvest loop).
        if self.seed:
            stage = min(int(stage), max(1, int(self.seed.growth_stages) - 1))
        self.growth_stage = stage
        self._growth_frames = 0
        self._regrowing = True
        self._recoil_t = RECOIL_SECONDS   # spring back after the pluck
        if self.seed:
            self.water = (self.seed.water_min + self.seed.water_max) / 2.0
            self.sun = (self.seed.sun_min + self.seed.sun_max) / 2.0
        else:
            self.water = 50.0
            self.sun = 50.0
        self._bad_frames = 0.0
        # A re-fruit is judged on its own cycle (real grow time), so reset the
        # quality timers but keep eligibility.
        self._alive_seconds = 0.0
        self._in_range_seconds = 0.0
        self._quality_eligible = True
        self._ready_pop_t = 0.0

    def trigger_ready_pop(self) -> None:
        self._ready_pop_t = 0.22

    # ── tools / effects ──────────────────────────────────────────────────
    @property
    def compost_boost_remaining(self) -> float:
        return float(self._compost_boost_remaining)

    def apply_compost(self, seconds: float) -> None:
        self._compost_boost_remaining = max(0.0, float(seconds))

    @property
    def compost_ratio(self) -> float:
        """Remaining compost boost as 0..1 (cap is one application)."""
        if self._compost_boost_remaining <= 0.0 or COMPOST_BOOST_SECONDS <= 0.0:
            return 0.0
        return max(0.0, min(1.0, self._compost_boost_remaining / float(COMPOST_BOOST_SECONDS)))

    def place_scarecrow(self, seconds: float) -> None:
        self.has_scarecrow = True
        self._scarecrow_total_seconds = max(0.0, float(seconds))
        self._scarecrow_seconds_remaining = self._scarecrow_total_seconds

    def remove_scarecrow(self) -> None:
        self.has_scarecrow = False
        self._scarecrow_seconds_remaining = 0.0
        self._scarecrow_total_seconds = 0.0

    @property
    def scarecrow_ratio(self) -> float:
        """Remaining durability as a 0..1 fraction (0 when no scarecrow)."""
        if not self.has_scarecrow or self._scarecrow_total_seconds <= 0.0:
            return 0.0
        return max(0.0, min(1.0, self._scarecrow_seconds_remaining / self._scarecrow_total_seconds))

    def add_lightning_rod_charges(self, charges: int) -> None:
        self.lightning_rod_charges = max(0, int(charges))

    @property
    def salted(self) -> bool:
        return self._salted_seconds_remaining > 0.0

    def salt(self, seconds: float) -> None:
        self._salted_seconds_remaining = max(self._salted_seconds_remaining, float(seconds))

    def scorch(self, seconds: float, water_loss: float = 0.0) -> None:
        """Heat-scorch the soil: evaporate a chunk of water now and keep it drying
        for a few seconds. Recoverable by re-watering; never sets dead directly."""
        if not self.seed or self.dead:
            return
        if water_loss:
            self.water = max(0.0, self.water - float(water_loss))
        self._scorch_seconds = max(self._scorch_seconds, float(seconds))

    @property
    def blight(self) -> float:
        return self._blight

    def apply_blight(self, amount: float = 1.0) -> None:
        self._blight = max(0.0, min(1.0, self._blight + float(amount)))

    def clear_blight(self) -> None:
        self._blight = 0.0

    @property
    def growth_blight_mult(self) -> float:
        """Growth multiplier from blight: a fully blighted plot grows at half speed."""
        return 1.0 - 0.5 * max(0.0, min(1.0, self._blight))

    # ── save / load ──────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "seed": type(self.seed).__name__ if self.seed else None,
            "growth_stage": self.growth_stage,
            "growth_frames": float(self._growth_frames),
            "water": float(self.water),
            "sun": float(self.sun),
            "dead": bool(self.dead),
            "bad_frames": float(self._bad_frames),
            "has_scarecrow": bool(self.has_scarecrow),
            "scarecrow_seconds_remaining": float(self._scarecrow_seconds_remaining),
            "scarecrow_total_seconds": float(self._scarecrow_total_seconds),
            "lightning_rod_charges": int(self.lightning_rod_charges),
            "compost_boost_remaining": float(self._compost_boost_remaining),
            "regrowing": bool(self._regrowing),
            "salted_seconds_remaining": float(self._salted_seconds_remaining),
            "blight": float(self._blight),
            "alive_seconds": float(self._alive_seconds),
            "in_range_seconds": float(self._in_range_seconds),
            "quality_eligible": bool(self._quality_eligible),
        }

    def from_dict(self, data: dict, seed_lookup: dict) -> None:
        name = data.get("seed")
        self.seed = seed_lookup.get(name) if name else None
        self.growth_stage = int(data.get("growth_stage", 0))
        self._growth_frames = float(data.get("growth_frames", 0.0))
        self.water = float(data.get("water", 50.0))
        self.sun = float(data.get("sun", 50.0))
        self.dead = bool(data.get("dead", False))
        self._bad_frames = float(data.get("bad_frames", 0.0))
        self.has_scarecrow = bool(data.get("has_scarecrow", False))
        self._scarecrow_seconds_remaining = float(data.get("scarecrow_seconds_remaining", 0.0))
        self._scarecrow_total_seconds = float(data.get("scarecrow_total_seconds", 0.0))
        self.lightning_rod_charges = int(data.get("lightning_rod_charges", 0))
        self._compost_boost_remaining = float(data.get("compost_boost_remaining", 0.0))
        self._regrowing = bool(data.get("regrowing", False))
        self._salted_seconds_remaining = float(data.get("salted_seconds_remaining", 0.0))
        self._blight = float(data.get("blight", 0.0))
        self._alive_seconds = float(data.get("alive_seconds", 0.0))
        self._in_range_seconds = float(data.get("in_range_seconds", 0.0))
        self._quality_eligible = bool(data.get("quality_eligible", True))

    def update(
        self,
        water_delta: float,
        sun_delta: float,
        *,
        water_kill: float,
        sun_kill: float,
        bad_seconds_to_die: float,
        bad_recovery_rate: float,
        growth_rate_good: float,
        growth_rate_bad: float,
        dt: float,
    ):
        self.water = max(0.0, min(100.0, self.water + water_delta))
        self.sun = max(0.0, min(100.0, self.sun + sun_delta))

        self._bad_seconds_to_die = bad_seconds_to_die

        if self._compost_boost_remaining > 0.0:
            self._compost_boost_remaining = max(0.0, self._compost_boost_remaining - dt)

        if self._recoil_t > 0.0:
            self._recoil_t = max(0.0, self._recoil_t - dt)
        if self._ready_pop_t > 0.0:
            self._ready_pop_t = max(0.0, self._ready_pop_t - dt)

        if self._frozen_seconds > 0.0:
            self._frozen_seconds = max(0.0, self._frozen_seconds - dt)

        if self._scorch_seconds > 0.0:
            self._scorch_seconds = max(0.0, self._scorch_seconds - dt)
            self.water = max(0.0, self.water - float(SCORCH_WATER_DRAIN_PER_SEC) * dt)

        if self.has_scarecrow and self._scarecrow_total_seconds > 0.0:
            self._scarecrow_seconds_remaining = max(0.0, self._scarecrow_seconds_remaining - dt)
            if self._scarecrow_seconds_remaining <= 0.0:
                self.remove_scarecrow()

        if self._salted_seconds_remaining > 0.0:
            self._salted_seconds_remaining = max(0.0, self._salted_seconds_remaining - dt)

        if not self.seed or self.harvestable or self.dead:
            return

        in_range = self.seed.water_min <= self.water <= self.seed.water_max and self.seed.sun_min <= self.sun <= self.seed.sun_max
        # Quality tracking, only while actively growing (guarded above).
        self._alive_seconds += dt
        if in_range:
            self._in_range_seconds += dt
        in_over = self.water >= water_kill or self.sun >= sun_kill
        frozen = self._frozen_seconds > 0.0
        if in_range:
            self._bad_frames = max(0.0, self._bad_frames - bad_recovery_rate * dt)
            if not frozen:
                self._growth_frames += growth_rate_good * dt
        else:
            rate = 2.0 if in_over else 1.0
            self._bad_frames += rate * dt
            if not frozen:
                self._growth_frames += growth_rate_bad * dt

        if self._bad_frames >= bad_seconds_to_die:
            self.dead = True
            return

        if self._growth_frames >= self._active_seconds_per_stage:
            self._growth_frames = 0
            self.growth_stage += 1

    def strike_lightning(self, salt_seconds: float = 0.0):
        """Apply an instant lightning strike to this slot.

        Kept intentionally small so other systems (bosses, events, etc.) can
        damage plants without rewriting the core update loop.
        """
        if not self.seed or self.dead:
            return

        # Storm-fed crops (e.g. Lightning Vine) turn a strike into a growth
        # surge instead of dying - and never waste a rod or get salted.
        if getattr(self.seed, "lightning_surge_on_strike", False):
            self.growth_stage = min(self.growth_stage + 1, self.seed.growth_stages)
            self._growth_frames = 0
            self._bad_frames = 0.0
            self.water = (self.seed.water_min + self.seed.water_max) / 2.0
            self.sun = (self.seed.sun_min + self.seed.sun_max) / 2.0
            # Growth handed out by the strike, not earned: no Golden this cycle.
            self._quality_eligible = False
            return

        if self.lightning_rod_charges > 0:
            # I consume a charge and keep the plant alive (no salt).
            self.lightning_rod_charges = max(0, int(self.lightning_rod_charges) - 1)
            return

        self.dead = True
        # Optional flavor: a struck plant is dried out and over-sunned.
        self.water = 0.0
        self.sun = 100.0
        if salt_seconds > 0.0:
            self.salt(salt_seconds)

    def draw(
        self,
        surface: pygame.Surface,
        empty_color: tuple[int, int, int],
        border_color: tuple[int, int, int],
        *,
        phase_image: pygame.Surface | None = None,
        dead_image: pygame.Surface | None = None,
    ):
        # Soil darkens toward WET_SOIL_COLOR as the slot's water rises.
        t = max(0.0, min(1.0, self.water / 100.0))
        soil = tuple(int(empty_color[i] + (WET_SOIL_COLOR[i] - empty_color[i]) * t) for i in range(3))
        # Blight (within-season titan damage) tints the soil a sickly olive-grey.
        b = 0.0
        if self._blight > 0.0:
            b = max(0.0, min(1.0, self._blight))
            sick = (92, 104, 70)
            soil = tuple(int(soil[i] + (sick[i] - soil[i]) * (0.65 * b)) for i in range(3))

        tile = _slot_tile(self.rect.size)
        if tile is not None:
            # Painted soil tile as the base, then translucent washes so the wet and
            # blight feedback still reads while the tile texture shows through.
            surface.blit(tile, self.rect.topleft)
            if t > 0.02:
                wash = pygame.Surface(self.rect.size, pygame.SRCALPHA)
                wash.fill((*WET_SOIL_COLOR, int(95 * t)))
                surface.blit(wash, self.rect.topleft)
            if b > 0.0:
                wash = pygame.Surface(self.rect.size, pygame.SRCALPHA)
                wash.fill((92, 104, 70, int(150 * b)))
                surface.blit(wash, self.rect.topleft)
        else:
            pygame.draw.rect(surface, soil, self.rect, border_radius=4)
        pygame.draw.rect(surface, border_color, self.rect, 2, border_radius=4)
        if self._blight > 0.0:
            # A few dark blotches so the spreading cost reads at a glance.
            r = self.rect
            for ox, oy in ((6, 8), (r.width - 10, 12), (r.width // 2, r.height - 8)):
                pygame.draw.circle(surface, (60, 74, 46), (r.left + ox, r.top + oy), 2)

        if self.salted:
            self._draw_salt(surface)

        if self.harvestable and not self.dead:
            t = _glow_pulse()  # shared pulse (no strobing across many ready crops)
            grow = int(4 + 4 * t)
            glow_rect = self.rect.inflate(grow, grow)
            g = int(175 + 65 * t)
            pygame.draw.rect(surface, (80, g, 95), glow_rect, 2 + int(2 * t), border_radius=6)

        if not self.seed:
            if self.has_scarecrow:
                self._draw_scarecrow(surface)
            return

        cx, cy = self.rect.center
        stage = min(self.growth_stage, self.seed.growth_stages)
        size = 4 + stage * 3
        color = self.seed.base_color
        if self.dead:
            color = (90, 90, 90)
        elif self.harvestable:
            color = (min(color[0] + 30, 255), min(color[1] + 30, 255), min(color[2] + 30, 255))

        # Golden-in-progress: a soft gold pulse promises a 2x harvest while the crop
        # still lives, so the player can see what a death would cost them.
        if (not self.dead and not self.harvestable and self._quality_eligible
                and self.growth_ratio > 0.6 and self.quality_ratio >= STAR_QUALITY_THRESHOLD):
            pulse = _glow_pulse()
            glow = effects.radial_glow(int(self.rect.width * 0.6), (255, 214, 92), int(70 + 60 * pulse))
            surface.blit(glow, glow.get_rect(center=(cx, self.rect.bottom - 18)))

        br = 0.0 if self.dead else self.bad_ratio
        stem_color = (80, 120, 80) if not self.dead else (80, 80, 80)
        if self.seed and not self.dead and not self.harvestable:
            self._draw_band_need_pulse(surface, cx, cy)
        if self.dead and dead_image:
            img_rect = dead_image.get_rect(midbottom=(cx, self.rect.bottom - 4))
            surface.blit(dead_image, img_rect)
        elif phase_image:
            img = phase_image
            if br > 0.05:
                # Act 1-2 wilt: dim toward a sickly tone and droop further as it suffers.
                img = phase_image.copy()
                dim = tuple(int(255 - (255 - c) * br) for c in (150, 150, 120))
                img.fill(dim, special_flags=pygame.BLEND_RGB_MULT)
                if br > 0.15:
                    img = pygame.transform.rotate(img, -16.0 * br)
            elif not self.harvestable:
                if self._recoil_t > 0.0:
                    # Harvest recoil: squash then spring back, anchored at the base.
                    p = 1.0 - self._recoil_t / RECOIL_SECONDS
                    sy = 0.8 + 0.2 * effects.ease_out_elastic(max(0.0, min(1.0, p)))
                    h = max(1, int(phase_image.get_height() * sy))
                    img = pygame.transform.smoothscale(phase_image, (phase_image.get_width(), h))
                else:
                    # Healthy and growing: a gentle wind sway (cached per angle bucket).
                    deg = _sway_deg(self.rect.centerx)
                    key = (id(phase_image), deg)
                    if key != self._sway_key:
                        self._sway_surf = pygame.transform.rotate(phase_image, deg) if deg else phase_image
                        self._sway_key = key
                    img = self._sway_surf
            if self._ready_pop_t > 0.0:
                p = 1.0 - self._ready_pop_t / 0.22
                scale = 1.0 + 0.22 * (1.0 - p) * effects.ease_out_back(max(0.0, min(1.0, p)))
                w = max(1, int(img.get_width() * scale))
                h = max(1, int(img.get_height() * scale))
                img = pygame.transform.smoothscale(img, (w, h))
            img_rect = img.get_rect(midbottom=(cx, self.rect.bottom - 4))
            surface.blit(img, img_rect)
        else:
            if br > 0.05:
                color = tuple(int(c * (1.0 - 0.4 * br)) for c in color)
            if self._ready_pop_t > 0.0:
                p = 1.0 - self._ready_pop_t / 0.22
                size = int(size * (1.0 + 0.28 * (1.0 - p) * effects.ease_out_back(max(0.0, min(1.0, p)))))
            pygame.draw.line(surface, stem_color, (cx, self.rect.bottom - 6), (cx, cy), 2)
            pygame.draw.circle(surface, color, (cx, cy), size)

        self._draw_growth_bar(surface)
        self._draw_minibars(surface)
        self._draw_compost_badge(surface)
        self._draw_lightning_badge(surface)
        if self._frozen_seconds > 0.0:
            self._draw_frost(surface)
        if self._scorch_seconds > 0.0:
            self._draw_scorch(surface)

    def _band_need(self) -> tuple[str, tuple[int, int, int]] | None:
        if not self.seed or self.dead or self.harvestable:
            return None
        if self.water < self.seed.water_min:
            return ("water", (78, 168, 245))
        if self.water > self.seed.water_max:
            return ("water", (58, 98, 160))
        if self.sun < self.seed.sun_min:
            return ("sun", (252, 210, 82))
        if self.sun > self.seed.sun_max:
            return ("shade", (68, 62, 96))
        return None

    def _draw_band_need_pulse(self, surface: pygame.Surface, cx: int, cy: int) -> None:
        need = self._band_need()
        if need is None:
            return
        _kind, color = need
        pulse = _glow_pulse()
        radius = int(self.rect.width * (0.32 + 0.08 * pulse))
        glow = effects.radial_glow(radius, color, int(58 + 42 * pulse))
        surface.blit(glow, glow.get_rect(center=(cx, max(self.rect.top + 24, cy + 2))))
        ring_r = max(9, int(self.rect.width * (0.18 + 0.04 * pulse)))
        pygame.draw.circle(surface, (*color, 180), (cx, max(self.rect.top + 24, cy + 2)), ring_r, 2)

    def _draw_compost_badge(self, surface: pygame.Surface) -> None:
        if self._compost_boost_remaining <= 0.0:
            return
        r = self.rect
        bw = 12
        badge = pygame.Rect(r.left + 3, r.top + 3, bw, 12)
        pygame.draw.rect(surface, (60, 140, 60), badge, border_radius=3)
        pygame.draw.rect(surface, (30, 80, 30), badge, 1, border_radius=3)
        cx, cy = badge.center
        pygame.draw.line(surface, (200, 240, 190), (cx, cy + 3), (cx, cy - 3), 1)
        pygame.draw.circle(surface, (200, 240, 190), (cx - 2, cy - 1), 2)
        pygame.draw.circle(surface, (200, 240, 190), (cx + 2, cy - 1), 2)
        my = badge.bottom + 1
        pygame.draw.rect(surface, (25, 35, 25), (badge.left, my, bw, 3), border_radius=1)
        fill_w = int(bw * self.compost_ratio)
        if fill_w > 0:
            pygame.draw.rect(surface, (110, 210, 120), (badge.left, my, fill_w, 3), border_radius=1)

    def _draw_lightning_badge(self, surface: pygame.Surface) -> None:
        if self.lightning_rod_charges <= 0:
            return
        r = self.rect
        bw, bh = 12, 14
        badge = pygame.Rect(r.right - bw - 3, r.top + 3, bw, bh)
        pygame.draw.rect(surface, (60, 66, 78), badge, border_radius=3)
        pygame.draw.rect(surface, (150, 160, 175), badge, 1, border_radius=3)
        cx = badge.centerx
        pygame.draw.line(surface, (210, 220, 235), (cx, badge.bottom - 3), (cx, badge.top + 4), 2)
        pygame.draw.line(surface, (210, 220, 235), (cx, badge.top + 4), (cx - 2, badge.top + 1), 1)
        pygame.draw.line(surface, (210, 220, 235), (cx, badge.top + 4), (cx + 2, badge.top + 1), 1)
        txt = _badge_font().render(str(int(self.lightning_rod_charges)), True, (235, 240, 250))
        surface.blit(txt, txt.get_rect(midright=(badge.left - 1, badge.centery)))

    def _draw_growth_bar(self, surface: pygame.Surface) -> None:
        if not self.seed or self.dead:
            return

        meter_h = 10
        lift = 34
        meter_w = max(16, self.rect.width - 4)
        meter_x = self.rect.centerx - meter_w // 2
        meter_y = self.rect.top - meter_h - lift
        if meter_y < 0:
            meter_y = 0

        ratio = self.growth_ratio
        bg = pygame.Rect(meter_x, meter_y, meter_w, meter_h)
        pygame.draw.rect(surface, (20, 24, 30), bg, border_radius=4)
        pygame.draw.rect(surface, (240, 240, 245), bg, 2, border_radius=4)

        inner_w = meter_w - 4
        fill_w = max(0, int(inner_w * ratio))
        if fill_w > 0:
            fill = pygame.Rect(meter_x + 2, meter_y + 2, fill_w, meter_h - 4)
            fill_color = (55, 220, 100) if self.harvestable else (100, 190, 75)
            pygame.draw.rect(surface, fill_color, fill, border_radius=3)

    def _draw_frost(self, surface: pygame.Surface) -> None:
        # A pale-blue chill over a frozen slot, with a few ice crystals; fades as the
        # freeze wears off so the player sees the stall lifting.
        t = max(0.0, min(1.0, self._frozen_seconds / 5.0))
        overlay = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        overlay.fill((180, 215, 245, int(70 + 60 * t)))
        for gx, gy in ((0.25, 0.3), (0.7, 0.4), (0.45, 0.7), (0.82, 0.72)):
            ix, iy = int(self.rect.width * gx), int(self.rect.height * gy)
            pygame.draw.line(overlay, (235, 248, 255, 220), (ix - 3, iy), (ix + 3, iy), 1)
            pygame.draw.line(overlay, (235, 248, 255, 220), (ix, iy - 3), (ix, iy + 3), 1)
        surface.blit(overlay, self.rect.topleft)

    def _draw_scorch(self, surface: pygame.Surface) -> None:
        # A warm amber haze with rising heat-shimmer streaks over a scorched slot;
        # fades as the scorch wears off so the player sees the soil cooling.
        t = max(0.0, min(1.0, self._scorch_seconds / 4.0))
        overlay = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        overlay.fill((250, 150, 60, int(40 + 55 * t)))
        for gx, gy in ((0.3, 0.7), (0.6, 0.6), (0.8, 0.75)):
            ix, iy = int(self.rect.width * gx), int(self.rect.height * gy)
            pygame.draw.line(overlay, (255, 220, 150, 200), (ix, iy), (ix, iy - 5), 1)
        surface.blit(overlay, self.rect.topleft)

    def _draw_salt(self, surface: pygame.Surface) -> None:
        # Pale scattered grains over the soil, signalling "locked / salted".
        overlay = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        overlay.fill((*SALT_OVERLAY_COLOR, SALT_OVERLAY_ALPHA))
        for gx, gy in ((0.2, 0.35), (0.5, 0.6), (0.78, 0.4), (0.4, 0.8), (0.85, 0.72), (0.62, 0.25)):
            pygame.draw.circle(
                overlay, (255, 255, 255, 210),
                (int(self.rect.width * gx), int(self.rect.height * gy)), 2,
            )
        surface.blit(overlay, self.rect.topleft)

    def _draw_scarecrow(self, surface: pygame.Surface) -> None:
        rect = self.rect
        cx = rect.centerx

        # ── durability meter (horizontal, drains left→right) ──────────────
        meter_h = 6
        meter_w = rect.width - 12
        meter_x = rect.left + 6
        meter_y = rect.bottom - 4 - meter_h
        bg = pygame.Rect(meter_x, meter_y, meter_w, meter_h)
        pygame.draw.rect(surface, (35, 30, 28), bg, border_radius=3)
        pygame.draw.rect(surface, (15, 12, 10), bg, 1, border_radius=3)
        ratio = self.scarecrow_ratio
        fill_w = int((meter_w - 2) * ratio)
        if fill_w > 0:
            fill = pygame.Rect(meter_x + 1, meter_y + 1, fill_w, meter_h - 2)
            pygame.draw.rect(surface, (80, 190, 90), fill, border_radius=2)

        # ── figure: a tall, skinny scarecrow that rises above the slot ────
        post = (100, 70, 44)
        post_d = (52, 35, 22)
        straw = (235, 205, 110)
        straw_d = (180, 150, 70)
        cloth = (175, 82, 70)
        cloth_d = (120, 52, 46)
        hat = (55, 50, 65)
        stitch = (60, 40, 30)

        base_y = meter_y - 3
        height = int(rect.height * 1.7)
        head_r = max(4, rect.width // 8)
        head_cy = base_y - height + head_r

        # Central post (thin).
        pygame.draw.line(surface, post_d, (cx, head_cy), (cx, base_y), 5)
        pygame.draw.line(surface, post, (cx, head_cy), (cx, base_y), 2)

        # Crossbar shoulders (thin), set below the head.
        arm_y = head_cy + head_r + int(height * 0.16)
        arm = int(rect.width * 0.5)
        pygame.draw.line(surface, post_d, (cx - arm, arm_y), (cx + arm, arm_y), 5)
        pygame.draw.line(surface, post, (cx - arm, arm_y), (cx + arm, arm_y), 2)
        # Straw tufts spilling from the sleeve ends.
        for hx in (cx - arm, cx + arm):
            for a in range(-2, 3):
                pygame.draw.line(surface, straw_d, (hx, arm_y), (hx + a * 2, arm_y + 7), 1)

        # Skinny tattered tunic hanging from the shoulders.
        tunic_top = arm_y - 2
        tunic_bottom = base_y - int(height * 0.12)
        tw_top = max(4, int(rect.width * 0.28))
        tw_bot = max(3, int(rect.width * 0.22))
        pygame.draw.polygon(surface, cloth_d, [
            (cx - tw_top, tunic_top), (cx + tw_top, tunic_top),
            (cx + tw_bot, tunic_bottom), (cx - tw_bot, tunic_bottom),
        ])
        pygame.draw.polygon(surface, cloth, [
            (cx - tw_top + 1, tunic_top + 1), (cx + tw_top - 1, tunic_top + 1),
            (cx + tw_bot - 1, tunic_bottom - 2), (cx - tw_bot + 1, tunic_bottom - 2),
        ])
        # Tattered hem.
        step = max(2, tw_bot // 2)
        for i in range(-2, 3):
            sx = cx + i * step
            pygame.draw.line(surface, cloth_d, (sx, tunic_bottom - 2), (sx, tunic_bottom + 6), 2)
        # Sleeves draped along the crossbar.
        pygame.draw.line(surface, cloth, (cx - arm + 2, arm_y), (cx - tw_top, tunic_top + 4), 3)
        pygame.draw.line(surface, cloth, (cx + arm - 2, arm_y), (cx + tw_top, tunic_top + 4), 3)

        # Head.
        pygame.draw.circle(surface, straw_d, (cx, head_cy), head_r + 1)
        pygame.draw.circle(surface, straw, (cx, head_cy), head_r)
        # Stitched X eyes.
        e = max(2, head_r // 2)
        for ox in (-e, e):
            pygame.draw.line(surface, stitch, (cx + ox - 2, head_cy - 2), (cx + ox + 1, head_cy + 1), 1)
            pygame.draw.line(surface, stitch, (cx + ox + 1, head_cy - 2), (cx + ox - 2, head_cy + 1), 1)
        # Pointed hat.
        brim = head_r + 5
        pygame.draw.line(surface, hat, (cx - brim, head_cy - head_r + 1), (cx + brim, head_cy - head_r + 1), 3)
        pygame.draw.polygon(surface, hat, [
            (cx - head_r, head_cy - head_r + 1),
            (cx + head_r, head_cy - head_r + 1),
            (cx, head_cy - head_r - 11),
        ])

    def _draw_minibars(self, surface: pygame.Surface):
        meter_h = 9
        icon_w = 9
        icon_gap = 2
        left_margin = 4
        right_margin = 4
        meter_spacing = 3
        bottom_margin = 4

        bar_x = self.rect.left + left_margin + icon_w + icon_gap
        bar_width = self.rect.right - right_margin - bar_x
        if bar_width <= 8:
            return

        water_y = self.rect.bottom - bottom_margin - meter_h
        sun_y = water_y - meter_h - meter_spacing

        sun_pct = max(0.0, min(1.0, self.sun / 100.0))
        water_pct = max(0.0, min(1.0, self.water / 100.0))

        # Vibrate a meter once its stat leaves the healthy range; the shake
        # grows as the plant gets closer to dying.
        ratio = self.bad_ratio
        sun_bad = not (self.seed.sun_min <= self.sun <= self.seed.sun_max)
        water_bad = not (self.seed.water_min <= self.water <= self.seed.water_max)
        sun_dx, sun_dy = self._meter_shake(ratio) if (sun_bad and ratio > 0.0) else (0, 0)
        water_dx, water_dy = self._meter_shake(ratio) if (water_bad and ratio > 0.0) else (0, 0)

        # Sun meter (top), water meter (bottom). The green band of each meter
        # lines up with this plant's healthy range for that stat.
        self._draw_meter(
            surface, bar_x + sun_dx, sun_y + sun_dy, bar_width, meter_h, sun_pct, "sun",
            self.seed.sun_min / 100.0, self.seed.sun_max / 100.0,
            pygame.Rect(self.rect.left + left_margin + sun_dx, sun_y + sun_dy, icon_w, meter_h),
        )
        self._draw_meter(
            surface, bar_x + water_dx, water_y + water_dy, bar_width, meter_h, water_pct, "water",
            self.seed.water_min / 100.0, self.seed.water_max / 100.0,
            pygame.Rect(self.rect.left + left_margin + water_dx, water_y + water_dy, icon_w, meter_h),
        )

    @staticmethod
    def _meter_shake(ratio: float) -> tuple[int, int]:
        ratio = max(0.0, min(1.0, ratio))
        if ratio <= 0.0:
            return (0, 0)
        # Intermittent at low intensity, ramping to continuous near death.
        chance = min(1.0, ratio * 1.6)
        if random.random() > chance:
            return (0, 0)
        amp = 1.0 + ratio * 1.2  # ~1px twitch early, up to ~2px close to dying
        return (round(random.uniform(-amp, amp)), round(random.uniform(-amp, amp)))

    def _draw_meter(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        w: int,
        h: int,
        pct: float,
        kind: str,
        lo: float,
        hi: float,
        icon_rect: pygame.Rect,
    ):
        # Semi-transparent gradient whose green band matches the healthy range.
        surface.blit(_build_meter_gradient(w, h, lo, hi), (x, y))
        pygame.draw.rect(
            surface, (40, 45, 55), (x, y, w, h), 1,
            border_radius=min(_METER_CORNER_RADIUS, h // 2),
        )

        # Marker showing the current level, tinted by the wrong side when out of band.
        marker_w = 3
        marker_x = x + int(pct * (w - marker_w))
        marker = pygame.Rect(marker_x, y, marker_w, h)
        marker_color = (245, 245, 245)
        if pct < lo:
            marker_color = (78, 168, 245) if kind == "water" else (252, 210, 82)
        elif pct > hi:
            marker_color = (58, 98, 160) if kind == "water" else (68, 62, 96)
        pygame.draw.rect(surface, marker_color, marker, border_radius=2)
        pygame.draw.rect(surface, (60, 60, 70), marker, 1, border_radius=2)

        self._draw_meter_icon(surface, kind, icon_rect)

    def _draw_meter_icon(self, surface: pygame.Surface, kind: str, rect: pygame.Rect):
        cx, cy = rect.center
        r = max(2, min(rect.width, rect.height) // 2 - 1)
        if kind == "sun":
            for i in range(8):
                ang = math.tau * i / 8
                x1 = cx + int(math.cos(ang) * r)
                y1 = cy + int(math.sin(ang) * r)
                x2 = cx + int(math.cos(ang) * (r + 2))
                y2 = cy + int(math.sin(ang) * (r + 2))
                pygame.draw.line(surface, (250, 205, 70), (x1, y1), (x2, y2), 1)
            pygame.draw.circle(surface, (250, 205, 70), (cx, cy), r)
            pygame.draw.circle(surface, (255, 230, 140), (cx, cy), max(1, r - 2))
        else:
            pygame.draw.circle(surface, (70, 150, 235), (cx, cy + 1), r)
            pygame.draw.polygon(
                surface, (70, 150, 235),
                [(cx - r, cy + 1), (cx + r, cy + 1), (cx, cy - r - 2)],
            )
            pygame.draw.circle(surface, (160, 205, 250), (cx - 1, cy), max(1, r - 3))

    def stats_lines(self) -> list[str]:
        if not self.seed:
            return []
        stage = min(self.growth_stage, self.seed.growth_stages)
        status = "Dead" if self.dead else "Alive"
        lines = [
            f"{self.seed.name}",
            f"Status: {status}",
        ]
        if self.harvestable:
            lines.append("Ready - click to harvest")
        desc = getattr(self.seed, "description", "")
        if desc:
            lines.append(desc if len(desc) <= 44 else desc[:41] + "...")
        lines.extend([
            f"Stage: {stage}/{self.seed.growth_stages}",
            f"Water: {int(self.water)}",
            f"Water range: {int(self.seed.water_min)}-{int(self.seed.water_max)}",
            f"Sun: {int(self.sun)}",
            f"Sun range: {int(self.seed.sun_min)}-{int(self.seed.sun_max)}",
        ])

        if self.lightning_rod_charges > 0:
            lines.append(f"Lightning rod charges: {int(self.lightning_rod_charges)}")
        if self._compost_boost_remaining > 0.0:
            lines.append(f"Compost boost: {max(0, int(self._compost_boost_remaining) + 1)}s")
        return lines
