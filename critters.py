from __future__ import annotations

import os
import random
import math
from dataclasses import dataclass

import pygame

from settings import (
    SCREEN_W,
    UI_PANEL_W,
    CRITTER_SPAWN_CHECK_SECONDS,
    SQUIRREL_SPAWN_CHANCE,
    SQUIRREL_SPEED_PX_PER_SEC,
    SQUIRREL_EAT_SECONDS,
    SQUIRREL_IMAGE_FILENAME,
    SNAKE_SPAWN_CHANCE,
    SNAKE_SPEED_PX_PER_SEC,
    SNAKE_EAT_SECONDS,
    SNAKE_IMAGE_FILENAME,
    CRITTER_SCARECROW_AVOID_RADIUS_SLOTS,
)
from settings import (
    CHIPMUNK_DROP_ITEM_NAME,
    CHIPMUNK_DROP_CHANCE,
    CHIPMUNK_DROP_COUNT,
    SNAKE_DROP_ITEM_NAME,
    SNAKE_DROP_CHANCE,
    SNAKE_DROP_COUNT,
)

PROPS_DIR = os.path.join(os.path.dirname(__file__), "props")


@dataclass(frozen=True)
class CritterConfig:
    name: str
    width: int
    height: int
    speed_px_per_sec: float
    eat_seconds: float
    spawn_chance: float
    spawn_check_seconds: float = CRITTER_SPAWN_CHECK_SECONDS
    image_filename: str | None = None
    color: tuple[int, int, int] = (200, 200, 200)


class PlantThief:
    """A critter that spawns from a side and tries to steal plants.

    Rules:
    - Spawns from either left or right edge.
    - Targets a random planted slot.
    - When it reaches the target, it eats for N seconds, then clears the slot.
    - Repeats until no plants remain, then flees to the closest side and despawns.
    - Clicking the critter scares it into fleeing immediately.
    """

    STATE_INACTIVE = "inactive"
    STATE_MOVING = "moving"
    STATE_EATING = "eating"
    STATE_FLEEING = "fleeing"

    def __init__(self, config: CritterConfig, *, rng: random.Random | None = None):
        self.config = config
        self._rng = rng or random.Random()

        self.image = self._load_image_or_fallback()
        self.rect = self.image.get_rect()

        self._state = self.STATE_INACTIVE
        self._spawn_accum = 0.0

        self._x = 0.0
        self._spawn_side: str | None = None  # "left" or "right"
        self._direction = 1

        self._target_slot_index: int | None = None
        self._target_x: float | None = None
        self._eating_remaining = 0.0

        self._flee_x: float | None = None

        # If the critter generated a drop item (name, count), store here
        self._last_drop: tuple[str, int] | None = None

    # ── public ────────────────────────────────────────────────────────────
    @property
    def active(self) -> bool:
        return self._state != self.STATE_INACTIVE

    def force_spawn(self, *, field_rect: pygame.Rect, ground_rect: pygame.Rect) -> None:
        if self.active:
            return
        self._spawn(field_rect=field_rect, ground_rect=ground_rect)

    def scare_away(self, *, field_rect: pygame.Rect) -> None:
        if not self.active:
            return
        self._begin_flee(field_rect=field_rect)
        # audio removed; placeholder for future sound effects

    def update(self, dt: float, *, slots: list[object], field_rect: pygame.Rect, ground_rect: pygame.Rect) -> None:
        if dt <= 0.0:
            return

        if self._state == self.STATE_INACTIVE:
            self._spawn_accum += dt
            while self._spawn_accum >= float(self.config.spawn_check_seconds):
                self._spawn_accum -= float(self.config.spawn_check_seconds)
                if self._rng.random() < float(self.config.spawn_chance):
                    self._spawn(field_rect=field_rect, ground_rect=ground_rect)
                    break
            return

        if self._state == self.STATE_EATING:
            # If the target disappears, retarget.
            if not self._target_is_valid(slots):
                self._choose_target(slots)
                if self._target_slot_index is None:
                    self._begin_flee(field_rect=field_rect)
                else:
                    self._state = self.STATE_MOVING
                return

            self._eating_remaining -= dt
            if self._eating_remaining <= 0.0:
                self._steal_target(slots)
                self._choose_target(slots)
                if self._target_slot_index is None:
                    self._begin_flee(field_rect=field_rect)
                else:
                    self._state = self.STATE_MOVING
            return

        if self._state == self.STATE_FLEEING:
            self._move_toward(self._flee_x, dt)
            # Despawn once fully off-screen.
            if self._spawn_side == "left" and self.rect.right < 0:
                self._deactivate()
            elif self._spawn_side == "right" and self.rect.left > field_rect.width:
                self._deactivate()
            return

        # moving
        if self._target_slot_index is None:
            self._choose_target(slots)
            if self._target_slot_index is None:
                self._begin_flee(field_rect=field_rect)
                return

        # Keep target x synced (plant could be removed/moved).
        if not self._target_is_valid(slots):
            self._target_slot_index = None
            self._target_x = None
            return

        slot = slots[self._target_slot_index]
        rect = getattr(slot, "rect", None)
        if isinstance(rect, pygame.Rect):
            self._target_x = float(rect.centerx)

        self._move_toward(self._target_x, dt)
        if self._target_x is not None and abs(self._x - self._target_x) <= 3.0:
            self._state = self.STATE_EATING
            self._eating_remaining = float(self.config.eat_seconds)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active:
            return
        surface.blit(self.image, self.rect)

    # ── internals ─────────────────────────────────────────────────────────
    def _spawn(self, *, field_rect: pygame.Rect, ground_rect: pygame.Rect) -> None:
        # spawn from either side
        side = self._rng.choice(["left", "right"]) if hasattr(self._rng, "choice") else ("left" if self._rng.random() < 0.5 else "right")
        self._spawn_side = side

        if side == "left":
            self._x = -float(self.rect.width) - 4.0
            self._direction = 1
        else:
            self._x = float(field_rect.width) + 4.0
            self._direction = -1

        self.rect.bottom = ground_rect.bottom - 2
        self.rect.x = int(round(self._x))

        self._flip_if_needed()

        self._target_slot_index = None
        self._target_x = None
        self._eating_remaining = 0.0
        self._flee_x = None

        self._state = self.STATE_MOVING
        # audio removed; placeholder for future sound effects

    def _flip_if_needed(self) -> None:
        # crude flip based on direction so sprites face inward
        if self._direction < 0:
            self.image = pygame.transform.flip(self._load_image_or_fallback(), True, False)
        else:
            self.image = self._load_image_or_fallback()
        old_bottom = self.rect.bottom
        self.rect = self.image.get_rect()
        self.rect.bottom = old_bottom
        self.rect.x = int(round(self._x))

    def _scarecrow_protects(self, slots: list[object], idx: int) -> bool:
        """True if slot ``idx`` is within the scare radius of any scarecrow."""
        target = slots[idx]
        trect = getattr(target, "rect", None)
        if not isinstance(trect, pygame.Rect):
            return False
        radius = max(0, int(CRITTER_SCARECROW_AVOID_RADIUS_SLOTS))
        if radius <= 0:
            return getattr(target, "has_scarecrow", False)
        pitch = max(trect.width, trect.height) * 1.4
        reach = radius * pitch
        for slot in slots:
            if not getattr(slot, "has_scarecrow", False):
                continue
            srect = getattr(slot, "rect", None)
            if not isinstance(srect, pygame.Rect):
                continue
            if abs(srect.centerx - trect.centerx) <= reach and abs(srect.centery - trect.centery) <= reach:
                return True
        return False

    def _choose_target(self, slots: list[object]) -> None:
        candidates: list[int] = []
        for idx, slot in enumerate(slots):
            if getattr(slot, "seed", None) is None:
                continue
            if getattr(slot, "dead", False):
                continue
            if self._scarecrow_protects(slots, idx):
                continue
            candidates.append(idx)
        if not candidates:
            self._target_slot_index = None
            self._target_x = None
            return
        self._target_slot_index = self._rng.choice(candidates)
        rect = getattr(slots[self._target_slot_index], "rect", None)
        self._target_x = float(rect.centerx) if isinstance(rect, pygame.Rect) else None

    def _target_is_valid(self, slots: list[object]) -> bool:
        if self._target_slot_index is None:
            return False
        if self._target_slot_index < 0 or self._target_slot_index >= len(slots):
            return False
        slot = slots[self._target_slot_index]
        if getattr(slot, "seed", None) is None:
            return False
        if getattr(slot, "dead", False):
            return False
        if self._scarecrow_protects(slots, self._target_slot_index):
            return False
        rect = getattr(slot, "rect", None)
        return isinstance(rect, pygame.Rect)

    def _steal_target(self, slots: list[object]) -> None:
        if not self._target_is_valid(slots):
            return
        slot = slots[self._target_slot_index]
        clear_fn = getattr(slot, "clear", None)
        if callable(clear_fn):
            clear_fn()
            # roll for a possible drop when stealing a plant
            self._last_drop = None
            try:
                if isinstance(self, ChipmunkThief):
                    if self._rng.random() < float(CHIPMUNK_DROP_CHANCE):
                        self._last_drop = (str(CHIPMUNK_DROP_ITEM_NAME), int(CHIPMUNK_DROP_COUNT))
                elif isinstance(self, SnakeThief):
                    if self._rng.random() < float(SNAKE_DROP_CHANCE):
                        self._last_drop = (str(SNAKE_DROP_ITEM_NAME), int(SNAKE_DROP_COUNT))
            except Exception:
                self._last_drop = None
            return
        # fallback: clear the most important fields
        try:
            slot.seed = None
        except Exception:
            pass

    def _begin_flee(self, *, field_rect: pygame.Rect) -> None:
        # run to closest edge
        field_w = field_rect.width
        left_dist = abs(self.rect.centerx - 0)
        right_dist = abs(self.rect.centerx - field_w)
        if left_dist <= right_dist:
            self._spawn_side = "left"
            self._flee_x = -float(self.rect.width) - 8.0
            self._direction = -1
        else:
            self._spawn_side = "right"
            self._flee_x = float(field_w) + 8.0
            self._direction = 1

        self._flip_if_needed()
        self._target_slot_index = None
        self._target_x = None
        self._eating_remaining = 0.0
        self._state = self.STATE_FLEEING

    def _move_toward(self, target_x: float | None, dt: float) -> None:
        if target_x is None:
            return
        speed = max(1.0, float(self.config.speed_px_per_sec))
        dx = target_x - self._x
        if abs(dx) <= 0.01:
            return
        step = speed * dt
        if abs(dx) <= step:
            self._x = target_x
        else:
            self._x += step if dx > 0 else -step
        self.rect.x = int(round(self._x))

    def _deactivate(self) -> None:
        self._state = self.STATE_INACTIVE
        self._spawn_accum = 0.0
        self._spawn_side = None
        self._target_slot_index = None
        self._target_x = None
        self._eating_remaining = 0.0
        self._flee_x = None

    def _load_image_or_fallback(self) -> pygame.Surface:
        if self.config.image_filename:
            path = os.path.join(PROPS_DIR, self.config.image_filename)
            if os.path.exists(path):
                try:
                    raw = pygame.image.load(path)
                    try:
                        raw = raw.convert_alpha()
                    except pygame.error:
                        pass
                    return pygame.transform.smoothscale(raw, (self.config.width, self.config.height))
                except Exception:
                    pass
        return self._draw_fallback_surface(self.config.width, self.config.height)

    def _draw_fallback_surface(self, w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        body = (*self.config.color[:3], 235)
        pygame.draw.ellipse(surf, body, pygame.Rect(0, 0, w, h))
        pygame.draw.circle(surf, (0, 0, 0), (int(w * 0.35), int(h * 0.45)), 2)
        pygame.draw.circle(surf, (0, 0, 0), (int(w * 0.65), int(h * 0.45)), 2)
        return surf


class ChipmunkThief(PlantThief):
    def _draw_fallback_surface(self, w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Colors
        fur = (165, 115, 70, 235)
        fur_dark = (125, 85, 55, 220)
        belly = (215, 175, 125, 220)
        outline = (35, 30, 25, 210)

        # Big tail (behind)
        tail_rect = pygame.Rect(0, int(h * 0.05), int(w * 0.44), int(h * 0.92))
        pygame.draw.ellipse(surf, fur_dark, tail_rect)
        pygame.draw.ellipse(surf, fur, tail_rect.inflate(-int(w * 0.08), -int(h * 0.18)))
        pygame.draw.arc(
            surf,
            (235, 220, 200, 150),
            tail_rect.inflate(-int(w * 0.14), -int(h * 0.26)),
            0.2,
            2.7,
            3,
        )

        # Body
        body_rect = pygame.Rect(int(w * 0.18), int(h * 0.36), int(w * 0.54), int(h * 0.46))
        pygame.draw.ellipse(surf, fur, body_rect)
        belly_rect = pygame.Rect(int(w * 0.34), int(h * 0.50), int(w * 0.30), int(h * 0.28))
        pygame.draw.ellipse(surf, belly, belly_rect)

        # Chipmunk stripes
        for sx in (0.42, 0.50, 0.58):
            stripe = pygame.Rect(int(w * sx), int(h * 0.40), int(w * 0.03), int(h * 0.42))
            pygame.draw.rect(surf, fur_dark, stripe, border_radius=4)

        # Head
        head_center = (int(w * 0.78), int(h * 0.50))
        head_r = max(6, int(h * 0.22))
        pygame.draw.circle(surf, fur, head_center, head_r)

        # Ear
        ear_center = (int(w * 0.80), int(h * 0.32))
        pygame.draw.circle(surf, fur_dark, ear_center, max(3, int(h * 0.10)))

        # Eye + nose
        pygame.draw.circle(surf, (10, 10, 10), (int(w * 0.81), int(h * 0.47)), 2)
        pygame.draw.circle(surf, (20, 15, 15), (int(w * 0.90), int(h * 0.55)), 2)

        # Tiny mouth line
        pygame.draw.line(
            surf,
            outline,
            (int(w * 0.88), int(h * 0.58)),
            (int(w * 0.86), int(h * 0.60)),
            2,
        )

        # Feet
        foot = (90, 60, 40, 220)
        pygame.draw.ellipse(surf, foot, pygame.Rect(int(w * 0.35), int(h * 0.80), int(w * 0.10), int(h * 0.12)))
        pygame.draw.ellipse(surf, foot, pygame.Rect(int(w * 0.52), int(h * 0.80), int(w * 0.10), int(h * 0.12)))

        return surf


class SnakeThief(PlantThief):
    def _draw_fallback_surface(self, w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        green = (70, 170, 90, 235)
        green_dark = (45, 120, 65, 225)
        highlight = (130, 225, 150, 160)

        margin_x = max(6, int(w * 0.08))
        amp = max(3, int(h * 0.24))
        center_y = int(h * 0.55)

        points: list[tuple[int, int]] = []
        segments = 12
        for i in range(segments):
            t = i / (segments - 1)
            x = int(margin_x + t * (w - margin_x * 2))
            y = int(center_y + math.sin(t * math.tau) * amp)
            points.append((x, y))

        # Body (S-like curve)
        pygame.draw.lines(surf, green_dark, False, points, 9)
        pygame.draw.lines(surf, green, False, points, 7)
        pygame.draw.lines(surf, highlight, False, points, 3)

        # Head
        hx, hy = points[-1]
        pygame.draw.circle(surf, green_dark, (hx + 1, hy), 7)
        pygame.draw.circle(surf, green, (hx, hy), 7)

        # Eye
        pygame.draw.circle(surf, (10, 10, 10), (hx + 2, hy - 2), 2)

        # Tongue (forked)
        tongue_color = (220, 60, 70)
        mouth_x = hx + 6
        mouth_y = hy + 2
        pygame.draw.line(surf, tongue_color, (mouth_x, mouth_y), (mouth_x + 8, mouth_y), 2)
        pygame.draw.line(surf, tongue_color, (mouth_x + 8, mouth_y), (mouth_x + 12, mouth_y - 3), 2)
        pygame.draw.line(surf, tongue_color, (mouth_x + 8, mouth_y), (mouth_x + 12, mouth_y + 3), 2)

        return surf


def make_squirrel(*, rng: random.Random | None = None) -> PlantThief:
    cfg = CritterConfig(
        name="Squirrel",
        width=56,
        height=28,
        speed_px_per_sec=SQUIRREL_SPEED_PX_PER_SEC,
        eat_seconds=SQUIRREL_EAT_SECONDS,
        spawn_chance=SQUIRREL_SPAWN_CHANCE,
        image_filename=SQUIRREL_IMAGE_FILENAME,
        color=(165, 115, 70),
    )
    return ChipmunkThief(cfg, rng=rng)


def make_snake(*, rng: random.Random | None = None) -> PlantThief:
    cfg = CritterConfig(
        name="Snake",
        width=70,
        height=18,
        speed_px_per_sec=SNAKE_SPEED_PX_PER_SEC,
        eat_seconds=SNAKE_EAT_SECONDS,
        spawn_chance=SNAKE_SPAWN_CHANCE,
        image_filename=SNAKE_IMAGE_FILENAME,
        color=(70, 170, 90),
    )
    return SnakeThief(cfg, rng=rng)
