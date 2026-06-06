from __future__ import annotations

import math
import random

import pygame
from plants import PlantType


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

    @property
    def planted(self) -> bool:
        return self.seed is not None

    @property
    def harvestable(self) -> bool:
        return self.seed is not None and self.growth_stage >= self.seed.growth_stages

    @property
    def bad_ratio(self) -> float:
        """0.0 when healthy, approaching 1.0 as the plant nears death."""
        if not self.seed or self.dead or self.harvestable:
            return 0.0
        threshold = self._bad_seconds_to_die if self._bad_seconds_to_die > 0 else 6.0
        return max(0.0, min(1.0, self._bad_frames / threshold))

    def plant(self, seed: PlantType):
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
    
    def regrow(self, stage):
        #reset to a specific grow stage, but keep seed planted
        self.growth_stage = stage
        self._growth_frames = 0
        if self.seed:
            self.water = (self.seed.water_min + self.seed.water_max) / 2.0
            self.sun = (self.seed.sun_min + self.seed.sun_max) / 2.0
        else:
            self.water = 50.0
            self.sun = 50.0
        self._bad_frames = 0.0

    # ── tools / effects ──────────────────────────────────────────────────
    @property
    def compost_boost_remaining(self) -> float:
        return float(self._compost_boost_remaining)

    def apply_compost(self, seconds: float) -> None:
        self._compost_boost_remaining = max(0.0, float(seconds))

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

        if self.has_scarecrow and self._scarecrow_total_seconds > 0.0:
            self._scarecrow_seconds_remaining = max(0.0, self._scarecrow_seconds_remaining - dt)
            if self._scarecrow_seconds_remaining <= 0.0:
                self.remove_scarecrow()

        if not self.seed or self.harvestable or self.dead:
            return

        in_range = self.seed.water_min <= self.water <= self.seed.water_max and self.seed.sun_min <= self.sun <= self.seed.sun_max
        in_over = self.water >= water_kill or self.sun >= sun_kill
        if in_range:
            self._bad_frames = max(0.0, self._bad_frames - bad_recovery_rate * dt)
            self._growth_frames += growth_rate_good * dt
        else:
            rate = 2.0 if in_over else 1.0
            self._bad_frames += rate * dt
            self._growth_frames += growth_rate_bad * dt

        if self._bad_frames >= bad_seconds_to_die:
            self.dead = True
            return

        if self._growth_frames >= self.seed.seconds_per_stage:
            self._growth_frames = 0
            self.growth_stage += 1

    def strike_lightning(self):
        """Apply an instant lightning strike to this slot.

        Kept intentionally small so other systems (bosses, events, etc.) can
        damage plants without rewriting the core update loop.
        """
        if not self.seed or self.dead:
            return

        if self.lightning_rod_charges > 0:
            # I consume a charge and keep the plant alive.
            self.lightning_rod_charges = max(0, int(self.lightning_rod_charges) - 1)
            return

        self.dead = True
        # Optional flavor: a struck plant is dried out and over-sunned.
        self.water = 0.0
        self.sun = 100.0

    def draw(
        self,
        surface: pygame.Surface,
        empty_color: tuple[int, int, int],
        border_color: tuple[int, int, int],
        *,
        phase_image: pygame.Surface | None = None,
        dead_image: pygame.Surface | None = None,
    ):
        pygame.draw.rect(surface, empty_color, self.rect, border_radius=4)
        pygame.draw.rect(surface, border_color, self.rect, 2, border_radius=4)

        if self.harvestable and not self.dead:
            glow_rect = self.rect.inflate(4, 4)
            pygame.draw.rect(surface, (80, 200, 90), glow_rect, 3, border_radius=6)

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

        stem_color = (80, 120, 80) if not self.dead else (80, 80, 80)
        if self.dead and dead_image:
            img_rect = dead_image.get_rect(midbottom=(cx, self.rect.bottom - 4))
            surface.blit(dead_image, img_rect)
        elif phase_image:
            img_rect = phase_image.get_rect(midbottom=(cx, self.rect.bottom - 4))
            surface.blit(phase_image, img_rect)
        else:
            pygame.draw.line(surface, stem_color, (cx, self.rect.bottom - 6), (cx, cy), 2)
            pygame.draw.circle(surface, color, (cx, cy), size)

        self._draw_minibars(surface)

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

        # White marker showing the current level.
        marker_w = 3
        marker_x = x + int(pct * (w - marker_w))
        marker = pygame.Rect(marker_x, y, marker_w, h)
        pygame.draw.rect(surface, (245, 245, 245), marker, border_radius=2)
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
            f"Stage: {stage}/{self.seed.growth_stages}",
            f"Water: {int(self.water)}",
            f"Water range: {int(self.seed.water_min)}-{int(self.seed.water_max)}",
            f"Sun: {int(self.sun)}",
            f"Sun range: {int(self.seed.sun_min)}-{int(self.seed.sun_max)}",
        ]

        if self.lightning_rod_charges > 0:
            lines.append(f"Lightning rod charges: {int(self.lightning_rod_charges)}")
        if self._compost_boost_remaining > 0.0:
            lines.append(f"Compost boost: {max(0, int(self._compost_boost_remaining) + 1)}s")
        return lines
