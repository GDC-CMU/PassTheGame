from __future__ import annotations

import os
import random
import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import pygame

from settings import (
    SCREEN_W,
    UI_PANEL_W,
    STORM_TITAN_WIDTH,
    STORM_TITAN_HEIGHT,
    STORM_TITAN_Y,
    STORM_TITAN_MAX_HP,
    STORM_TITAN_SPAWN_EVERY_SECONDS,
    STORM_TITAN_STRIKE_COOLDOWN_SECONDS,
    STORM_TITAN_STRIKE_WARNING_SECONDS,
    STORM_TITAN_RETREAT_SECONDS,
    STORM_TITAN_REWARD_ITEM_NAME,
    STORM_TITAN_REWARD_ITEM_COUNT,
    STORM_TITAN_LIGHTNING_KILLS_PLANT,
    STORM_TITAN_IMAGE_FILENAME,
    PERFECT_BLOCK_WINDOW_SECONDS,
    PERFECT_BLOCK_BONUS_DAMAGE,
)

PROPS_DIR = os.path.join(os.path.dirname(__file__), "props")


@dataclass(frozen=True)
class StormTitanConfig:
    """Tuning parameters for Storm Titan.

    Defaults are sourced from settings.py so contributors can tweak values
    without touching the boss code.
    """

    spawn_every_seconds: float = STORM_TITAN_SPAWN_EVERY_SECONDS
    max_hp: int = STORM_TITAN_MAX_HP

    strike_cooldown_seconds: float = STORM_TITAN_STRIKE_COOLDOWN_SECONDS
    strike_warning_seconds: float = STORM_TITAN_STRIKE_WARNING_SECONDS

    retreat_seconds: float = STORM_TITAN_RETREAT_SECONDS

    reward_item_name: str = STORM_TITAN_REWARD_ITEM_NAME
    reward_item_count: int = STORM_TITAN_REWARD_ITEM_COUNT

    width: int = STORM_TITAN_WIDTH
    height: int = STORM_TITAN_HEIGHT
    y: int = STORM_TITAN_Y

    lightning_kills_plant: bool = STORM_TITAN_LIGHTNING_KILLS_PLANT

    image_filename: str = STORM_TITAN_IMAGE_FILENAME

    warning_color: tuple[int, int, int] = (220, 70, 70)
    bolt_color: tuple[int, int, int] = (255, 235, 120)
    bolt_shadow_color: tuple[int, int, int] = (255, 255, 255)

    # Movement: boss slides horizontally to the target before striking.
    move_lerp_rate: float = 5.0
    align_epsilon_px: float = 4.0

    # Damage: when unblocked, also strike adjacent slots (0 = only the target).
    aoe_radius_slots: int = 0

    # UI: health bar size on the top HUD.
    health_bar_width: int = 360
    health_bar_height: int = 18


class StormTitan(pygame.sprite.Sprite):
    """Storm Titan boss.

    Gameplay loop:
    - Waits off-screen until its spawn timer hits 0.
    - While active: targets a planted slot, warns briefly, then strikes lightning.
    - Any player cloud can block the strike by covering the target x-position.
      If blocked, the boss takes damage.
    - If unblocked, the plant is killed.
    - When defeated, the boss retreats after a short timer and drops a reward.
    """

    STATE_WAITING = "waiting"
    STATE_ACTIVE = "active"
    STATE_RETREATING = "retreating"

    def __init__(
        self,
        config: StormTitanConfig | None = None,
        *,
        rng: random.Random | None = None,
    ):
        super().__init__()
        self.config = config or StormTitanConfig()
        self._rng = rng or random.Random()

        self.image = self._load_image_or_fallback()
        self.rect = self.image.get_rect()

        field_w = SCREEN_W - UI_PANEL_W
        self.rect.centerx = field_w // 2
        self.rect.top = self.config.y
        self._x = float(self.rect.centerx)
        self._target_x: float | None = None

        self._state = self.STATE_WAITING
        self._hp = int(self.config.max_hp)

        self._spawn_remaining = float(self.config.spawn_every_seconds)
        self._cooldown_remaining = 0.0
        self._warning_remaining = 0.0
        self._retreat_remaining = 0.0

        self._target_slot_index: int | None = None

        self._bolt_flash_remaining = 0.0
        self._bolt_points: list[tuple[int, int]] | None = None

        self._pending_reward = 0

    # ── status ──────────────────────────────────────────────────────────────
    @property
    def state(self) -> str:
        return self._state

    @property
    def hp(self) -> int:
        return self._hp

    @property
    def max_hp(self) -> int:
        return self.config.max_hp

    @property
    def visible(self) -> bool:
        return self._state in {self.STATE_ACTIVE, self.STATE_RETREATING}

    @property
    def seconds_until_spawn(self) -> float:
        return max(0.0, self._spawn_remaining) if self._state == self.STATE_WAITING else 0.0

    @property
    def seconds_until_leave(self) -> float:
        return max(0.0, self._retreat_remaining) if self._state == self.STATE_RETREATING else 0.0

    # ── battle logic ─────────────────────────────────────────────────────────
    def update_battle(self, dt: float, *, slots: Sequence[object], clouds: Iterable[object]) -> None:
        if dt <= 0.0:
            return

        if self._state == self.STATE_WAITING:
            self._spawn_remaining -= dt
            if self._spawn_remaining <= 0.0:
                self._begin_fight()
            return

        if self._state == self.STATE_RETREATING:
            self._retreat_remaining -= dt
            if self._retreat_remaining <= 0.0:
                self._reset_to_waiting()
            return

        # active
        self._bolt_flash_remaining = max(0.0, self._bolt_flash_remaining - dt)
        moved_this_frame = False

        # If we have a target, keep our desired x synced and slide toward it.
        if self._target_slot_index is not None:
            slot = self._get_valid_target_slot(slots)
            if slot is None:
                self._target_slot_index = None
                self._target_x = None
                self._warning_remaining = 0.0
            else:
                rect = getattr(slot, "rect", None)
                if isinstance(rect, pygame.Rect):
                    self._target_x = float(rect.centerx)
                    self._smooth_move_x(dt)
                    moved_this_frame = True

        if self._warning_remaining > 0.0:
            self._warning_remaining -= dt
            if self._warning_remaining <= 0.0:
                # Snap the boss above the strike for a clean-looking hit.
                self._snap_to_target_x()
                self._resolve_strike(slots, clouds)
            return

        self._cooldown_remaining -= dt
        if self._cooldown_remaining > 0.0:
            return

        # Acquire a target if needed.
        if self._target_slot_index is None:
            self._choose_target(slots)
            if self._target_slot_index is None:
                # No plants to target; try again soon.
                self._cooldown_remaining = 1.0
                return

            slot = self._get_valid_target_slot(slots)
            rect = getattr(slot, "rect", None) if slot is not None else None
            if not isinstance(rect, pygame.Rect):
                self._target_slot_index = None
                self._cooldown_remaining = 1.0
                return
            self._target_x = float(rect.centerx)

        # Move toward our target, then start the warning once aligned.
        if self._target_x is not None:
            if not moved_this_frame:
                self._smooth_move_x(dt)
            if abs(self._x - self._target_x) <= float(self.config.align_epsilon_px):
                self._warning_remaining = float(self.config.strike_warning_seconds)

    def tick_spawn_timer(self, dt: float) -> None:
        """Advance spawn countdown while waiting, without spawning.

        Used by the game loop to keep other bosses' schedules moving while one
        boss fight is currently active.
        """
        if dt <= 0.0:
            return
        if self._state != self.STATE_WAITING:
            return
        self._spawn_remaining = max(0.0, self._spawn_remaining - dt)

    def pop_reward(self) -> tuple[str, int] | None:
        if self._pending_reward <= 0:
            return None
        count = self._pending_reward
        self._pending_reward = 0
        return (self.config.reward_item_name, count)

    def force_spawn_now(self) -> None:
        """Cheat/debug helper: force the boss to appear immediately."""
        if self._state == self.STATE_ACTIVE:
            return
        self._spawn_remaining = 0.0
        self._retreat_remaining = 0.0
        self._begin_fight()

    def despawn_now(self) -> None:
        """Cheat/debug helper: remove the boss immediately."""
        self._reset_to_waiting()

    # ── drawing ─────────────────────────────────────────────────────────────
    def draw_body(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return

        if self._state == self.STATE_RETREATING:
            tmp = self.image.copy()
            tmp.set_alpha(150)
            surface.blit(tmp, self.rect)
        else:
            surface.blit(self.image, self.rect)

    def draw_bolt(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        if self._bolt_flash_remaining <= 0.0 or not self._bolt_points:
            return

        pygame.draw.lines(surface, self.config.bolt_shadow_color, False, self._bolt_points, 6)
        pygame.draw.lines(surface, self.config.bolt_color, False, self._bolt_points, 3)

    def draw_warning(self, surface: pygame.Surface, *, slots: Sequence[object]) -> None:
        if not self.visible:
            return
        if self._state != self.STATE_ACTIVE:
            return
        if self._warning_remaining <= 0.0:
            return
        if self._target_slot_index is None:
            return
        if self._target_slot_index < 0 or self._target_slot_index >= len(slots):
            return

        slot = slots[self._target_slot_index]
        rect = getattr(slot, "rect", None)
        if not isinstance(rect, pygame.Rect):
            return

        pygame.draw.rect(surface, self.config.warning_color, rect.inflate(6, 6), 3, border_radius=6)

    # ── internals ───────────────────────────────────────────────────────────
    def _begin_fight(self) -> None:
        self._state = self.STATE_ACTIVE
        self._hp = int(self.config.max_hp)
        self._cooldown_remaining = 0.5
        self._warning_remaining = 0.0
        self._target_slot_index = None
        self._target_x = None
        self._bolt_flash_remaining = 0.0
        self._bolt_points = None

    def _begin_retreat(self) -> None:
        self._state = self.STATE_RETREATING
        self._retreat_remaining = float(self.config.retreat_seconds)
        self._cooldown_remaining = 0.0
        self._warning_remaining = 0.0
        self._target_slot_index = None
        self._target_x = None
        if self.config.reward_item_count > 0:
            self._pending_reward += int(self.config.reward_item_count)

    def _reset_to_waiting(self) -> None:
        self._state = self.STATE_WAITING
        self._spawn_remaining = float(self.config.spawn_every_seconds)
        self._cooldown_remaining = 0.0
        self._warning_remaining = 0.0
        self._retreat_remaining = 0.0
        self._target_slot_index = None
        self._target_x = None
        self._bolt_flash_remaining = 0.0
        self._bolt_points = None

    def _choose_target(self, slots: Sequence[object]) -> None:
        candidates: list[int] = []
        for idx, slot in enumerate(slots):
            if getattr(slot, "seed", None) is None:
                continue
            if getattr(slot, "dead", False):
                continue
            candidates.append(idx)

        if not candidates:
            self._target_slot_index = None
            return

        self._target_slot_index = self._rng.choice(candidates)

    def _get_valid_target_slot(self, slots: Sequence[object]):
        if self._target_slot_index is None:
            return None
        if self._target_slot_index < 0 or self._target_slot_index >= len(slots):
            return None
        slot = slots[self._target_slot_index]
        if getattr(slot, "seed", None) is None:
            return None
        if getattr(slot, "dead", False):
            return None
        rect = getattr(slot, "rect", None)
        if not isinstance(rect, pygame.Rect):
            return None
        return slot

    def _smooth_move_x(self, dt: float) -> None:
        if self._target_x is None:
            return

        # Exponential smoothing. Rate is in 1/seconds.
        rate = max(0.0, float(self.config.move_lerp_rate))
        if rate <= 0.0:
            self._x = float(self._target_x)
        else:
            alpha = 1.0 - math.exp(-rate * dt)
            self._x = (1.0 - alpha) * self._x + alpha * float(self._target_x)

        self.rect.centerx = int(round(self._x))

    def _snap_to_target_x(self) -> None:
        if self._target_x is None:
            return
        self._x = float(self._target_x)
        self.rect.centerx = int(round(self._x))

    def _resolve_strike(self, slots: Sequence[object], clouds: Iterable[object]) -> None:
        if self._target_slot_index is None:
            self._cooldown_remaining = float(self.config.strike_cooldown_seconds)
            return

        if self._target_slot_index < 0 or self._target_slot_index >= len(slots):
            self._target_slot_index = None
            self._cooldown_remaining = float(self.config.strike_cooldown_seconds)
            return

        target_index = self._target_slot_index
        slot = slots[target_index]
        slot_rect = getattr(slot, "rect", None)
        if not isinstance(slot_rect, pygame.Rect):
            self._target_slot_index = None
            self._cooldown_remaining = float(self.config.strike_cooldown_seconds)
            return

        x = int(slot_rect.centerx)
        start_y = int(self.rect.bottom)

        blocking_cloud = self._blocking_cloud_for_x(x, clouds)
        bolt_points: list[tuple[int, int]]
        if blocking_cloud is not None:
            hit_y = max(int(blocking_cloud.rect.top), start_y)
            down = self._make_bolt(x, start_y, hit_y)
            up = self._make_bolt(x, hit_y, int(self.rect.centery))
            bolt_points = down + up[1:]
            self._bolt_flash_remaining = 0.32
        else:
            hit_y = int(slot_rect.top)
            bolt_points = self._make_bolt(x, start_y, hit_y)
            self._bolt_flash_remaining = 0.25

        self._bolt_points = bolt_points

        if blocking_cloud is not None:
            # Check for a "perfect block" — cloud started blocking shortly before strike.
            is_perfect = False
            try:
                last = getattr(blocking_cloud, "_last_rain_toggled_at", None)
                if last is not None:
                    now = pygame.time.get_ticks() / 1000.0
                    if now - float(last) <= float(PERFECT_BLOCK_WINDOW_SECONDS):
                        is_perfect = True
            except Exception:
                is_perfect = False
            damage = 1 + int(PERFECT_BLOCK_BONUS_DAMAGE) if is_perfect else 1
            self._hp = max(0, self._hp - int(damage))
            # expose perfect-block timing for HUD feedback
            try:
                if is_perfect:
                    self._last_perfect_at = pygame.time.get_ticks() / 1000.0
            except Exception:
                pass
            if self._hp <= 0:
                self._begin_retreat()
        else:
            if self.config.lightning_kills_plant:
                radius = max(0, int(getattr(self.config, "aoe_radius_slots", 0)))
                for idx in range(target_index - radius, target_index + radius + 1):
                    if idx < 0 or idx >= len(slots):
                        continue
                    self._kill_slot(slots[idx])

        self._target_slot_index = None
        self._target_x = None
        self._cooldown_remaining = float(self.config.strike_cooldown_seconds)

    @staticmethod
    def _kill_slot(slot: object) -> None:
        if getattr(slot, "seed", None) is None:
            return
        if getattr(slot, "dead", False):
            return
        strike_fn = getattr(slot, "strike_lightning", None)
        if callable(strike_fn):
            strike_fn()
            return
        # Fallback for older PlantSlot shapes
        try:
            slot.dead = True
        except Exception:
            pass

    @staticmethod
    def _blocking_cloud_for_x(x: int, clouds: Iterable[object]):
        blockers: list[object] = []
        for cloud in clouds:
            rect = getattr(cloud, "rect", None)
            if not isinstance(rect, pygame.Rect):
                continue
            if rect.left <= x <= rect.right:
                blockers.append(cloud)

        if not blockers:
            return None

        # Highest cloud blocks first.
        return min(blockers, key=lambda c: c.rect.top)

    def _make_bolt(self, x: int, start_y: int, end_y: int) -> list[tuple[int, int]]:
        segments = 7
        points: list[tuple[int, int]] = [(x, start_y)]
        dy = end_y - start_y
        sign = 1 if dy >= 0 else -1
        height = max(1, abs(dy))
        for i in range(1, segments):
            t = i / segments
            y = start_y + sign * int(height * t)
            jitter = int(14 * (1.0 - t))
            points.append((x + self._rng.randint(-jitter, jitter), y))
        points.append((x, end_y))
        return points

    # ── visuals ─────────────────────────────────────────────────────────────
    def _load_image_or_fallback(self) -> pygame.Surface:
        img_path = os.path.join(PROPS_DIR, self.config.image_filename)
        if os.path.exists(img_path):
            try:
                raw = pygame.image.load(img_path)
                try:
                    raw = raw.convert_alpha()
                except pygame.error:
                    # convert_alpha may fail if display isn't initialized.
                    pass
                return pygame.transform.smoothscale(raw, (self.config.width, self.config.height))
            except Exception:
                pass
        return self._draw_fallback_surface(self.config.width, self.config.height)

    @staticmethod
    def _draw_fallback_surface(w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Cloud body
        base = (120, 125, 140, 240)
        pygame.draw.ellipse(surf, base, pygame.Rect(10, h // 2 - 8, w - 20, h // 2 + 12))
        pygame.draw.ellipse(surf, base, pygame.Rect(10, 18, int(w * 0.38), int(h * 0.62)))
        pygame.draw.ellipse(surf, base, pygame.Rect(int(w * 0.28), 0, int(w * 0.44), int(h * 0.68)))
        pygame.draw.ellipse(surf, base, pygame.Rect(int(w * 0.62), 16, int(w * 0.32), int(h * 0.58)))

        # Angry face
        eye = (25, 25, 30)
        left_eye = pygame.Rect(int(w * 0.33), int(h * 0.46), 18, 10)
        right_eye = pygame.Rect(int(w * 0.58), int(h * 0.46), 18, 10)
        pygame.draw.ellipse(surf, eye, left_eye)
        pygame.draw.ellipse(surf, eye, right_eye)

        pygame.draw.line(surf, eye, (left_eye.left - 2, left_eye.top - 6), (left_eye.right + 4, left_eye.top - 2), 3)
        pygame.draw.line(surf, eye, (right_eye.left - 4, right_eye.top - 2), (right_eye.right + 2, right_eye.top - 6), 3)

        pygame.draw.arc(
            surf,
            eye,
            pygame.Rect(int(w * 0.40), int(h * 0.56), int(w * 0.22), int(h * 0.18)),
            3.4,
            6.0,
            3,
        )

        return surf
