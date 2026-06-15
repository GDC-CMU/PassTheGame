from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import pygame

from settings import (
    SCREEN_W,
    UI_PANEL_W,
    SUN_X,
    SUN_Y,
    SUN_RADIUS,
    DROUGHT_TITAN_WIDTH,
    DROUGHT_TITAN_HEIGHT,
    DROUGHT_TITAN_Y,
    DROUGHT_TITAN_MAX_HP,
    DROUGHT_TITAN_SPAWN_EVERY_SECONDS,
    DROUGHT_TITAN_STRIKE_COOLDOWN_SECONDS,
    DROUGHT_TITAN_STRIKE_WARNING_SECONDS,
    DROUGHT_TITAN_RETREAT_SECONDS,
    DROUGHT_TITAN_SUN_SPIKE,
    DROUGHT_TITAN_WATER_DRAIN,
    DROUGHT_TITAN_REWARD_ITEM_NAME,
    DROUGHT_TITAN_REWARD_ITEM_COUNT,
    DROUGHT_TITAN_NODAMAGE_BONUS_ITEM_NAME,
    DROUGHT_TITAN_NODAMAGE_BONUS_ITEM_COUNT,
    DROUGHT_TITAN_IMAGE_FILENAME,
    DROUGHT_TITAN_RING_MAX_RADIUS,
    DROUGHT_TITAN_RING_MIN_RADIUS,
    PERFECT_BLOCK_TOLERANCE_PX,
    PERFECT_BLOCK_BONUS_DAMAGE,
    PERFECT_BLOCK_RING_WIDTH,
    PERFECT_BLOCK_RING_COLOR,
    BOSS_COMBO_THRESHOLD,
    BOSS_COMBO_DAMAGE_BONUS,
)
from storm_titan import StormTitan, StormTitanConfig


@dataclass(frozen=True)
class DroughtTitanConfig(StormTitanConfig):
    """Tuning for the Drought Titan, which overheats the sun instead of striking
    a single slot. Block it by covering the sun with a cloud."""

    spawn_every_seconds: float = DROUGHT_TITAN_SPAWN_EVERY_SECONDS
    max_hp: int = DROUGHT_TITAN_MAX_HP

    strike_cooldown_seconds: float = DROUGHT_TITAN_STRIKE_COOLDOWN_SECONDS
    strike_warning_seconds: float = DROUGHT_TITAN_STRIKE_WARNING_SECONDS

    retreat_seconds: float = DROUGHT_TITAN_RETREAT_SECONDS

    width: int = DROUGHT_TITAN_WIDTH
    height: int = DROUGHT_TITAN_HEIGHT
    y: int = DROUGHT_TITAN_Y

    reward_item_name: str = DROUGHT_TITAN_REWARD_ITEM_NAME
    reward_item_count: int = DROUGHT_TITAN_REWARD_ITEM_COUNT
    no_damage_bonus_item_name: str = DROUGHT_TITAN_NODAMAGE_BONUS_ITEM_NAME
    no_damage_bonus_item_count: int = DROUGHT_TITAN_NODAMAGE_BONUS_ITEM_COUNT

    image_filename: str = DROUGHT_TITAN_IMAGE_FILENAME

    # It overheats the whole farm; it does not one-shot a single plant.
    lightning_kills_plant: bool = False

    warning_color: tuple[int, int, int] = (240, 160, 60)  # heat orange

    health_bar_width: int = 420
    health_bar_height: int = 20

    move_lerp_rate: float = 4.0


class DroughtTitan(StormTitan):
    """Drought Titan: hovers over the sun and overheats the farm. Block it by
    moving a cloud to cover the sun during the warning (which also shades the
    field and cuts sun-gain - a coherent single skill check)."""

    boss_id = "drought"
    display_name = "Drought Titan"
    plays_lightning_sfx = False  # it flares the sun; no thunderclap

    def __init__(self, config: DroughtTitanConfig | None = None, *, rng=None):
        super().__init__(config or DroughtTitanConfig(), rng=rng)

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _sun_rect() -> pygame.Rect:
        # The sun is stationary (sun.py uses SUN_X/SUN_Y/SUN_RADIUS).
        return pygame.Rect(SUN_X - SUN_RADIUS, SUN_Y - SUN_RADIUS, SUN_RADIUS * 2, SUN_RADIUS * 2)

    @staticmethod
    def _living_planted(slots: Sequence[object]) -> list[object]:
        return [s for s in slots if getattr(s, "seed", None) is not None and not getattr(s, "dead", False)]

    def _covering_cloud(self, clouds: Iterable[object]):
        sr = self._sun_rect()
        covers = []
        for c in clouds:
            rect = getattr(c, "rect", None)
            if not isinstance(rect, pygame.Rect):
                continue
            cover_fn = getattr(c, "covers_sun", None)
            covered = cover_fn(sr) if callable(cover_fn) else rect.colliderect(sr)
            if covered:
                covers.append(c)
        if not covers:
            return None
        return min(covers, key=lambda c: c.rect.top)

    # ── battle loop (targets the SUN, not a slot) ─────────────────────────────
    def update_battle(self, dt: float, *, slots: Sequence[object], clouds: Iterable[object]) -> None:
        self._advance_anim(dt)
        if dt <= 0.0:
            return

        if self._state == self.STATE_WAITING:
            if not self.enabled:
                return
            self._spawn_remaining -= dt
            if self._spawn_remaining <= 0.0:
                self._begin_fight()
            return

        if self._state == self.STATE_RETREATING:
            self._retreat_remaining -= dt
            if self._retreat_remaining <= 0.0:
                self._reset_to_waiting()
            return

        # ACTIVE: hover over the sun, then warn + overheat.
        self._bolt_flash_remaining = max(0.0, self._bolt_flash_remaining - dt)
        self._target_x = float(SUN_X)
        self._smooth_move_x(dt)

        if self._warning_remaining > 0.0:
            self._warning_remaining -= dt
            if self._warning_remaining <= 0.0:
                self._resolve_strike(slots, clouds)
            return

        self._cooldown_remaining -= dt
        if self._cooldown_remaining > 0.0:
            return

        if self._living_planted(slots):
            self._warning_remaining = float(self.config.strike_warning_seconds)
        else:
            self._cooldown_remaining = 1.0

    def _resolve_strike(self, slots: Sequence[object], clouds: Iterable[object]) -> None:
        blocker = self._covering_cloud(clouds)
        self._bolt_flash_remaining = 0.30  # drives the heat-flare draw

        if blocker is not None:
            is_perfect = abs(int(blocker.rect.centerx) - int(SUN_X)) <= int(PERFECT_BLOCK_TOLERANCE_PX)
            self._last_strike_result = "perfect" if is_perfect else "block"
            damage = 1
            if is_perfect:
                damage += int(PERFECT_BLOCK_BONUS_DAMAGE)
                self._last_perfect_at = pygame.time.get_ticks() / 1000.0
                self._last_perfect_pos = (int(SUN_X), int(SUN_Y))
            self._block_combo += 1
            if self._block_combo >= int(BOSS_COMBO_THRESHOLD):
                damage += int(BOSS_COMBO_DAMAGE_BONUS)
            self._blocks_since_poll += 1
            self._hp = max(0, self._hp - int(damage))
            if self._hp <= 0:
                self._begin_retreat()
        else:
            self._block_combo = 0
            self._took_unblocked_hit = True
            self._last_strike_result = "hit"
            for s in self._living_planted(slots):
                try:
                    s.sun = min(100.0, float(s.sun) + float(DROUGHT_TITAN_SUN_SPIKE))
                    s.water = max(0.0, float(s.water) - float(DROUGHT_TITAN_WATER_DRAIN))
                except Exception:
                    pass

        self._cooldown_remaining = float(self.config.strike_cooldown_seconds)

    # ── drawing (reticle + flare over the SUN) ────────────────────────────────
    def draw_warning(self, surface: pygame.Surface, *, slots: Sequence[object]) -> None:
        if self._state != self.STATE_ACTIVE or self._warning_remaining <= 0.0:
            return
        warn_total = max(0.001, float(self.config.strike_warning_seconds))
        p = max(0.0, min(1.0, 1.0 - self._warning_remaining / warn_total))
        r_max, r_min = int(DROUGHT_TITAN_RING_MAX_RADIUS), int(DROUGHT_TITAN_RING_MIN_RADIUS)
        radius = int(r_min + (r_max - r_min) * (1.0 - p))
        wc, lc = self.config.warning_color, PERFECT_BLOCK_RING_COLOR
        color = tuple(int(wc[i] + (lc[i] - wc[i]) * p) for i in range(3))
        pygame.draw.circle(surface, color, (SUN_X, SUN_Y), r_min, 1)
        pygame.draw.circle(surface, color, (SUN_X, SUN_Y), radius, int(PERFECT_BLOCK_RING_WIDTH))

        # Field-wide heat haze that intensifies as the strike approaches.
        if p > 0.0:
            field_w = SCREEN_W - UI_PANEL_W
            haze = pygame.Surface((field_w, surface.get_height()), pygame.SRCALPHA)
            haze.fill((255, 140, 50, int(70 * p)))
            surface.blit(haze, (0, 0))

    def draw_bolt(self, surface: pygame.Surface) -> None:
        if self._bolt_flash_remaining <= 0.0:
            return
        t = max(0.0, min(1.0, self._bolt_flash_remaining / 0.30))
        for k, rr in enumerate((SUN_RADIUS + 12, SUN_RADIUS + 30, SUN_RADIUS + 50)):
            a = int(150 * t / (k + 1))
            ring = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 175, 70, a), (SUN_X, SUN_Y), int(rr), 4)
            surface.blit(ring, (0, 0))
        for i in range(12):
            ang = math.tau * i / 12
            reach = (SUN_RADIUS + 64) * t
            x2 = SUN_X + int(math.cos(ang) * reach)
            y2 = SUN_Y + int(math.sin(ang) * reach)
            pygame.draw.line(surface, (255, 205, 95), (SUN_X, SUN_Y), (x2, y2), 2)

    # ── fallback art: a scorching sun-demon when no PNG is provided ───────────
    @staticmethod
    def _draw_fallback_surface(w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, int(h * 0.55)
        r = int(min(w, h) * 0.34)

        # Heat rays.
        for i in range(16):
            ang = math.tau * i / 16
            x1 = cx + int(math.cos(ang) * r)
            y1 = cy + int(math.sin(ang) * r)
            x2 = cx + int(math.cos(ang) * (r + int(r * 0.5)))
            y2 = cy + int(math.sin(ang) * (r + int(r * 0.5)))
            pygame.draw.line(surf, (240, 140, 40, 220), (x1, y1), (x2, y2), 4)

        # Body.
        pygame.draw.circle(surf, (250, 170, 50, 245), (cx, cy), r)
        pygame.draw.circle(surf, (255, 210, 90, 255), (cx, cy), int(r * 0.7))

        # Angry eyes + scowl.
        eye = (90, 30, 10)
        le = pygame.Rect(cx - int(r * 0.45), cy - int(r * 0.2), int(r * 0.28), int(r * 0.16))
        re = pygame.Rect(cx + int(r * 0.17), cy - int(r * 0.2), int(r * 0.28), int(r * 0.16))
        pygame.draw.ellipse(surf, eye, le)
        pygame.draw.ellipse(surf, eye, re)
        pygame.draw.line(surf, eye, (le.left - 2, le.top - 5), (le.right + 2, le.top + 1), 3)
        pygame.draw.line(surf, eye, (re.left - 2, re.top + 1), (re.right + 2, re.top - 5), 3)
        pygame.draw.arc(surf, eye, pygame.Rect(cx - int(r * 0.3), cy + int(r * 0.18), int(r * 0.6), int(r * 0.4)), 3.4, 6.0, 3)
        return surf
