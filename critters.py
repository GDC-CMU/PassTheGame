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
    BEE_SPAWN_CHANCE,
    BEE_MAX_ACTIVE,
    BEE_SERVICE_SECONDS,
    BEE_SPEED_PX_PER_SEC,
    BEE_ALTITUDE_PX,
    BEE_BLOOM_MIN_RATIO,
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

    # ── procedural animation tuning ───────────────────────────────────────
    # Offsets are in pixels; squash/stretch values are fractions of the base
    # size. These are intentionally small so the critters read as lively and
    # cute rather than jittery, and so the feet stay planted on the ground.
    # Speeds are angular (radians per second): period = 2*pi / speed, and the
    # hop-style terms use abs(sin) so a footfall lands twice per cycle.
    _WALK_BOB_SPEED = 11.0      # ~3.5 footfalls per second while walking
    _WALK_BOB_AMP = 2.0         # pixels the body rises at the top of a hop
    _WALK_SQUASH = 0.05         # widen/flatten by 5% at each footfall

    _EAT_CHOMP_SPEED = 18.0     # faster than walking, so it reads as munching
    _EAT_BOB_AMP = 1.5          # small vertical chomp
    _EAT_NIBBLE_SPEED = 18.0    # forward/back head jitter speed
    _EAT_NIBBLE_AMP = 2.0       # pixels the head pushes toward the crop
    _EAT_SQUASH = 0.07          # squash as it bites down

    _FLEE_BOB_SPEED = 16.0      # a frantic scurry, faster than walking
    _FLEE_BOB_AMP = 3.0         # higher hops than walking
    _FLEE_LEAN_PX = 3.0         # pixels leaned forward into the run
    _FLEE_STRETCH = 0.05        # horizontal stretch, like running fast
    _FLEE_SQUASH = 0.04         # footfall squash while fleeing

    def __init__(self, config: CritterConfig, *, rng: random.Random | None = None):
        self.config = config
        self._rng = rng or random.Random()

        self.image = self._load_image_or_fallback()
        self.rect = self.image.get_rect()

        self._state = self.STATE_INACTIVE
        self._spawn_accum = 0.0
        # Difficulty multiplier on the spawn chance (1.0 == base). The game raises
        # this as the year/difficulty climbs so thieves get more frequent over time.
        self._spawn_scale = 1.0

        # Phase accumulator that drives the procedural animation. It advances
        # with dt in update() and is reset on each spawn so motion is
        # deterministic from the moment a critter appears.
        self._anim_time = 0.0

        self._x = 0.0
        self._spawn_side: str | None = None  # "left" or "right"
        self._direction = 1

        self._target_slot_index: int | None = None
        self._target_x: float | None = None
        self._eating_remaining = 0.0

        self._flee_x: float | None = None

        # If the critter generated a drop item (name, count), store here
        self._last_drop: tuple[str, int] | None = None
        self._juice_events: list[dict] = []

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
        self._juice_events.append({"kind": "scare", "name": self.config.name, "pos": self.rect.center})
        self._begin_flee(field_rect=field_rect)

    def set_spawn_scale(self, scale: float) -> None:
        """Difficulty hook: multiplies this critter's spawn chance (1.0 == base)."""
        self._spawn_scale = max(0.0, float(scale))

    def pop_juice_events(self) -> list[dict]:
        events = self._juice_events
        self._juice_events = []
        return events

    def update(self, dt: float, *, slots: list[object], field_rect: pygame.Rect, ground_rect: pygame.Rect) -> None:
        if dt <= 0.0:
            return

        # Advance the animation clock for every active frame. While inactive
        # this is harmless and gets reset on the next spawn.
        self._anim_time += dt

        if self._state == self.STATE_INACTIVE:
            self._spawn_accum += dt
            while self._spawn_accum >= float(self.config.spawn_check_seconds):
                self._spawn_accum -= float(self.config.spawn_check_seconds)
                if self._rng.random() < float(self.config.spawn_chance) * self._spawn_scale:
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
        frame, topleft = self._animated_frame()
        surface.blit(frame, topleft)

    def _animation_offsets(self) -> tuple[float, float, float, float]:
        """Return ``(dx, dy, scale_x, scale_y)`` for the current frame.

        ``dx``/``dy`` shift the bottom-center anchor in pixels (``dy`` negative
        means up). ``scale_x``/``scale_y`` multiply the base size and are applied
        about the bottom-center so the feet stay planted. The scales are always
        positive, so the animation can never mirror the sprite, and there is no
        vertical flip anywhere in this method: the critter is always upright.

        The behavior state picks the motion: STATE_MOVING is the idle/walk bob,
        STATE_EATING is the fast nibble while a crop is being eaten, and
        STATE_FLEEING is the leaning scurry.
        """
        t = self._anim_time
        facing = 1.0 if self._direction >= 0 else -1.0

        if self._state == self.STATE_EATING:
            # Fast vertical chomp plus a forward/back head jitter toward the
            # crop, with a squash on the bite so it reads as munching.
            bite = 0.5 + 0.5 * math.sin(t * self._EAT_CHOMP_SPEED)
            dy = -self._EAT_BOB_AMP * bite
            dx = facing * self._EAT_NIBBLE_AMP * math.sin(t * self._EAT_NIBBLE_SPEED)
            sx = 1.0 + self._EAT_SQUASH * bite
            sy = 1.0 - self._EAT_SQUASH * bite
            return dx, dy, sx, sy

        if self._state == self.STATE_FLEEING:
            # Lean forward into the run with a faster, taller scurry and a
            # horizontal stretch, squashing on each footfall.
            hop = abs(math.sin(t * self._FLEE_BOB_SPEED))
            dy = -self._FLEE_BOB_AMP * hop
            dx = facing * self._FLEE_LEAN_PX
            sx = 1.0 + self._FLEE_STRETCH
            sy = 1.0 - self._FLEE_SQUASH * (1.0 - hop)
            return dx, dy, sx, sy

        if self._state == self.STATE_MOVING:
            # Gentle walk bob: a couple of pixels up at the top of each hop and
            # a slight squash at the footfall so it scurries instead of sliding.
            hop = abs(math.sin(t * self._WALK_BOB_SPEED))
            dy = -self._WALK_BOB_AMP * hop
            dx = 0.0
            sx = 1.0 + self._WALK_SQUASH * (1.0 - hop)
            sy = 1.0 - self._WALK_SQUASH * (1.0 - hop)
            return dx, dy, sx, sy

        return 0.0, 0.0, 1.0, 1.0

    def _animated_frame(self) -> tuple[pygame.Surface, tuple[int, int]]:
        """Derive the animated surface and its blit position from ``self.image``.

        The base image (already facing the right way via the horizontal flip in
        ``_flip_if_needed``) is never mutated; a fresh frame is computed each
        call from the current animation phase. Squash/stretch is anchored about
        the bottom-center so the feet stay on the ground line at ``rect.bottom``.
        """
        base = self.image
        dx, dy, scale_x, scale_y = self._animation_offsets()

        bw, bh = base.get_size()
        nw = max(1, int(round(bw * scale_x)))
        nh = max(1, int(round(bh * scale_y)))

        if (nw, nh) != (bw, bh):
            try:
                frame = pygame.transform.smoothscale(base, (nw, nh))
            except (pygame.error, ValueError):
                try:
                    frame = pygame.transform.scale(base, (nw, nh))
                except (pygame.error, ValueError):
                    frame = base
                    nw, nh = bw, bh
        else:
            frame = base

        anchor_x = self.rect.centerx
        anchor_bottom = self.rect.bottom
        left = int(round(anchor_x - nw / 2.0 + dx))
        top = int(round(anchor_bottom - nh + dy))
        return frame, (left, top)

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

        self._anim_time = 0.0

        self._state = self.STATE_MOVING
        self._juice_events.append({"kind": "spawn", "name": self.config.name, "pos": self.rect.midbottom})

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
        plant_cands: list[int] = []
        for idx, slot in enumerate(slots):
            if self._scarecrow_protects(slots, idx):
                continue
            if getattr(slot, "seed", None) is None or getattr(slot, "dead", False):
                continue
            plant_cands.append(idx)

        if plant_cands:
            self._target_slot_index = self._rng.choice(plant_cands)
        else:
            self._target_slot_index = None
            self._target_x = None
            return
        rect = getattr(slots[self._target_slot_index], "rect", None)
        self._target_x = float(rect.centerx) if isinstance(rect, pygame.Rect) else None

    def _target_is_valid(self, slots: list[object]) -> bool:
        if self._target_slot_index is None:
            return False
        if self._target_slot_index < 0 or self._target_slot_index >= len(slots):
            return False
        slot = slots[self._target_slot_index]
        rect = getattr(slot, "rect", None)
        if not isinstance(rect, pygame.Rect):
            return False
        if self._scarecrow_protects(slots, self._target_slot_index):
            return False
        if getattr(slot, "seed", None) is None:
            return False
        if getattr(slot, "dead", False):
            return False
        return True

    def _steal_target(self, slots: list[object]) -> None:
        if not self._target_is_valid(slots):
            return
        slot = slots[self._target_slot_index]
        rect = getattr(slot, "rect", None)
        pos = rect.center if isinstance(rect, pygame.Rect) else self.rect.center
        self._juice_events.append({
            "kind": "steal",
            "name": self.config.name,
            "slot_index": self._target_slot_index,
            "pos": pos,
        })
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


class Bee:
    """A beneficial day visitor that pollinates flowering crops.

    The bee is NOT a pest. It lives in its own list, is never click-scared, and
    only ever helps. While it hovers over a flowering (pollinatable) crop that
    is currently in its healthy band, the game grants that slot a small growth
    speed-up. Because the bonus is applied to the in-range growth term only, the
    bee rewards a crop you have already solved with the clouds and does nothing
    for one that is out of band, so it never relieves the core watering puzzle.

    States: INACTIVE -> FLY_IN -> SERVICE -> ROAM -> (SERVICE | LEAVE).
    """

    STATE_INACTIVE = "inactive"
    STATE_FLY_IN = "fly_in"
    STATE_SERVICE = "service"
    STATE_ROAM = "roam"
    STATE_LEAVE = "leave"

    def __init__(self, *, rng: random.Random | None = None):
        self._rng = rng or random.Random()
        self._state = self.STATE_INACTIVE
        self._spawn_accum = 0.0
        self._can_spawn = False
        self._anim_time = 0.0
        self._x = 0.0
        self._y = 0.0
        self._target_idx: int | None = None
        self._service_remaining = 0.0
        self._side = "left"
        self.rect = pygame.Rect(0, 0, 20, 14)

    # ── state queries ────────────────────────────────────────────────────
    @property
    def active(self) -> bool:
        return self._state != self.STATE_INACTIVE

    @property
    def serviced_slot_index(self) -> int | None:
        """The slot the bee is actively pollinating this frame, else None."""
        if self._state == self.STATE_SERVICE:
            return self._target_idx
        return None

    def set_can_spawn(self, ok: bool) -> None:
        self._can_spawn = bool(ok)

    def dismiss(self, *, field_rect: pygame.Rect) -> None:
        """Send an active bee home (e.g. when night falls or flowers run out)."""
        if self.active and self._state != self.STATE_LEAVE:
            self._begin_leave(field_rect=field_rect)

    # ── flower selection ─────────────────────────────────────────────────
    def _scarecrow_blocks(self, slots: list[object], idx: int) -> bool:
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
            if abs(srect.centerx - trect.centerx) <= reach:
                return True
        return False

    def _flower_candidates(self, slots: list[object], *, exclude: int | None = None) -> list[int]:
        out: list[int] = []
        for idx, slot in enumerate(slots):
            if idx == exclude:
                continue
            seed = getattr(slot, "seed", None)
            if seed is None or getattr(slot, "dead", False):
                continue
            if not getattr(seed, "pollinatable", False):
                continue
            if float(getattr(slot, "growth_ratio", 0.0)) < float(BEE_BLOOM_MIN_RATIO):
                continue
            if self._scarecrow_blocks(slots, idx):
                continue
            out.append(idx)
        return out

    def _target_is_valid(self, slots: list[object]) -> bool:
        idx = self._target_idx
        if idx is None or idx < 0 or idx >= len(slots):
            return False
        slot = slots[idx]
        seed = getattr(slot, "seed", None)
        if seed is None or getattr(slot, "dead", False):
            return False
        if not getattr(seed, "pollinatable", False):
            return False
        if self._scarecrow_blocks(slots, idx):
            return False
        return True

    def _slot_hover_point(self, slots: list[object], idx: int) -> tuple[float, float]:
        rect = slots[idx].rect
        return float(rect.centerx), float(max(0, rect.top - int(BEE_ALTITUDE_PX)))

    # ── lifecycle ────────────────────────────────────────────────────────
    def _spawn(self, slots: list[object], field_rect: pygame.Rect) -> None:
        cands = self._flower_candidates(slots)
        if not cands:
            return
        self._target_idx = self._rng.choice(cands)
        tx, ty = self._slot_hover_point(slots, self._target_idx)
        self._side = "left" if tx >= field_rect.width / 2 else "right"
        self._x = -24.0 if self._side == "left" else float(field_rect.width) + 24.0
        self._y = ty
        self._anim_time = 0.0
        self._state = self.STATE_FLY_IN

    def _begin_leave(self, *, field_rect: pygame.Rect) -> None:
        self._target_idx = None
        self._side = "left" if self._x <= field_rect.width / 2 else "right"
        self._state = self.STATE_LEAVE

    def _deactivate(self) -> None:
        self._state = self.STATE_INACTIVE
        self._target_idx = None
        self._spawn_accum = 0.0

    def _move_toward(self, tx: float, ty: float, dt: float) -> bool:
        """Move toward a point; return True once essentially arrived."""
        speed = max(1.0, float(BEE_SPEED_PX_PER_SEC))
        dx, dy = tx - self._x, ty - self._y
        dist = math.hypot(dx, dy)
        step = speed * dt
        if dist <= max(2.0, step):
            self._x, self._y = tx, ty
            return True
        self._x += step * dx / dist
        self._y += step * dy / dist
        return False

    def update(self, dt: float, *, slots: list[object], field_rect: pygame.Rect, ground_rect: pygame.Rect) -> None:
        if dt <= 0.0:
            return
        self._anim_time += dt

        if self._state == self.STATE_INACTIVE:
            if not self._can_spawn:
                self._spawn_accum = 0.0
                return
            self._spawn_accum += dt
            while self._spawn_accum >= float(CRITTER_SPAWN_CHECK_SECONDS):
                self._spawn_accum -= float(CRITTER_SPAWN_CHECK_SECONDS)
                if self._rng.random() < float(BEE_SPAWN_CHANCE):
                    self._spawn(slots, field_rect)
                    break
            self._sync_rect()
            return

        if self._state == self.STATE_LEAVE:
            edge = -40.0 if self._side == "left" else float(field_rect.width) + 40.0
            self._move_toward(edge, self._y - 30.0, dt)
            if self._x < -32.0 or self._x > field_rect.width + 32.0:
                self._deactivate()
            self._sync_rect()
            return

        if not self._target_is_valid(slots):
            # flower harvested, died, or got a scarecrow; find another or leave.
            cands = self._flower_candidates(slots, exclude=self._target_idx)
            if cands:
                self._target_idx = self._rng.choice(cands)
                self._state = self.STATE_ROAM
            else:
                self._begin_leave(field_rect=field_rect)
                self._sync_rect()
                return

        tx, ty = self._slot_hover_point(slots, self._target_idx)

        if self._state in (self.STATE_FLY_IN, self.STATE_ROAM):
            if self._move_toward(tx, ty, dt):
                self._state = self.STATE_SERVICE
                self._service_remaining = float(BEE_SERVICE_SECONDS)
        elif self._state == self.STATE_SERVICE:
            # gentle hover bob centered on the flower
            self._x = tx
            self._y = ty + math.sin(self._anim_time * 7.0) * 3.0
            self._service_remaining -= dt
            if self._service_remaining <= 0.0:
                cands = self._flower_candidates(slots, exclude=self._target_idx)
                if cands:
                    self._target_idx = self._rng.choice(cands)
                    self._state = self.STATE_ROAM
                else:
                    self._begin_leave(field_rect=field_rect)

        self._sync_rect()

    def _sync_rect(self) -> None:
        self.rect.center = (int(round(self._x)), int(round(self._y)))

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active:
            return
        w, h = 20, 14
        bee = pygame.Surface((w, h + 6), pygame.SRCALPHA)
        cx, cy = w // 2, (h + 6) // 2
        # flutter: wings alternate height quickly so it reads as buzzing
        flutter = abs(math.sin(self._anim_time * 38.0))
        wing_h = int(5 + flutter * 4)
        wing_col = (235, 245, 255, 150)
        pygame.draw.ellipse(bee, wing_col, pygame.Rect(cx - 9, cy - wing_h, 8, wing_h * 2))
        pygame.draw.ellipse(bee, wing_col, pygame.Rect(cx + 1, cy - wing_h, 8, wing_h * 2))
        # fuzzy body
        body = pygame.Rect(cx - 8, cy - 5, 16, 10)
        pygame.draw.ellipse(bee, (40, 34, 20, 235), body.inflate(2, 2))
        pygame.draw.ellipse(bee, (245, 205, 60, 245), body)
        # stripes
        for sx in (-3, 1, 5):
            pygame.draw.rect(bee, (30, 26, 16, 235), pygame.Rect(cx + sx, cy - 5, 2, 10))
        # eye
        pygame.draw.circle(bee, (20, 18, 12), (cx + 7, cy - 1), 1)
        surface.blit(bee, (int(self._x) - cx, int(self._y) - cy))


def make_bee(*, rng: random.Random | None = None) -> Bee:
    return Bee(rng=rng)
