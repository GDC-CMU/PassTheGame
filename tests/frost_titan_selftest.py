"""Headless harness for the Frost Titan (winter multi-mark boss).

Run from the repo root with no display:

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tests/frost_titan_selftest.py

It drives a FrostTitan through WAITING -> ACTIVE -> warning -> strike -> retreat
with mock planted slots and clouds, calling update_battle and draw_warning /
draw_bolt / draw_body every frame onto an off-screen Surface. It checks that:

  1. No frame raises while updating or drawing.
  2. A strike marks MORE than one slot (the band is telegraphed via _mark_indices).
  3. With a single covering cloud, some marks block and others are unblocked,
     pop_unblocked_hits() returns exactly the unblocked indices, and the boss
     takes damage for the blocked marks.
  4. An unblocked mark freezes its slot (_frozen_seconds) without killing it.
  5. A fully blocked, perfectly placed volley tags _last_strike_result "perfect"
     and sums damage across the marks.
  6. Two clouds cannot cover three spread marks (the keystone forced choice).
  7. A defeated boss retreats and records the block via pop_blocks().
  8. The inherited procedural animation still runs (idle -> windup -> strike).

Exit code is 0 on success, 1 on any failure, so it can gate a commit. It uses a
seeded RNG so results are deterministic.
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

from settings import (  # noqa: E402
    SCREEN_W,
    FROST_TITAN_MARK_COUNT,
    FROST_TITAN_FREEZE_SECONDS,
)
from frost_titan import FrostTitan  # noqa: E402

DT = 1.0 / 60.0
_FAILURES = []


def check(condition, label):
    print(("  ok  " if condition else " FAIL ") + label)
    if not condition:
        _FAILURES.append(label)


class FakeSlot:
    """Minimal stand-in for a PlantSlot the titan can target and freeze."""

    def __init__(self, x, y=440, planted=True, product_name="Carrot", yield_=1):
        self.rect = pygame.Rect(0, 0, 80, 80)
        self.rect.center = (x, y)
        if planted:
            self.seed = types.SimpleNamespace(product_name=product_name, harvest_yield=yield_)
        else:
            self.seed = None
        self.dead = False
        self.value = 0


class FakeCloud:
    """A blocking cloud spanning an x range (160px wide, like the real cloud)."""

    def __init__(self, center, size=(160, 80)):
        self.rect = pygame.Rect(0, 0, size[0], size[1])
        self.rect.center = center
        self.raining = True

    def covers_sun(self, sun_rect):
        return self.rect.colliderect(sun_rect)


def make_slots():
    """10 slots in a row; plant every other one so the marked band is spread out
    (so a single cloud cannot cover all of it). Slot 4 is the most valuable."""
    slots = []
    for i in range(10):
        x = 80 + i * 100
        if i % 2 == 0:
            name = "Tomato" if i == 4 else "Carrot"  # Tomato (18) > Carrot (7)
            slots.append(FakeSlot(x, planted=True, product_name=name))
        else:
            slots.append(FakeSlot(x, planted=False))
    return slots


def step(titan, surface, slots, clouds):
    """Advance one frame: update + draw everything. Returns the anim transform."""
    titan.update_battle(DT, slots=slots, clouds=clouds)
    titan.draw_body(surface)
    titan.draw_warning(surface, slots=slots)
    titan.draw_bolt(surface)
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


def sample(samples, titan, anim):
    """Track, per phase: the peak vertical scale, and the off_y extremes seen.

    Comparing extremes over each window (rather than one arbitrary frame) keeps
    the animation assertions robust to the idle bob's phase.
    """
    if samples is None or anim is None:
        return
    ph = _phase(titan)
    rec = samples.get(ph)
    if rec is None:
        samples[ph] = {
            "scale_y": anim["scale_y"],
            "scale_x": anim["scale_x"],
            "tint": anim["tint"],
            "off_min": anim["off_y"],
            "off_max": anim["off_y"],
        }
        return
    if anim["scale_y"] > rec["scale_y"]:
        rec["scale_y"] = anim["scale_y"]
        rec["scale_x"] = anim["scale_x"]
        rec["tint"] = anim["tint"]
    rec["off_min"] = min(rec["off_min"], anim["off_y"])
    rec["off_max"] = max(rec["off_max"], anim["off_y"])


def covers(cloud, x):
    return cloud.rect.left <= x <= cloud.rect.right


def run_to_warning(titan, surface, slots, clouds, samples=None, max_frames=6000):
    """Step until the warning window opens and the marks are locked in."""
    for _ in range(max_frames):
        anim = step(titan, surface, slots, clouds)
        sample(samples, titan, anim)
        if titan._warning_remaining > 0.0 and titan._mark_indices:
            return list(titan._mark_indices)
    return None


def run_to_resolve(titan, surface, slots, clouds, samples=None, max_frames=6000):
    """Step until the strike resolves (the frost flash rises)."""
    prev_flash = titan._bolt_flash_remaining
    for _ in range(max_frames):
        anim = step(titan, surface, slots, clouds)
        sample(samples, titan, anim)
        if titan._bolt_flash_remaining > 0.0 and prev_flash <= 0.0:
            return True
        prev_flash = titan._bolt_flash_remaining
    return False


def mark_x(slots, idx):
    return slots[idx].rect.centerx


# ── scenario 1: telegraph + single-cloud forced sacrifice ────────────────────
def scenario_single_cloud():
    print("[1] single cloud: some marks block, the rest land + freeze")
    titan = FrostTitan(rng=random.Random(11))
    surface = pygame.Surface((SCREEN_W, 900), pygame.SRCALPHA)
    slots = make_slots()
    clouds = []  # populated once the band is known

    titan.force_spawn_now()
    check(titan.state == titan.STATE_ACTIVE, "force_spawn_now -> ACTIVE")

    samples = {}
    marks = run_to_warning(titan, surface, slots, clouds, samples=samples)
    check(marks is not None, "a warning window opened with marks")
    if marks is None:
        return
    check(len(marks) >= 2, f"more than one slot is marked (got {len(marks)})")
    check(len(marks) == min(FROST_TITAN_MARK_COUNT, 5),
          f"marked the configured band size ({FROST_TITAN_MARK_COUNT})")

    # Cover only the center mark with one cloud. The outer marks must land.
    center = marks[len(marks) // 2]
    clouds.append(FakeCloud((mark_x(slots, center), 150)))
    expected_unblocked = sorted(i for i in marks if not any(covers(c, mark_x(slots, i)) for c in clouds))
    check(len(expected_unblocked) >= 1, "at least one mark is left uncovered by the single cloud")

    hp_before = titan.hp
    resolved = run_to_resolve(titan, surface, slots, clouds, samples=samples)
    check(resolved, "the strike resolved")

    hits = sorted(titan.pop_unblocked_hits())
    check(hits == expected_unblocked,
          f"pop_unblocked_hits == uncovered marks (got {hits}, want {expected_unblocked})")
    check(titan._last_strike_result == "hit", "result is 'hit' (a mark landed)")
    check(titan.hp < hp_before, f"boss took damage from the blocked mark ({hp_before} -> {titan.hp})")

    for idx in expected_unblocked:
        slot = slots[idx]
        check(abs(getattr(slot, "_frozen_seconds", 0.0) - FROST_TITAN_FREEZE_SECONDS) < 1e-6,
              f"slot {idx} frozen for {FROST_TITAN_FREEZE_SECONDS}s")
        check(slot.dead is False, f"slot {idx} was frozen, not killed")

    # The strike lunge is armed one frame after the flash rises (rising-edge
    # detection in _advance_anim), so step a few more frames to sample it.
    for _ in range(6):
        anim = step(titan, surface, slots, clouds)
        sample(samples, titan, anim)

    # Inherited animation must still be live.
    idle, windup, strike = samples.get("idle"), samples.get("windup"), samples.get("strike")
    check(idle is not None and windup is not None and strike is not None,
          "idle, windup and strike frames were all drawn")
    if idle and windup and strike:
        check(windup["scale_y"] > idle["scale_y"] + 0.04, "windup swells taller than idle")
        check(windup["tint"] > 0.05, "windup adds a cold charge tint")
        check(strike["off_max"] > idle["off_max"] + 6.0, "strike lunges downward")
    print()


# ── scenario 2: fully blocked, perfectly placed volley ───────────────────────
def scenario_all_perfect():
    print("[2] all marks blocked + perfectly centered -> 'perfect' + summed damage")
    titan = FrostTitan(rng=random.Random(22))
    surface = pygame.Surface((SCREEN_W, 900), pygame.SRCALPHA)
    slots = make_slots()
    clouds = []

    titan.force_spawn_now()
    marks = run_to_warning(titan, surface, slots, clouds)
    check(marks is not None and len(marks) >= 2, "marks telegraphed")
    if not marks:
        return

    # One cloud centered exactly on each mark -> every mark is a perfect block.
    for idx in marks:
        clouds.append(FakeCloud((mark_x(slots, idx), 150)))

    hp_before = titan.hp
    resolved = run_to_resolve(titan, surface, slots, clouds)
    check(resolved, "the strike resolved")

    hits = titan.pop_unblocked_hits()
    check(hits == [], f"no marks landed (pop_unblocked_hits empty, got {hits})")
    check(titan._last_strike_result == "perfect", "result is 'perfect' (all blocked, >=1 perfect)")
    check(titan._last_perfect_pos is not None, "_last_perfect_pos recorded")
    # Each mark = 1 dmg + 1 perfect bonus, so >= 2 * len(marks).
    dealt = hp_before - titan.hp
    check(dealt >= 2 * len(marks),
          f"damage summed across {len(marks)} perfect blocks ({dealt} dealt)")
    check(titan.block_combo >= 1, "a clean volley extended the block combo")
    print()


# ── scenario 3: two clouds cannot cover three spread marks ────────────────────
def scenario_two_clouds_keystone():
    print("[3] keystone: two clouds cannot cover three spread marks")
    titan = FrostTitan(rng=random.Random(33))
    surface = pygame.Surface((SCREEN_W, 900), pygame.SRCALPHA)
    slots = make_slots()
    clouds = []

    titan.force_spawn_now()
    marks = run_to_warning(titan, surface, slots, clouds)
    check(marks is not None and len(marks) == 3, "exactly three marks (the keystone case)")
    if not marks or len(marks) != 3:
        return

    # Cover the first two marks; the third is out of reach of both clouds.
    clouds.append(FakeCloud((mark_x(slots, marks[0]), 150)))
    clouds.append(FakeCloud((mark_x(slots, marks[1]), 150)))
    expected_unblocked = sorted(i for i in marks if not any(covers(c, mark_x(slots, i)) for c in clouds))

    run_to_resolve(titan, surface, slots, clouds)
    hits = sorted(titan.pop_unblocked_hits())
    check(hits == expected_unblocked == [marks[2]],
          f"exactly one mark landed despite two clouds (got {hits})")
    print()


# ── scenario 4: defeat -> retreat ────────────────────────────────────────────
def scenario_retreat_on_defeat():
    print("[4] a killing block sends the boss into retreat")
    titan = FrostTitan(rng=random.Random(44))
    surface = pygame.Surface((SCREEN_W, 900), pygame.SRCALPHA)
    slots = make_slots()
    clouds = []

    titan.force_spawn_now()
    marks = run_to_warning(titan, surface, slots, clouds)
    if not marks:
        check(False, "marks telegraphed")
        return
    titan._hp = 1  # next block finishes it
    clouds.append(FakeCloud((mark_x(slots, marks[len(marks) // 2]), 150)))

    run_to_resolve(titan, surface, slots, clouds)
    retreating = False
    for _ in range(400):
        step(titan, surface, slots, clouds)
        if titan.state == titan.STATE_RETREATING:
            retreating = True
            break
    check(retreating or titan.state != titan.STATE_ACTIVE,
          "boss left the fight after defeat (retreated; may have already returned to waiting)")
    check(titan.hp <= 0, "boss HP reached zero")
    check(titan.pop_blocks() >= 1, "the block was recorded via pop_blocks()")
    print()


def main():
    scenario_single_cloud()
    scenario_all_perfect()
    scenario_two_clouds_keystone()
    scenario_retreat_on_defeat()

    if _FAILURES:
        print(f"RESULT: {len(_FAILURES)} FAILED")
        for f in _FAILURES:
            print("  - " + f)
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
