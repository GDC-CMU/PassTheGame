"""Headless harness for the boss-titan procedural animation.

Run from the repo root with no display:

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tests/titan_anim_selftest.py

It drives each titan (Storm, Cyclone, Drought) through the full state machine,
idle -> windup -> strike -> retreat, calling update_battle and draw_body every
frame onto an off-screen Surface. It checks that:

  1. No frame raises while drawing.
  2. The drawn scale/offset actually changes between idle, windup and strike
     (the animation is live, not a static blit). Sampled values are printed.
  3. Combat is untouched: an unblocked strike still records via
     pop_unblocked_hits() (Storm/Cyclone) or spikes plant sun (Drought), and a
     blocked strike still damages the boss and sends it into retreat.

Exit code is 0 on success, 1 on any failure, so it can gate a commit. It uses no
test framework and a seeded RNG so results are deterministic.
"""

import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import random  # noqa: E402

import pygame  # noqa: E402

pygame.init()

from settings import SCREEN_W, UI_PANEL_W, SUN_X, SUN_Y, SUN_RADIUS  # noqa: E402
from storm_titan import StormTitan  # noqa: E402
from cyclone_titan import CycloneTitan  # noqa: E402
from drought_titan import DroughtTitan  # noqa: E402

DT = 1.0 / 60.0
FIELD_CENTER_X = (SCREEN_W - UI_PANEL_W) // 2
_FAILURES = []


def check(condition, label):
    print(("  ok  " if condition else " FAIL ") + label)
    if not condition:
        _FAILURES.append(label)


class FakeSlot:
    """Minimal stand-in for a PlantSlot the titans can target."""

    def __init__(self, x, y=400):
        self.seed = types.SimpleNamespace(product_name=None, harvest_yield=1)
        self.dead = False
        self.rect = pygame.Rect(0, 0, 40, 40)
        self.rect.center = (x, y)
        self.sun = 50.0
        self.water = 50.0
        self.struck = False

    def replant(self):
        self.seed = types.SimpleNamespace(product_name=None, harvest_yield=1)
        self.dead = False
        self.sun = 50.0
        self.water = 50.0
        self.struck = False

    def strike_lightning(self, salt_seconds=0.0):
        self.dead = True
        self.struck = True


class FakeCloud:
    """A blocking cloud: spans an x range and can rain / cover the sun."""

    def __init__(self, center, size=(160, 60), raining=True):
        self.rect = pygame.Rect(0, 0, size[0], size[1])
        self.rect.center = center
        self.raining = raining

    def covers_sun(self, sun_rect):
        return self.rect.colliderect(sun_rect)


def _step(titan, surface, slots, clouds):
    """Advance one frame: update battle, then draw the body. Returns the
    transform that draw_body computed for this frame."""
    titan.update_battle(DT, slots=slots, clouds=clouds)
    titan.draw_body(surface)
    return titan._anim_debug


def _phase(titan):
    if titan.state == titan.STATE_RETREATING:
        return "retreat"
    if titan._strike_pop_remaining > 0.0:
        return "strike"
    if titan.state == titan.STATE_ACTIVE and titan._warning_remaining > 0.0:
        return "windup"
    if titan.state == titan.STATE_ACTIVE:
        return "idle"
    return "other"


def run_titan(name, titan, *, slot_x, sun_target):
    print(f"[{name}]")
    surface = pygame.Surface((SCREEN_W, 800), pygame.SRCALPHA)

    slot = FakeSlot(slot_x)
    slots = [slot]

    samples = {}  # phase -> transform with the largest scale_y seen

    def record(anim, ph):
        if anim is None:
            return
        prev = samples.get(ph)
        if prev is None or anim["scale_y"] > prev["scale_y"]:
            samples[ph] = anim

    titan.force_spawn_now()
    check(titan.state == titan.STATE_ACTIVE, "force_spawn_now -> ACTIVE")

    # Idle -> windup -> unblocked strike (no cloud present).
    target_index_at_strike = None
    sun_before_strike = slot.sun
    drew_ok = True
    for _ in range(2000):
        anim = _step(titan, surface, slots, clouds=[])
        ph = _phase(titan)  # classify the state that produced this drawn frame
        if anim is None:
            drew_ok = False
        record(anim, ph)
        if ph == "windup" and titan._target_slot_index is not None:
            # Remember the slot the storm/cyclone locked just before it fires.
            target_index_at_strike = titan._target_slot_index
        if titan._strike_pop_remaining > 0.0:
            break

    check(drew_ok, "draw_body produced a transform every frame")
    check("idle" in samples, "idle frames were drawn")
    check("windup" in samples, "windup frames were drawn")
    check(titan._strike_pop_remaining > 0.0, "a strike lunge was triggered")

    # Drive a couple more frames so the strike pop is captured at full strength.
    for _ in range(3):
        anim = _step(titan, surface, slots, clouds=[])
        record(anim, _phase(titan))

    idle = samples.get("idle")
    windup = samples.get("windup")
    strike = samples.get("strike")
    check(strike is not None, "strike frames were drawn")

    if idle and windup and strike:
        def fmt(a):
            return (f"scale=({a['scale_x']:.3f},{a['scale_y']:.3f}) "
                    f"off=({a['off_x']:+.1f},{a['off_y']:+.1f}) tint={a['tint']:.2f}")
        print("      idle  : " + fmt(idle))
        print("      windup: " + fmt(windup))
        print("      strike: " + fmt(strike))

        check(abs(idle["scale_x"] - 1.0) < 1e-6 and abs(idle["scale_y"] - 1.0) < 1e-6,
              "idle has no scaling (just bob/sway)")
        check(windup["scale_y"] > idle["scale_y"] + 0.04,
              "windup swells the sprite taller than idle")
        check(windup["off_y"] < idle["off_y"] - 2.0,
              "windup rears the sprite upward vs idle")
        check(windup["tint"] > 0.0, "windup adds a charge tint")
        check(strike["off_y"] > idle["off_y"] + 6.0,
              "strike lunges downward toward the target")
        check(strike["scale_y"] > 1.05, "strike pops the sprite's scale")
        check(abs(strike["off_y"] - windup["off_y"]) > 6.0,
              "strike offset clearly differs from windup offset")

    # Combat must still work on the unblocked strike.
    if name == "Drought":
        check(slot.sun > sun_before_strike + 10.0,
              "drought unblocked strike spiked plant sun")
        check(titan._took_unblocked_hit, "drought recorded an unblocked hit")
    else:
        hits = titan.pop_unblocked_hits()
        check(len(hits) >= 1, "unblocked strike recorded via pop_unblocked_hits()")
        if target_index_at_strike is not None and target_index_at_strike >= 0:
            check(target_index_at_strike in hits,
                  "the locked target index was the one recorded")

    # Blocked strike -> boss takes damage -> retreat. Re-arm a living plant and
    # drop the boss to 1 HP so a single block finishes it.
    slot.replant()
    titan._hp = 1
    if name == "Drought":
        block_cloud = FakeCloud((SUN_X, SUN_Y), size=(140, 90))
    else:
        block_cloud = FakeCloud((slot_x, 130), size=(180, 60), raining=True)
    clouds = [block_cloud]

    retreating = False
    for _ in range(3000):
        anim = _step(titan, surface, slots, clouds=clouds)
        record(anim, _phase(titan))
        if titan.state == titan.STATE_RETREATING:
            retreating = True
            break

    check(retreating, "blocked strike damaged the boss into retreat")
    check(titan.hp <= 0, "boss HP reached zero from the block")
    check(titan.pop_blocks() >= 1, "the block was recorded via pop_blocks()")

    # Sample several retreat frames and confirm the gentle shrink + fade.
    retreat_sample = None
    for _ in range(30):
        anim = _step(titan, surface, slots, clouds=clouds)
        if anim is not None:
            retreat_sample = anim
    if retreat_sample is not None:
        print("      retreat: " + f"scale=({retreat_sample['scale_x']:.3f},"
              f"{retreat_sample['scale_y']:.3f}) alpha={retreat_sample['alpha']}")
        check(retreat_sample["alpha"] == titan.ANIM_RETREAT_ALPHA,
              "retreat keeps the faded alpha")
        check(retreat_sample["scale_x"] < 1.0 and retreat_sample["scale_y"] < 1.0,
              "retreat gently shrinks the sprite")
    print()


def main():
    run_titan("Storm", StormTitan(rng=random.Random(1)), slot_x=FIELD_CENTER_X, sun_target=False)
    run_titan("Cyclone", CycloneTitan(rng=random.Random(2)), slot_x=FIELD_CENTER_X, sun_target=False)
    run_titan("Drought", DroughtTitan(rng=random.Random(3)), slot_x=300, sun_target=True)

    if _FAILURES:
        print(f"RESULT: {len(_FAILURES)} FAILED")
        for f in _FAILURES:
            print("  - " + f)
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
