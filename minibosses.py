"""Mini-boss threats for the farming-defense field.

Mini-bosses are the small, frequent gap-fillers that keep mid-session tension up
between the big titans. They reuse the critter spawn/scare scaffolding (an active
flag, a force_spawn entry point, a per-frame update, a code-drawn fallback, and a
left-click counter) but trade the walk/eat state machine for a single
telegraph-then-resolve beat.

Shared design rules (from the design doc):
  - No health bar; each resolves in one ~2-4 second interaction.
  - Threatens ONE column (or one cloud) at a time; never demands both clouds.
  - Leaves at most a brief, recoverable debuff: a short salt timer, a sun
    overheat, or a brief growth freeze. None of them set ``slot.dead`` directly.

The five mini-bosses:
  - BurrowMole: surfaces under a planted slot (ignores the side-walk and the
    Scarecrow), shows a shrinking dust ring, and salts that slot briefly if it is
    not clicked. Counter: click it. Teaches reaction under cloud-micro pressure.
  - LocustPair: two locusts fly in from both edges; each clears one crop unless
    clicked. Teaches divided attention.
  - GlareMote: a spark of trapped sunlight settles on a sun-lover and pushes its
    sun toward overheat unless the column is shaded by a cloud. Teaches shading
    one column. Fizzles where no sun-lover exists.
  - ChillWisp: a pale sheen brushes a band of adjacent columns; any column not
    covered by a cloud when it resolves has its growth stalled briefly. A gentle
    Frost primer. Teaches covering a band.
  - TangleVine: a root coils toward one cloud and pins it briefly unless clicked
    three times. Teaches surviving with less cloud flexibility.

A ``MiniBossDirector`` ticks the active mini-bosses, rolls spawns on a capped
cadence, and routes left clicks to the click-counterable ones.
"""

from __future__ import annotations

import math
import random

import pygame

from settings import (
    MINIBOSS_SPAWN_CHECK_SECONDS,
    MINIBOSS_SPAWN_CHANCE,
    MINIBOSS_SPAWN_COOLDOWN_SECONDS,
    MINIBOSS_MAX_ACTIVE,
    MINIBOSS_SUN_LOVER_SUN_MIN,
    MINIBOSS_RESOLVE_FLASH_SECONDS,
    MINIBOSS_MOLE_TELEGRAPH_SECONDS,
    MINIBOSS_MOLE_SALT_SECONDS,
    MINIBOSS_MOLE_SIZE,
    MINIBOSS_LOCUST_TELEGRAPH_SECONDS,
    MINIBOSS_LOCUST_SPEED_PX_PER_SEC,
    MINIBOSS_LOCUST_MIN_PLANTED,
    MINIBOSS_LOCUST_SIZE,
    MINIBOSS_GLARE_TELEGRAPH_SECONDS,
    MINIBOSS_GLARE_OVERHEAT_SUN,
    MINIBOSS_GLARE_SCORCH_SECONDS,
    MINIBOSS_GLARE_SCORCH_WATER_LOSS,
    MINIBOSS_WISP_TELEGRAPH_SECONDS,
    MINIBOSS_WISP_FREEZE_SECONDS,
    MINIBOSS_WISP_BAND_MIN,
    MINIBOSS_WISP_BAND_MAX,
)

TANGLE_VINE_TELEGRAPH_SECONDS = 2.35
TANGLE_VINE_PIN_SECONDS = 3.5
TANGLE_VINE_REQUIRED_CLICKS = 3
TANGLE_VINE_ROOT_SIZE = (58, 46)


# ── small shared helpers ──────────────────────────────────────────────────────
def _cloud_covers_x(clouds, x) -> bool:
    """True if any cloud spans the column at screen-x ``x``.

    This is the exact check the field uses for shade/rain coverage:
    ``cloud.rect.left <= x <= cloud.rect.right``.
    """
    for cloud in clouds or ():
        rect = getattr(cloud, "rect", None)
        if isinstance(rect, pygame.Rect) and rect.left <= x <= rect.right:
            return True
    return False


def _slot_is_plantable_target(slot) -> bool:
    """A planted, living slot with a real rect (a valid mini-boss target)."""
    if getattr(slot, "seed", None) is None or getattr(slot, "dead", False):
        return False
    return isinstance(getattr(slot, "rect", None), pygame.Rect)


def _is_sun_lover(slot) -> bool:
    """A living, planted crop whose sun_min marks it as a sun-lover."""
    if not _slot_is_plantable_target(slot):
        return False
    sun_min = float(getattr(slot.seed, "sun_min", 0.0) or 0.0)
    return sun_min >= float(MINIBOSS_SUN_LOVER_SUN_MIN)


def _planted_indices(slots) -> list[int]:
    return [i for i, s in enumerate(slots) if _slot_is_plantable_target(s)]


def _cloud_is_pinned(cloud) -> bool:
    return bool(getattr(cloud, "pinned", False) or float(getattr(cloud, "pinned_seconds", 0.0) or 0.0) > 0.0)


def _field_clouds(clouds) -> list:
    return [c for c in (clouds or ()) if isinstance(getattr(c, "rect", None), pygame.Rect)]


# ── base ──────────────────────────────────────────────────────────────────────
class MiniBoss:
    """Shared telegraph-then-resolve scaffolding for a mini-boss.

    Lifecycle: ``INACTIVE`` -> ``TELEGRAPH`` (a fixed countdown showing the
    warning) -> ``RESOLVED`` (a short cozy puff) -> ``INACTIVE``. Subclasses
    implement ``_spawn`` (pick a target, place the art), ``_tick`` (per-frame
    movement / early counters), ``_resolve`` (apply the cozy fail or a clean
    counter), ``_draw``, and optionally ``try_click``.
    """

    STATE_INACTIVE = "inactive"
    STATE_TELEGRAPH = "telegraph"
    STATE_RESOLVED = "resolved"

    RESULT_COUNTERED = "countered"
    RESULT_FAILED = "failed"
    RESULT_FIZZLED = "fizzled"

    name = "MiniBoss"
    telegraph_seconds: float = 2.0
    click_counterable: bool = False

    def __init__(self, *, rng: random.Random | None = None):
        self._rng = rng or random.Random()
        self._state = self.STATE_INACTIVE
        self._anim_time = 0.0
        self._telegraph_total = float(self.telegraph_seconds)
        self._telegraph_remaining = 0.0
        self._flash_remaining = 0.0
        self._result: str | None = None
        self._juice_events: list[dict] = []
        # Anchor / hitbox in screen coords. Subclasses size and place this.
        self.rect = pygame.Rect(0, 0, 1, 1)

    # ── public surface (mirrors the critter interface) ────────────────────────
    @property
    def active(self) -> bool:
        return self._state != self.STATE_INACTIVE

    @property
    def resolving(self) -> bool:
        return self._state == self.STATE_RESOLVED

    @property
    def result(self) -> str | None:
        return self._result

    @property
    def telegraph_ratio(self) -> float:
        """1.0 at spawn, easing to 0.0 the instant it resolves."""
        if self._telegraph_total <= 0.0:
            return 0.0
        return max(0.0, min(1.0, self._telegraph_remaining / self._telegraph_total))

    @property
    def progress(self) -> float:
        """0.0 at spawn, 1.0 at resolve (handy for growing telegraphs)."""
        return 1.0 - self.telegraph_ratio

    def force_spawn(self, *, slots, clouds, field_rect: pygame.Rect, ground_rect: pygame.Rect) -> bool:
        if self.active:
            return False
        self._anim_time = 0.0
        self._result = None
        self._telegraph_total = float(self.telegraph_seconds)
        self._telegraph_remaining = float(self.telegraph_seconds)
        ok = self._spawn(slots=slots, clouds=clouds, field_rect=field_rect, ground_rect=ground_rect)
        if not ok:
            self._state = self.STATE_INACTIVE
            return False
        self._state = self.STATE_TELEGRAPH
        return True

    def update(self, dt: float, *, slots, clouds, field_rect: pygame.Rect, ground_rect: pygame.Rect) -> None:
        if dt <= 0.0:
            return
        self._anim_time += dt

        if self._state == self.STATE_INACTIVE:
            return

        if self._state == self.STATE_RESOLVED:
            self._flash_remaining -= dt
            if self._flash_remaining <= 0.0:
                self._deactivate()
            return

        # STATE_TELEGRAPH
        self._telegraph_remaining -= dt
        self._tick(dt, slots=slots, clouds=clouds)
        if self._state != self.STATE_TELEGRAPH:
            return  # _tick resolved early (e.g. a click or a clean counter)
        if self._telegraph_remaining <= 0.0:
            self._telegraph_remaining = 0.0
            self._resolve(slots=slots, clouds=clouds)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active:
            return
        self._draw(surface)

    def try_click(self, pos) -> bool:
        """Route a left click; return True if it countered this mini-boss."""
        return False

    # ── hooks for subclasses ──────────────────────────────────────────────────
    def _spawn(self, *, slots, clouds, field_rect, ground_rect) -> bool:
        raise NotImplementedError

    def _tick(self, dt: float, *, slots, clouds) -> None:
        return

    def _resolve(self, *, slots, clouds) -> None:
        self._finish(self.RESULT_FIZZLED)

    def _draw(self, surface: pygame.Surface) -> None:
        return

    # ── resolution / cleanup ──────────────────────────────────────────────────
    def _finish(self, result: str) -> None:
        self._result = result
        self._state = self.STATE_RESOLVED
        self._flash_remaining = float(MINIBOSS_RESOLVE_FLASH_SECONDS)

    def _deactivate(self) -> None:
        self._state = self.STATE_INACTIVE
        self._telegraph_remaining = 0.0
        self._flash_remaining = 0.0

    # ── tiny drawing utilities (deterministic; no per-frame RNG) ───────────────
    @staticmethod
    def _alpha_circle(surface, color_rgb, center, radius, alpha, width=0) -> None:
        radius = int(radius)
        if radius <= 0:
            return
        pad = 2
        size = radius * 2 + pad * 2
        tmp = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(tmp, (*color_rgb[:3], int(max(0, min(255, alpha)))),
                           (size // 2, size // 2), radius, int(width))
        surface.blit(tmp, (int(center[0]) - size // 2, int(center[1]) - size // 2))


# ── 1. Burrow Mole ────────────────────────────────────────────────────────────
class BurrowMole(MiniBoss):
    """Surfaces under a planted slot, ignoring the side-walk and the Scarecrow.

    A dust ring shrinks toward the mole over the telegraph. Click the mole to
    chase it off. If it is not clicked in time it salts that slot briefly (a
    short, recoverable debuff that blocks replanting until it wears off) and
    burrows away. It never touches the standing crop and never sets dead.
    """

    name = "Burrow Mole"
    telegraph_seconds = float(MINIBOSS_MOLE_TELEGRAPH_SECONDS)
    click_counterable = True

    def __init__(self, *, rng=None):
        super().__init__(rng=rng)
        self._target_index: int | None = None
        self._ring_r0 = 1.0

    def _spawn(self, *, slots, clouds, field_rect, ground_rect) -> bool:
        # Ignore the Scarecrow on purpose: the mole comes up from below.
        cands = _planted_indices(slots)
        if not cands:
            return False
        idx = self._rng.choice(cands)
        self._target_index = idx
        rect = slots[idx].rect
        w, h = MINIBOSS_MOLE_SIZE
        self.rect = pygame.Rect(0, 0, int(w), int(h))
        # Surface from the soil: sit the mound low in the slot.
        self.rect.midbottom = (rect.centerx, rect.bottom - 2)
        self._ring_r0 = max(rect.width, rect.height) * 0.55
        return True

    def _tick(self, dt, *, slots, clouds) -> None:
        # If the crop it surfaced under vanished, there is nothing to salt.
        if not self._target_valid(slots):
            self._finish(self.RESULT_FIZZLED)

    def _resolve(self, *, slots, clouds) -> None:
        if self._target_valid(slots):
            salt = getattr(slots[self._target_index], "salt", None)
            if callable(salt):
                salt(float(MINIBOSS_MOLE_SALT_SECONDS))
            self._finish(self.RESULT_FAILED)
        else:
            self._finish(self.RESULT_FIZZLED)

    def try_click(self, pos) -> bool:
        if self._state == self.STATE_TELEGRAPH and self.rect.collidepoint(pos):
            self._finish(self.RESULT_COUNTERED)
            return True
        return False

    def _target_valid(self, slots) -> bool:
        idx = self._target_index
        return idx is not None and 0 <= idx < len(slots) and _slot_is_plantable_target(slots[idx])

    def _draw(self, surface) -> None:
        t = self._anim_time
        cx, cy = self.rect.centerx, self.rect.centery
        bob = math.sin(t * 6.0) * 1.5  # gentle peek up and down

        if self._state == self.STATE_TELEGRAPH:
            # Shrinking dust ring: large at spawn, collapsing onto the mole as
            # the burrow timer runs out, brightening as it tightens.
            ratio = self.telegraph_ratio
            ring_r = self._ring_r0 * (0.35 + 0.65 * ratio)
            pulse = 0.5 + 0.5 * math.sin(t * 9.0)
            ring_a = int(70 + 90 * (1.0 - ratio))
            self._alpha_circle(surface, (185, 150, 110), (cx, cy - 2), ring_r + pulse * 2,
                               ring_a, width=3)
            self._alpha_circle(surface, (150, 120, 85), (cx, cy - 2), ring_r * 0.62,
                               int(ring_a * 0.7), width=2)

        self._draw_mole(surface, cx, int(cy + bob))

    def _draw_mole(self, surface, cx, cy) -> None:
        w, h = self.rect.width, self.rect.height
        dirt = (120, 85, 55)
        dirt_dark = (92, 64, 42)
        fur = (78, 70, 78)
        fur_dark = (58, 52, 60)
        snout = (208, 150, 150)

        # Dirt mound the mole pokes through.
        mound = pygame.Rect(cx - w // 2, cy - 2, w, h // 2 + 6)
        pygame.draw.ellipse(surface, dirt_dark, mound)
        pygame.draw.ellipse(surface, dirt, mound.inflate(-6, -4))

        # Mole head and body.
        head_r = max(6, h // 3)
        pygame.draw.circle(surface, fur_dark, (cx, cy - head_r // 2 + 1), head_r)
        pygame.draw.circle(surface, fur, (cx, cy - head_r // 2), head_r - 2)
        # Snout.
        pygame.draw.circle(surface, snout, (cx, cy - head_r // 2 + head_r // 3), max(2, head_r // 3))
        pygame.draw.circle(surface, (150, 95, 95), (cx, cy - head_r // 2 + head_r // 3), max(1, head_r // 6))
        # Beady eyes (closed-ish; moles barely see).
        pygame.draw.circle(surface, (15, 12, 12), (cx - head_r // 2, cy - head_r // 2 - 1), 1)
        pygame.draw.circle(surface, (15, 12, 12), (cx + head_r // 2, cy - head_r // 2 - 1), 1)
        # Two little digging paws.
        paw = (64, 56, 62)
        pygame.draw.circle(surface, paw, (cx - head_r, cy + 2), max(2, head_r // 3))
        pygame.draw.circle(surface, paw, (cx + head_r, cy + 2), max(2, head_r // 3))


# ── 2. Locust Pair ────────────────────────────────────────────────────────────
class _Locust:
    """One half of the Locust Pair: flies from an edge to its crop, then nibbles."""

    def __init__(self, *, side, target_index, start_x, target_x, y, size):
        self.side = side
        self.target_index = target_index
        self.x = float(start_x)
        self.target_x = float(target_x)
        self.y = float(y)
        self.alive = True   # False once clicked away
        self.ate = False
        w, h = size
        self.rect = pygame.Rect(0, 0, int(w), int(h))
        self.rect.center = (int(self.x), int(self.y))

    @property
    def arrived(self) -> bool:
        return abs(self.x - self.target_x) <= 2.0

    def move(self, dt, speed) -> None:
        if not self.alive:
            return
        dx = self.target_x - self.x
        step = speed * dt
        if abs(dx) <= step:
            self.x = self.target_x
        else:
            self.x += step if dx > 0 else -step
        self.rect.center = (int(self.x), int(self.y))


class LocustPair(MiniBoss):
    """Two locusts enter from both edges at once and split the player's attention.

    Each locust flies to a planted crop and eats it (clears the slot) when the
    timer expires, unless it is clicked first. Clicking one shoos only that one;
    the other keeps coming. Eating clears the slot (seed -> None) but never sets
    dead. Needs at least two planted crops to spawn.
    """

    name = "Locust Pair"
    telegraph_seconds = float(MINIBOSS_LOCUST_TELEGRAPH_SECONDS)
    click_counterable = True

    def __init__(self, *, rng=None):
        super().__init__(rng=rng)
        self._locusts: list[_Locust] = []

    def _spawn(self, *, slots, clouds, field_rect, ground_rect) -> bool:
        planted = _planted_indices(slots)
        if len(planted) < int(MINIBOSS_LOCUST_MIN_PLANTED):
            return False
        # Maximise separation: leftmost and rightmost crops force divided
        # attention across the field.
        left_idx, right_idx = planted[0], planted[-1]
        w, h = MINIBOSS_LOCUST_SIZE
        left_slot = slots[left_idx].rect
        right_slot = slots[right_idx].rect
        # Hover a touch above each crop's canopy.
        left_y = left_slot.top - h
        right_y = right_slot.top - h
        self._locusts = [
            _Locust(side="left", target_index=left_idx,
                    start_x=-float(w), target_x=float(left_slot.centerx),
                    y=float(left_y), size=(w, h)),
            _Locust(side="right", target_index=right_idx,
                    start_x=float(field_rect.width) + float(w), target_x=float(right_slot.centerx),
                    y=float(right_y), size=(w, h)),
        ]
        # Bounding hitbox (the per-locust hit test in try_click is what matters).
        self.rect = pygame.Rect(0, 0, int(field_rect.width), int(h))
        self.rect.midtop = (field_rect.width // 2, min(left_y, right_y))
        return True

    def _tick(self, dt, *, slots, clouds) -> None:
        speed = float(MINIBOSS_LOCUST_SPEED_PX_PER_SEC)
        for loc in self._locusts:
            if loc.alive:
                loc.move(dt, speed)
        if not any(loc.alive for loc in self._locusts):
            # Both shooed before the timer; a clean save.
            self._finish(self.RESULT_COUNTERED)

    def _resolve(self, *, slots, clouds) -> None:
        any_ate = False
        for loc in self._locusts:
            if not loc.alive:
                continue
            idx = loc.target_index
            if 0 <= idx < len(slots) and _slot_is_plantable_target(slots[idx]):
                clear = getattr(slots[idx], "clear", None)
                if callable(clear):
                    clear()
                    loc.ate = True
                    any_ate = True
            loc.alive = False
        self._finish(self.RESULT_FAILED if any_ate else self.RESULT_COUNTERED)

    def try_click(self, pos) -> bool:
        if self._state != self.STATE_TELEGRAPH:
            return False
        hit = False
        for loc in self._locusts:
            if loc.alive and loc.rect.collidepoint(pos):
                loc.alive = False
                hit = True
                break  # one click shoos one locust
        if hit and not any(loc.alive for loc in self._locusts):
            self._finish(self.RESULT_COUNTERED)
        return hit

    def _deactivate(self) -> None:
        super()._deactivate()
        self._locusts = []

    def _draw(self, surface) -> None:
        for loc in self._locusts:
            if loc.alive:
                self._draw_locust(surface, loc)

    def _draw_locust(self, surface, loc) -> None:
        t = self._anim_time
        cx, cy = loc.rect.center
        w, h = loc.rect.width, loc.rect.height

        # Countdown ring while hovering on the crop: a depleting arc reads as
        # "about to bite". Only show it once the locust has settled.
        if loc.arrived and self._state == self.STATE_TELEGRAPH:
            ratio = self.telegraph_ratio
            r = max(w, h) // 2 + 5
            arc_rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
            try:
                pygame.draw.arc(surface, (230, 120, 90), arc_rect,
                                -math.pi / 2.0, -math.pi / 2.0 + math.tau * ratio, 3)
            except (pygame.error, ValueError):
                pass

        facing = -1 if loc.side == "right" else 1
        body = (150, 180, 70)
        body_dark = (110, 140, 55)
        wing = (220, 235, 175)
        leg = (88, 108, 50)

        # Abdomen + thorax.
        pygame.draw.ellipse(surface, body_dark, pygame.Rect(cx - w // 2, cy - h // 4, w, h // 2))
        pygame.draw.ellipse(surface, body, pygame.Rect(cx - w // 2 + 2, cy - h // 4 + 1, w - 4, h // 2 - 2))

        # Buzzing wings: a sin flicker opens and closes them each frame.
        flick = 0.5 + 0.5 * math.sin(t * 26.0)
        wing_h = int(h * (0.35 + 0.45 * flick))
        wing_surf = pygame.Surface((w, max(2, wing_h)), pygame.SRCALPHA)
        pygame.draw.ellipse(wing_surf, (*wing, 150), wing_surf.get_rect())
        surface.blit(wing_surf, (cx - w // 2, cy - h // 2 - wing_h // 3))

        # Big jumping legs and a head with an eye, facing the crop.
        hx = cx + facing * (w // 2 - 2)
        pygame.draw.line(surface, leg, (cx, cy + h // 4), (cx - facing * w // 4, cy + h // 2), 2)
        pygame.draw.line(surface, leg, (cx + facing * 2, cy + h // 4), (cx + facing * w // 6, cy + h // 2), 2)
        pygame.draw.circle(surface, body_dark, (hx, cy), max(2, h // 4))
        pygame.draw.circle(surface, (20, 20, 20), (hx + facing, cy - 1), 1)
        # Antennae.
        pygame.draw.line(surface, leg, (hx, cy - h // 4), (hx + facing * 5, cy - h // 2), 1)


# ── 3. Glare Mote ─────────────────────────────────────────────────────────────
class GlareMote(MiniBoss):
    """A spark of trapped sunlight settles on a single sun-lover crop.

    A bright halo fills over the telegraph. Shade the column with a cloud (the
    standard ``cloud.rect.left <= centerx <= cloud.rect.right`` cover check) so it
    is shaded when the halo completes, and the spark is snuffed. Otherwise it
    pushes that crop's sun toward overheat. It never sets dead, and it fizzles
    harmlessly if it lands where no sun-lover is planted.
    """

    name = "Glare Mote"
    telegraph_seconds = float(MINIBOSS_GLARE_TELEGRAPH_SECONDS)
    click_counterable = False

    def __init__(self, *, rng=None):
        super().__init__(rng=rng)
        self._target_index: int | None = None
        self._fizzle = False
        self._shaded_now = False

    def _spawn(self, *, slots, clouds, field_rect, ground_rect) -> bool:
        sun_lovers = [i for i in _planted_indices(slots) if _is_sun_lover(slots[i])]
        if sun_lovers:
            # Prefer a sun-lover whose column is not already shaded, so the mote
            # is an actual threat rather than instantly snuffed.
            unshaded = [i for i in sun_lovers if not _cloud_covers_x(clouds, slots[i].rect.centerx)]
            pool = unshaded or sun_lovers
            idx = self._rng.choice(pool)
            self._fizzle = False
        else:
            # Lands where no sun-lover exists: settle on any crop and fizzle.
            planted = _planted_indices(slots)
            if not planted:
                return False
            idx = self._rng.choice(planted)
            self._fizzle = True
        self._target_index = idx
        rect = slots[idx].rect
        size = max(20, min(rect.width, rect.height))
        self.rect = pygame.Rect(0, 0, size, size)
        self.rect.center = rect.center
        self._shaded_now = False
        return True

    def _tick(self, dt, *, slots, clouds) -> None:
        if not self._target_valid(slots):
            # Crop gone (harvested / eaten): nothing to overheat.
            self._finish(self.RESULT_FIZZLED)
            return
        cx = slots[self._target_index].rect.centerx
        self._shaded_now = _cloud_covers_x(clouds, cx)

    def _resolve(self, *, slots, clouds) -> None:
        if self._fizzle or not self._target_valid(slots):
            self._finish(self.RESULT_FIZZLED)
            return
        cx = slots[self._target_index].rect.centerx
        if _cloud_covers_x(clouds, cx):
            self._finish(self.RESULT_COUNTERED)
            return
        slot = slots[self._target_index]
        slot.sun = max(float(getattr(slot, "sun", 0.0)), float(MINIBOSS_GLARE_OVERHEAT_SUN))
        # Scorch the soil so the mote threatens every sun-lover, not only the few
        # crops whose sun_max is below 100. Evaporates water now and keeps drying.
        scorch = getattr(slot, "scorch", None)
        if callable(scorch):
            scorch(float(MINIBOSS_GLARE_SCORCH_SECONDS), float(MINIBOSS_GLARE_SCORCH_WATER_LOSS))
        self._finish(self.RESULT_FAILED)

    def _target_valid(self, slots) -> bool:
        idx = self._target_index
        return idx is not None and 0 <= idx < len(slots) and _slot_is_plantable_target(slots[idx])

    def _draw(self, surface) -> None:
        t = self._anim_time
        cx, cy = self.rect.center
        ratio = self.telegraph_ratio
        grow = self.progress  # 0 -> 1 as the halo fills

        base_r = self.rect.width * 0.5
        halo_r = base_r * (0.5 + 0.9 * grow)
        pulse = 0.5 + 0.5 * math.sin(t * 5.0)

        if self._fizzle:
            # A weak, cool spark that never blooms.
            self._alpha_circle(surface, (255, 235, 170), (cx, cy), base_r * 0.5,
                               int(70 + 40 * pulse))
            self._draw_core(surface, cx, cy, 0.4)
            return

        cool = self._shaded_now
        warm = (170, 205, 235) if cool else (255, 210, 110)
        glow = (210, 230, 245) if cool else (255, 240, 180)
        halo_a = int((40 + 120 * grow) * (0.5 if cool else 1.0))

        # A sunbeam pouring straight down onto the target crop. This is the key
        # legibility cue: it marks exactly which column is overheating and turns
        # cool blue the moment a cloud shades it, teaching "shade this column".
        self._draw_sunbeam(surface, cx, cy, grow, cool)

        # Filling halo: bigger and brighter the closer it is to overheating.
        self._alpha_circle(surface, warm, (cx, cy), halo_r + pulse * 2, halo_a)
        self._alpha_circle(surface, glow, (cx, cy), halo_r * 0.6, min(255, halo_a + 40))

        # Rotating sun-rays (deterministic from anim_time), retreating when shaded.
        ray_len = halo_r * (0.4 if cool else 0.9)
        ray_a = int(halo_a * (0.6 if cool else 1.0))
        for k in range(8):
            ang = t * 1.2 + k * (math.tau / 8.0)
            x2 = cx + math.cos(ang) * (halo_r + ray_len)
            y2 = cy + math.sin(ang) * (halo_r + ray_len)
            x1 = cx + math.cos(ang) * halo_r
            y1 = cy + math.sin(ang) * halo_r
            self._draw_alpha_line(surface, warm, (x1, y1), (x2, y2), ray_a, 2)

        self._draw_core(surface, cx, cy, 0.7 + 0.3 * pulse)

    def _draw_core(self, surface, cx, cy, intensity) -> None:
        r = max(3, int(self.rect.width * 0.16))
        a = int(180 + 75 * max(0.0, min(1.0, intensity)))
        self._alpha_circle(surface, (255, 255, 245), (cx, cy), r, a)

    def _draw_sunbeam(self, surface, cx, cy, grow, cool) -> None:
        # A tapering vertical beam from above the crop down onto it, brightest at
        # the crop so the player reads "the sun is focused HERE, shade it".
        w = max(12, int(self.rect.width * 0.85))
        top = cy - int(self.rect.height * 1.3)
        bottom = cy + int(self.rect.height * 0.95)
        h = max(1, bottom - top)
        warm = (150, 200, 235) if cool else (255, 196, 84)
        base_a = int((34 + 120 * grow) * (0.4 if cool else 1.0))
        beam = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(h):
            f = i / h  # 0 at top, 1 at the crop
            taper = 0.45 + 0.55 * f            # the beam widens toward the crop
            half = max(1, int((w // 2) * taper))
            alpha = int(base_a * (0.25 + 0.75 * f))
            pygame.draw.line(beam, (*warm, alpha), (w // 2 - half, i), (w // 2 + half, i))
        surface.blit(beam, (cx - w // 2, top))

    @staticmethod
    def _draw_alpha_line(surface, color_rgb, p1, p2, alpha, width) -> None:
        xs = [int(p1[0]), int(p2[0])]
        ys = [int(p1[1]), int(p2[1])]
        minx, miny = min(xs) - width - 1, min(ys) - width - 1
        w = max(xs) - minx + width + 1
        h = max(ys) - miny + width + 1
        tmp = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
        pygame.draw.line(tmp, (*color_rgb[:3], int(max(0, min(255, alpha)))),
                         (int(p1[0]) - minx, int(p1[1]) - miny),
                         (int(p2[0]) - minx, int(p2[1]) - miny), int(width))
        surface.blit(tmp, (minx, miny))


# ── 4. Chill Wisp ─────────────────────────────────────────────────────────────
class ChillWisp(MiniBoss):
    """A pale sheen brushes a band of 2-3 adjacent columns.

    When it resolves, any column in the band that is not covered by a cloud has
    its growth stalled briefly (``slot._frozen_seconds``). Covered columns are
    spared. Low stakes, never kills: it is a gentle Frost primer that teaches
    covering a band.
    """

    name = "Chill Wisp"
    telegraph_seconds = float(MINIBOSS_WISP_TELEGRAPH_SECONDS)
    click_counterable = False

    def __init__(self, *, rng=None):
        super().__init__(rng=rng)
        self._band: list[int] = []
        self._col_centers: list[int] = []
        self._col_rects: list[pygame.Rect] = []
        self._col_shaded: list[bool] = []

    def _spawn(self, *, slots, clouds, field_rect, ground_rect) -> bool:
        n = len(slots)
        if n < int(MINIBOSS_WISP_BAND_MIN):
            return False
        width = self._rng.randint(int(MINIBOSS_WISP_BAND_MIN),
                                  min(int(MINIBOSS_WISP_BAND_MAX), n))
        # Prefer the band that brushes the most crops, so "cover a band" is a real
        # choice rather than clipping one column at the edge.
        planted = set(_planted_indices(slots))
        starts = list(range(0, n - width + 1))
        if planted:
            def overlap(s):
                return sum(1 for k in range(width) if (s + k) in planted)
            best = max(overlap(s) for s in starts)
            if best > 0:
                starts = [s for s in starts if overlap(s) == best]
        start = self._rng.choice(starts)
        self._band = list(range(start, start + width))
        self._col_rects = [slots[i].rect.copy() for i in self._band]
        self._col_centers = [r.centerx for r in self._col_rects]
        self._col_shaded = [False] * len(self._band)

        left = self._col_rects[0].left
        right = self._col_rects[-1].right
        top = min(r.top for r in self._col_rects)
        bottom = max(r.bottom for r in self._col_rects)
        # Extend the sheen up the column so it reads as a falling chill.
        self.rect = pygame.Rect(left, max(0, top - 70), right - left, (bottom - max(0, top - 70)))
        return True

    def _tick(self, dt, *, slots, clouds) -> None:
        self._col_shaded = [_cloud_covers_x(clouds, cx) for cx in self._col_centers]

    def _resolve(self, *, slots, clouds) -> None:
        any_frozen = False
        for k, idx in enumerate(self._band):
            if _cloud_covers_x(clouds, self._col_centers[k]):
                continue  # shaded column is spared
            if 0 <= idx < len(slots) and _slot_is_plantable_target(slots[idx]):
                slot = slots[idx]
                prev = float(getattr(slot, "_frozen_seconds", 0.0) or 0.0)
                slot._frozen_seconds = max(prev, float(MINIBOSS_WISP_FREEZE_SECONDS))
                any_frozen = True
        self._finish(self.RESULT_FAILED if any_frozen else self.RESULT_COUNTERED)

    def _deactivate(self) -> None:
        super()._deactivate()
        self._band = []
        self._col_centers = []
        self._col_rects = []
        self._col_shaded = []

    def _draw(self, surface) -> None:
        t = self._anim_time
        shimmer = 0.5 + 0.5 * math.sin(t * 3.5)
        grow = self.progress
        for k, rect in enumerate(self._col_rects):
            shaded = self._col_shaded[k] if k < len(self._col_shaded) else False
            self._draw_column(surface, rect, shaded, shimmer, grow, t, k)

    def _draw_column(self, surface, slot_rect, shaded, shimmer, grow, t, k) -> None:
        top = self.rect.top
        col = pygame.Rect(slot_rect.left + 2, top, slot_rect.width - 4, slot_rect.bottom - top)
        sheen = pygame.Surface((max(1, col.width), max(1, col.height)), pygame.SRCALPHA)

        if shaded:
            # A spared column: a faint, warming clear instead of frost.
            base_a = int(22 + 14 * shimmer)
            pygame.draw.rect(sheen, (210, 225, 235, base_a), sheen.get_rect(), border_radius=8)
        else:
            base_a = int((40 + 70 * grow) * (0.7 + 0.3 * shimmer))
            pygame.draw.rect(sheen, (200, 225, 245, base_a), sheen.get_rect(), border_radius=8)
            # Frost crystals along the top edge, drifting with a sin sway.
            cw = col.width
            for j in range(3):
                fx = int(cw * (0.25 + 0.25 * j)) + int(math.sin(t * 2.0 + j + k) * 2)
                fy = int(6 + 4 * math.sin(t * 3.0 + j * 1.7))
                self._draw_crystal(sheen, fx, fy, 4 + j % 2)
        surface.blit(sheen, col.topleft)

        if not shaded:
            # A drifting wisp curl crossing the column.
            cx = col.centerx + int(math.sin(t * 1.6 + k) * (col.width * 0.25))
            cy = col.top + 14 + int(math.cos(t * 2.2 + k) * 4)
            self._alpha_circle(surface, (235, 245, 255), (cx, cy), 5, int(120 * (0.5 + 0.5 * shimmer)))
            self._alpha_circle(surface, (235, 245, 255), (cx + 6, cy + 3), 3, int(90 * shimmer))

    @staticmethod
    def _draw_crystal(surf, x, y, r) -> None:
        c = (225, 240, 255, 200)
        pygame.draw.line(surf, c, (x - r, y), (x + r, y), 2)
        pygame.draw.line(surf, c, (x, y - r), (x, y + r), 2)
        pygame.draw.line(surf, c, (x - r + 1, y - r + 1), (x + r - 1, y + r - 1), 1)
        pygame.draw.line(surf, c, (x - r + 1, y + r - 1), (x + r - 1, y - r + 1), 1)


# ── 5. Tangle Vine ─────────────────────────────────────────────────────────────
class TangleVine(MiniBoss):
    """A root coils toward one cloud, then pins that cloud briefly.

    The vine never touches crops. Its only fail effect is a short movement lock
    on the nearest unpinned cloud, and it refuses to spawn while any cloud is
    already pinned so a second cloud remains available.
    """

    name = "Tangle Vine"
    telegraph_seconds = float(TANGLE_VINE_TELEGRAPH_SECONDS)
    click_counterable = True

    def __init__(self, *, rng=None):
        super().__init__(rng=rng)
        self._target_cloud = None
        self._clicks = 0
        self._root_center = (0, 0)
        self._tip = (0, 0)

    def _spawn(self, *, slots, clouds, field_rect, ground_rect) -> bool:
        planted = _planted_indices(slots)
        cloud_list = _field_clouds(clouds)
        if not planted or not cloud_list:
            return False
        if any(_cloud_is_pinned(c) for c in cloud_list):
            return False

        def cloud_pressure_key(cloud):
            cx = cloud.rect.centerx
            nearest_crop_dx = min(abs(cx - slots[i].rect.centerx) for i in planted)
            return (nearest_crop_dx, cloud.rect.centery)

        self._target_cloud = min(cloud_list, key=cloud_pressure_key)
        w, h = TANGLE_VINE_ROOT_SIZE
        root_x = max(field_rect.left + w // 2, min(self._target_cloud.rect.centerx, field_rect.right - w // 2))
        root_y = max(ground_rect.top + h // 2, min(ground_rect.bottom - h // 3, ground_rect.top + h // 2))
        self.rect = pygame.Rect(0, 0, int(w), int(h))
        self.rect.center = (int(root_x), int(root_y))
        self._root_center = self.rect.center
        self._clicks = 0
        self._tip = self._cloud_grab_point()
        return True

    def _tick(self, dt, *, slots, clouds) -> None:
        cloud_list = _field_clouds(clouds)
        if self._target_cloud not in cloud_list:
            self._finish(self.RESULT_FIZZLED)
            return
        if any(c is not self._target_cloud and _cloud_is_pinned(c) for c in cloud_list):
            self._finish(self.RESULT_FIZZLED)
            return
        self._tip = self._cloud_grab_point()

    def _resolve(self, *, slots, clouds) -> None:
        cloud_list = _field_clouds(clouds)
        if self._target_cloud not in cloud_list:
            self._finish(self.RESULT_FIZZLED)
            return
        if any(c is not self._target_cloud and _cloud_is_pinned(c) for c in cloud_list):
            self._finish(self.RESULT_FIZZLED)
            return
        if _cloud_is_pinned(self._target_cloud):
            self._finish(self.RESULT_FIZZLED)
            return

        pin = getattr(self._target_cloud, "pin", None)
        if callable(pin):
            pin(float(TANGLE_VINE_PIN_SECONDS))
        else:
            self._target_cloud.pinned_seconds = float(TANGLE_VINE_PIN_SECONDS)
        self._finish(self.RESULT_FAILED)

    def try_click(self, pos) -> bool:
        if self._state != self.STATE_TELEGRAPH or not self.rect.collidepoint(pos):
            return False
        self._clicks += 1
        if self._clicks >= int(TANGLE_VINE_REQUIRED_CLICKS):
            self._finish(self.RESULT_COUNTERED)
        return True

    def _deactivate(self) -> None:
        super()._deactivate()
        self._target_cloud = None
        self._clicks = 0

    def _cloud_grab_point(self):
        rect = getattr(self._target_cloud, "rect", None)
        if not isinstance(rect, pygame.Rect):
            return self._root_center
        return (rect.centerx, rect.bottom - max(6, rect.height // 5))

    def _draw(self, surface) -> None:
        t = self._anim_time
        grow = self.progress
        root = self._root_center
        tip = self._tip
        reach = 0.18 + 0.82 * grow
        end = (root[0] + (tip[0] - root[0]) * reach, root[1] + (tip[1] - root[1]) * reach)

        vine = (54, 132, 58)
        vine_hi = (128, 206, 92)
        vine_dark = (31, 83, 41)
        warning = (235, 218, 120)
        pulse = 0.5 + 0.5 * math.sin(t * 8.0)

        for k, phase in enumerate((0.0, 1.7, 3.3)):
            sway = math.sin(t * 4.0 + phase) * (5.0 + k * 1.5)
            mid = ((root[0] + end[0]) * 0.5 + sway, (root[1] + end[1]) * 0.5 - 22 - k * 5)
            pts = [root, mid, end]
            pygame.draw.lines(surface, vine_dark, False, pts, 7 - k)
            pygame.draw.lines(surface, vine if k != 1 else vine_hi, False, pts, 4 - min(k, 2))

        if self._state == self.STATE_TELEGRAPH:
            ring_r = max(self.rect.width, self.rect.height) * (0.45 + 0.3 * self.telegraph_ratio)
            self._alpha_circle(surface, warning, root, ring_r, int(90 + 80 * pulse), width=3)
            self._draw_click_pips(surface)

        self._draw_root(surface, pulse)
        if grow > 0.55:
            self._draw_leaf_claw(surface, end, tip, grow)

    def _draw_root(self, surface, pulse) -> None:
        x, y = self.rect.center
        w, h = self.rect.size
        mound = pygame.Rect(0, 0, w, h // 2 + 8)
        mound.midbottom = (x, y + h // 2)
        pygame.draw.ellipse(surface, (82, 67, 42), mound)
        pygame.draw.ellipse(surface, (112, 89, 52), mound.inflate(-7, -5))
        core_r = max(9, int(13 + 2 * pulse))
        pygame.draw.circle(surface, (41, 112, 46), (x, y + 2), core_r + 4)
        pygame.draw.circle(surface, (69, 154, 62), (x, y), core_r)
        pygame.draw.circle(surface, (146, 214, 100), (x - 4, y - 5), max(3, core_r // 3))

    def _draw_click_pips(self, surface) -> None:
        needed = int(TANGLE_VINE_REQUIRED_CLICKS)
        cx = self.rect.centerx - (needed - 1) * 7
        y = self.rect.top - 10
        for i in range(needed):
            filled = i < self._clicks
            col = (245, 240, 180) if filled else (42, 92, 45)
            pygame.draw.circle(surface, col, (cx + i * 14, y), 4)
            pygame.draw.circle(surface, (25, 66, 32), (cx + i * 14, y), 4, 1)

    @staticmethod
    def _draw_leaf_claw(surface, end, tip, grow) -> None:
        ex, ey = int(end[0]), int(end[1])
        tx, ty = int(tip[0]), int(tip[1])
        dx = tx - ex
        dy = ty - ey
        dist = max(1.0, math.hypot(dx, dy))
        nx, ny = -dy / dist, dx / dist
        for sign in (-1, 1):
            leaf = pygame.Rect(0, 0, 14, 8)
            leaf.center = (int(ex + nx * sign * 8), int(ey + ny * sign * 8))
            pygame.draw.ellipse(surface, (118, 190, 78), leaf)
        if grow >= 0.92:
            pygame.draw.circle(surface, (224, 238, 150), (tx, ty), 7, 2)


# ── factory + director ────────────────────────────────────────────────────────
_MINIBOSS_FACTORIES = {
    "mole": BurrowMole,
    "locust": LocustPair,
    "glare": GlareMote,
    "wisp": ChillWisp,
    "vine": TangleVine,
}


def make_miniboss(name: str, *, rng: random.Random | None = None) -> MiniBoss:
    factory = _MINIBOSS_FACTORIES[name]
    return factory(rng=rng)


class MiniBossDirector:
    """Spawns and ticks mini-bosses on a capped cadence and routes clicks.

    Drop one of these next to the critters. Call ``update`` each unpaused frame,
    ``draw`` after the field is drawn, and ``handle_click`` from the left-click
    handler. ``force_spawn(name)`` is handy for debug keys.
    """

    def __init__(self, *, rng: random.Random | None = None):
        self._rng = rng or random.Random()
        self._active: list[MiniBoss] = []
        self._spawn_accum = 0.0
        self._cooldown = 0.0
        self._juice_events: list[dict] = []
        self._reported_results: set[int] = set()

    @property
    def active(self) -> list[MiniBoss]:
        return list(self._active)

    @property
    def active_count(self) -> int:
        return len(self._active)

    def update(self, dt: float, *, slots, clouds, field_rect: pygame.Rect, ground_rect: pygame.Rect) -> None:
        if dt <= 0.0:
            return
        if self._cooldown > 0.0:
            self._cooldown = max(0.0, self._cooldown - dt)

        for mb in self._active:
            mb.update(dt, slots=slots, clouds=clouds, field_rect=field_rect, ground_rect=ground_rect)
            if mb.result == MiniBoss.RESULT_FAILED and id(mb) not in self._reported_results:
                self._reported_results.add(id(mb))
                self._juice_events.append({"kind": "fail", "name": mb.name, "pos": mb.rect.center})
        self._active = [mb for mb in self._active if mb.active]

        self._spawn_accum += dt
        check = float(MINIBOSS_SPAWN_CHECK_SECONDS)
        while self._spawn_accum >= check:
            self._spawn_accum -= check
            if self._try_roll_spawn(slots=slots, clouds=clouds, field_rect=field_rect, ground_rect=ground_rect):
                break

    def draw(self, surface: pygame.Surface) -> None:
        for mb in self._active:
            mb.draw(surface)

    def handle_click(self, pos) -> bool:
        for mb in self._active:
            if mb.click_counterable and mb.try_click(pos):
                self._juice_events.append({"kind": "counter", "name": mb.name, "pos": pos})
                return True
        return False

    def force_spawn(self, name: str, *, slots, clouds, field_rect: pygame.Rect, ground_rect: pygame.Rect) -> bool:
        if len(self._active) >= int(MINIBOSS_MAX_ACTIVE):
            return False
        mb = make_miniboss(name, rng=self._rng)
        if mb.force_spawn(slots=slots, clouds=clouds, field_rect=field_rect, ground_rect=ground_rect):
            self._active.append(mb)
            self._juice_events.append({"kind": "spawn", "name": mb.name, "pos": mb.rect.center})
            self._cooldown = float(MINIBOSS_SPAWN_COOLDOWN_SECONDS)
            return True
        return False

    def pop_juice_events(self) -> list[dict]:
        events = self._juice_events
        self._juice_events = []
        return events

    # ── internals ─────────────────────────────────────────────────────────────
    def _try_roll_spawn(self, *, slots, clouds, field_rect, ground_rect) -> bool:
        if len(self._active) >= int(MINIBOSS_MAX_ACTIVE):
            return False
        if self._cooldown > 0.0:
            return False
        if self._rng.random() >= float(MINIBOSS_SPAWN_CHANCE):
            return False
        eligible = self._eligible_types(slots, clouds)
        if not eligible:
            return False
        name = self._rng.choice(eligible)
        return self.force_spawn(name, slots=slots, clouds=clouds, field_rect=field_rect, ground_rect=ground_rect)

    @staticmethod
    def _eligible_types(slots, clouds) -> list[str]:
        planted = _planted_indices(slots)
        eligible: list[str] = []
        if planted:
            eligible.append("mole")
        if len(planted) >= int(MINIBOSS_LOCUST_MIN_PLANTED):
            eligible.append("locust")
        if any(_is_sun_lover(slots[i]) for i in planted):
            eligible.append("glare")
        cloud_list = _field_clouds(clouds)
        if planted and cloud_list and not any(_cloud_is_pinned(c) for c in cloud_list):
            eligible.append("vine")
        return eligible
