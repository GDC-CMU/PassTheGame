"""Headless harness for the mini-boss tier (small, frequent field threats).

Run from the repo root with no display:

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tests/minibosses_selftest.py

It spawns each mini-boss against mock slots/clouds, drives it through its whole
telegraph -> resolve -> cleanup lifecycle while drawing every frame onto an
off-screen surface, and checks the contract that keeps them cozy:

  - The telegraph actually renders something (no invisible threats).
  - The counter works: a click shoos the Burrow Mole and the Locust Pair, a
    cloud over the column snuffs the Glare Mote, and clouds over the band spare
    the Chill Wisp's columns.
  - The cozy fail applies the right debuff and NEVER sets slot.dead: the Mole
    salts its slot, the Locust clears (eats) its crop, the Glare Mote overheats
    the sun-lover's sun toward 100, and the Chill Wisp freezes uncovered columns.
  - The Glare Mote fizzles with no effect where no sun-lover is planted.
  - Every mini-boss cleans up (goes inactive) after its resolve flash.
  - The director caps active mini-bosses and routes clicks.

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
pygame.display.set_mode((1, 1))

from settings import (  # noqa: E402
    SCREEN_W,
    SCREEN_H,
    UI_PANEL_W,
    GROUND_HEIGHT_PCT,
    SLOT_COUNT,
    SLOT_PADDING,
    MINIBOSS_MAX_ACTIVE,
    MINIBOSS_MOLE_SALT_SECONDS,
    MINIBOSS_GLARE_OVERHEAT_SUN,
    MINIBOSS_WISP_FREEZE_SECONDS,
    MINIBOSS_RESOLVE_FLASH_SECONDS,
)
from minibosses import (  # noqa: E402
    BurrowMole,
    LocustPair,
    GlareMote,
    ChillWisp,
    TangleVine,
    MiniBossDirector,
    MiniBoss,
)
from cloud import Cloud  # noqa: E402

DT = 1.0 / 60.0
FIELD_W = SCREEN_W - UI_PANEL_W
GROUND_H = int(SCREEN_H * GROUND_HEIGHT_PCT)
FIELD_RECT = pygame.Rect(0, 0, FIELD_W, SCREEN_H)
GROUND_RECT = pygame.Rect(0, SCREEN_H - GROUND_H, FIELD_W, GROUND_H)

_FAILURES = []


def check(condition, label):
    print(("  ok  " if condition else " FAIL ") + label)
    if not condition:
        _FAILURES.append(label)


class FakeSlot:
    """Minimal stand-in for a PlantSlot the mini-bosses can target and debuff."""

    def __init__(self, rect, *, seed=None, sun=60.0):
        self.rect = rect
        self.seed = seed
        self.dead = False
        self.sun = float(sun)
        self.water = 50.0
        self.has_scarecrow = False
        self._frozen_seconds = 0.0
        self._salted = 0.0

    def clear(self):
        self.seed = None  # eaten: empty, but explicitly NOT dead

    def salt(self, seconds):
        self._salted = max(self._salted, float(seconds))

    @property
    def salted(self):
        return self._salted > 0.0


class FakeCloud:
    """A cloud spanning an x range (160px wide, like the real cloud)."""

    def __init__(self, center, size=(160, 80)):
        self.rect = pygame.Rect(0, 0, size[0], size[1])
        self.rect.center = center
        self.raining = True
        self.pinned_seconds = 0.0

    @property
    def pinned(self):
        return self.pinned_seconds > 0.0

    def pin(self, seconds):
        if not self.pinned:
            self.pinned_seconds = float(seconds)


def _seed(name="Carrot", sun_min=20.0):
    return types.SimpleNamespace(product_name=name, sun_min=float(sun_min))


def make_slots(planted=None, sun_lovers=None, sun=60.0):
    """10 slots laid out exactly like Game._create_slots so cloud coverage is
    realistic. ``planted`` and ``sun_lovers`` are sets of indices to seed."""
    planted = set(planted or ())
    sun_lovers = set(sun_lovers or ())
    total_padding = SLOT_PADDING * (SLOT_COUNT + 1)
    slot_w = (FIELD_W - total_padding) // SLOT_COUNT
    slot_h = max(20, GROUND_H - SLOT_PADDING * 2)
    y = GROUND_RECT.top + (GROUND_H - slot_h) // 2
    slots = []
    for i in range(SLOT_COUNT):
        x = SLOT_PADDING + i * (slot_w + SLOT_PADDING)
        rect = pygame.Rect(x, y, slot_w, slot_h)
        seed = None
        if i in sun_lovers:
            seed = _seed("Tomato", sun_min=55.0)
        elif i in planted:
            seed = _seed("Lettuce", sun_min=0.0)
        slots.append(FakeSlot(rect, seed=seed, sun=sun))
    return slots


def fresh_surface():
    return pygame.Surface((FIELD_W, SCREEN_H), pygame.SRCALPHA)


def drawn_pixels(mb):
    """Render one frame onto a clean surface and count rendered (alpha) pixels."""
    surf = fresh_surface()
    surf.fill((0, 0, 0, 0))
    mb.draw(surf)
    return pygame.mask.from_surface(surf, 8).count()


def step(mb, slots, clouds, frames):
    for _ in range(frames):
        mb.update(DT, slots=slots, clouds=clouds, field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
        mb.draw(fresh_surface())  # exercise draw every frame; must not raise


def run_to_inactive(mb, slots, clouds, limit=240):
    for _ in range(limit):
        if not mb.active:
            return True
        mb.update(DT, slots=slots, clouds=clouds, field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
        mb.draw(fresh_surface())
    return not mb.active


# ── Burrow Mole ───────────────────────────────────────────────────────────────
def test_mole():
    print("[mole] Burrow Mole: surfaces on a slot, click to scare, else salt")
    rng = random.Random(1)

    # Counter path: a click chases it off with no salt.
    slots = make_slots(planted={4})
    slots[4].has_scarecrow = True  # it must ignore the scarecrow
    clouds = []
    mb = BurrowMole(rng=rng)
    ok = mb.force_spawn(slots=slots, clouds=clouds, field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    check(ok and mb.active, "mole spawned on a planted (scarecrow-protected) slot")
    check(abs(mb.rect.centerx - slots[4].rect.centerx) <= 1, "mole surfaced at the target slot column")
    check(mb.telegraph_ratio > 0.95, "telegraph starts full")
    step(mb, slots, clouds, 6)
    check(drawn_pixels(mb) > 0, "dust-ring telegraph renders")
    check(mb.telegraph_ratio < 1.0, "telegraph counts down")
    hit = mb.try_click(mb.rect.center)
    check(hit and mb.result == MiniBoss.RESULT_COUNTERED, "clicking the mole counters it")
    check(not slots[4].salted, "a countered mole leaves no salt")
    check(run_to_inactive(mb, slots, clouds), "countered mole cleans up")
    check(not slots[4].dead, "mole never kills the crop (counter)")

    # Fail path: ignored, it salts the slot briefly and burrows away.
    slots = make_slots(planted={4})
    mb = BurrowMole(rng=rng)
    mb.force_spawn(slots=slots, clouds=[], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    step(mb, slots, [], int(MINIBOSS_MOLE_SALT_SECONDS) + 140)  # well past the 2s telegraph
    check(mb.result == MiniBoss.RESULT_FAILED, "ignored mole resolves as a fail")
    check(slots[4].salted, "ignored mole salts its slot (cozy debuff)")
    check(abs(slots[4]._salted - float(MINIBOSS_MOLE_SALT_SECONDS)) < 0.01, "salt uses the tuned duration")
    check(not slots[4].dead, "mole never sets slot.dead")
    check(run_to_inactive(mb, slots, []), "failed mole cleans up after its puff")


# ── Locust Pair ───────────────────────────────────────────────────────────────
def test_locust():
    print("[locust] Locust Pair: two edges at once, click each or lose a crop")
    rng = random.Random(2)

    # Needs >= 2 planted to spawn.
    one = make_slots(planted={5})
    check(not LocustPair(rng=rng).force_spawn(slots=one, clouds=[], field_rect=FIELD_RECT, ground_rect=GROUND_RECT),
          "locusts refuse to spawn with fewer than two crops")

    slots = make_slots(planted={0, 9})
    mb = LocustPair(rng=rng)
    ok = mb.force_spawn(slots=slots, clouds=[], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    locs = mb._locusts
    check(ok and len(locs) == 2, "two locusts spawned")
    check(min(l.x for l in locs) < 0 and max(l.x for l in locs) > FIELD_W,
          "locusts enter from both edges at once")
    step(mb, slots, [], 16)  # let them fly in and settle
    check(drawn_pixels(mb) > 0, "locust telegraph renders once on screen")

    # Click the left locust; let the right one eat its crop.
    left = min(locs, key=lambda l: l.target_index)
    right = max(locs, key=lambda l: l.target_index)
    hit = mb.try_click(left.rect.center)
    check(hit and not left.alive and right.alive, "clicking one locust shoos only that one")
    step(mb, slots, [], 160)
    check(mb.result == MiniBoss.RESULT_FAILED, "an un-clicked locust resolves as a fail")
    check(slots[0].seed is not None, "the saved crop survived")
    check(slots[9].seed is None, "the un-clicked locust ate (cleared) its crop")
    check(not slots[9].dead, "eaten slot is empty, never dead")
    check(run_to_inactive(mb, slots, []), "locust pair cleans up")

    # Counter both: no crop lost.
    slots = make_slots(planted={2, 7})
    mb = LocustPair(rng=rng)
    mb.force_spawn(slots=slots, clouds=[], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    step(mb, slots, [], 16)
    for loc in list(mb._locusts):
        mb.try_click(loc.rect.center)
    check(mb.result == MiniBoss.RESULT_COUNTERED, "clicking both locusts counters the pair")
    check(slots[2].seed is not None and slots[7].seed is not None, "both crops survive a clean counter")
    check(run_to_inactive(mb, slots, []), "countered locust pair cleans up")


# ── Glare Mote ────────────────────────────────────────────────────────────────
def test_glare():
    print("[glare] Glare Mote: shade the sun-lover's column or it overheats")
    rng = random.Random(3)

    # Fail path: a sun-lover with no shade overheats toward 100.
    slots = make_slots(sun_lovers={4}, sun=62.0)
    mb = GlareMote(rng=rng)
    ok = mb.force_spawn(slots=slots, clouds=[], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    check(ok and mb._target_index == 4 and not mb._fizzle, "mote settled on the sun-lover")
    step(mb, slots, [], 6)
    check(drawn_pixels(mb) > 0, "growing-halo telegraph renders")
    step(mb, slots, [], 160)
    check(mb.result == MiniBoss.RESULT_FAILED, "unshaded sun-lover resolves as a fail")
    check(slots[4].sun >= float(MINIBOSS_GLARE_OVERHEAT_SUN) - 0.001, "overheat pushes sun toward 100")
    check(not slots[4].dead, "glare never sets slot.dead")
    check(run_to_inactive(mb, slots, []), "failed glare cleans up")

    # Counter path: a cloud over the column snuffs it (sun untouched).
    slots = make_slots(sun_lovers={4}, sun=62.0)
    cloud = FakeCloud(center=(slots[4].rect.centerx, 120))
    mb = GlareMote(rng=rng)
    mb.force_spawn(slots=slots, clouds=[cloud], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    step(mb, slots, [cloud], 6)
    check(mb._shaded_now, "the mote registers the column as shaded (feedback)")
    step(mb, slots, [cloud], 170)
    check(mb.result == MiniBoss.RESULT_COUNTERED, "shading the column counters the mote")
    check(abs(slots[4].sun - 62.0) < 0.001, "a shaded crop keeps its sun (no overheat)")
    check(not slots[4].dead, "countered glare leaves the crop alive")
    check(run_to_inactive(mb, slots, [cloud]), "countered glare cleans up")

    # Fizzle path: lands where no sun-lover exists -> no effect.
    slots = make_slots(planted={1}, sun=62.0)  # slot 1 is a non-sun-lover
    mb = GlareMote(rng=rng)
    ok = mb.force_spawn(slots=slots, clouds=[], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    check(ok and mb._fizzle, "mote on a non-sun-lover is flagged to fizzle")
    step(mb, slots, [], 170)
    check(mb.result == MiniBoss.RESULT_FIZZLED, "no sun-lover -> the mote fizzles")
    check(abs(slots[1].sun - 62.0) < 0.001 and not slots[1].dead, "a fizzle changes nothing")
    check(run_to_inactive(mb, slots, []), "fizzled glare cleans up")


# ── Chill Wisp ────────────────────────────────────────────────────────────────
def test_wisp():
    print("[wisp] Chill Wisp: cover the band or columns stall briefly")
    rng = random.Random(4)

    # Fail-with-partial-save: cover one column of the band, freeze the rest.
    slots = make_slots(planted={2, 3, 4, 5, 6})
    mb = ChillWisp(rng=rng)
    mb.force_spawn(slots=slots, clouds=[], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    band = list(mb._band)
    check(2 <= len(band) <= 3, "wisp brushes a 2-3 column band")
    check(band == list(range(band[0], band[0] + len(band))), "the band is contiguous (adjacent columns)")
    step(mb, slots, [], 6)
    check(drawn_pixels(mb) > 0, "pale-sheen telegraph renders")
    covered_idx = band[0]
    cloud = FakeCloud(center=(slots[covered_idx].rect.centerx, 120))
    step(mb, slots, [cloud], 170)
    check(mb.result == MiniBoss.RESULT_FAILED, "an uncovered band resolves as a fail")
    check(slots[covered_idx]._frozen_seconds == 0.0, "the covered column is spared")
    frozen_others = [slots[i]._frozen_seconds for i in band[1:]]
    check(all(abs(f - float(MINIBOSS_WISP_FREEZE_SECONDS)) < 0.001 for f in frozen_others),
          "uncovered columns get the freeze stall")
    check(all(not slots[i].dead for i in band), "the wisp never kills a column")
    check(run_to_inactive(mb, slots, [cloud]), "wisp cleans up")

    # Counter-all: cover every column center with clouds -> nothing freezes.
    slots = make_slots(planted={2, 3, 4, 5, 6})
    mb = ChillWisp(rng=rng)
    mb.force_spawn(slots=slots, clouds=[], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    band = list(mb._band)
    centers = [slots[i].rect.centerx for i in band]
    clouds = [FakeCloud(center=(c, 120)) for c in centers]  # one cloud per column center
    step(mb, slots, clouds, 170)
    check(mb.result == MiniBoss.RESULT_COUNTERED, "covering the whole band counters the wisp")
    check(all(slots[i]._frozen_seconds == 0.0 for i in band), "no column freezes when the band is covered")
    check(run_to_inactive(mb, slots, clouds), "countered wisp cleans up")


# ── Tangle Vine ────────────────────────────────────────────────────────────────
def test_tangle_vine():
    print("[vine] Tangle Vine: click root three times or one cloud is pinned briefly")
    rng = random.Random(6)

    slots = make_slots(planted={2, 7})
    cloud_a = FakeCloud(center=(slots[2].rect.centerx, 120))
    cloud_b = FakeCloud(center=(slots[7].rect.centerx, 120))
    mb = TangleVine(rng=rng)
    ok = mb.force_spawn(slots=slots, clouds=[cloud_a, cloud_b], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    check(ok and mb.active, "vine spawns with a cloud and planted crop")
    check(mb._target_cloud is cloud_a, "vine targets the nearest single cloud")
    step(mb, slots, [cloud_a, cloud_b], 6)
    check(drawn_pixels(mb) > 0, "coiling vine telegraph renders")
    check(mb.telegraph_ratio < 1.0, "vine telegraph counts down")

    for _ in range(2):
        check(mb.try_click(mb.rect.center), "clicking the vine root registers")
    check(mb.active and mb.result is None, "two root clicks are not enough")
    check(mb.try_click(mb.rect.center), "third vine-root click registers")
    check(mb.result == MiniBoss.RESULT_COUNTERED, "three root clicks counter the vine")
    check(not cloud_a.pinned and not cloud_b.pinned, "countered vine pins no cloud")
    check(run_to_inactive(mb, slots, [cloud_a, cloud_b]), "countered vine cleans up")

    slots = make_slots(planted={2, 7})
    cloud_a = FakeCloud(center=(slots[2].rect.centerx, 120))
    cloud_b = FakeCloud(center=(slots[7].rect.centerx, 120))
    mb = TangleVine(rng=rng)
    mb.force_spawn(slots=slots, clouds=[cloud_a, cloud_b], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    step(mb, slots, [cloud_a, cloud_b], 170)
    check(mb.result == MiniBoss.RESULT_FAILED, "ignored vine resolves as a fail")
    check(abs(cloud_a.pinned_seconds - 3.5) < 0.05, "ignored vine pins the nearest cloud for about 3.5s")
    check(not cloud_b.pinned, "vine never pins both clouds")
    check(all(s.seed is not None and not s.dead for s in slots if s.seed is not None), "vine never damages crops directly")
    check(run_to_inactive(mb, slots, [cloud_a, cloud_b]), "failed vine cleans up")

    real_cloud = Cloud(start_pos=(80, 80))
    real_cloud.pin(3.5)
    start = real_cloud.rect.topleft
    old_get_pressed = pygame.key.get_pressed

    class PressRight:
        def __getitem__(self, key):
            return key == real_cloud.controls["right"]

    pygame.key.get_pressed = lambda: PressRight()
    try:
        real_cloud.update_movement(1.0)
        check(real_cloud.rect.topleft == start, "a pinned real cloud ignores movement input")
        check(real_cloud.pinned, "cloud remains pinned during the pin window")
        real_cloud.update_movement(3.0)
        check(not real_cloud.pinned, "cloud frees itself after the pin window")
        real_cloud.update_movement(1.0)
        check(real_cloud.rect.x > start[0], "freed cloud moves again")
    finally:
        pygame.key.get_pressed = old_get_pressed

    surf = fresh_surface()
    real_cloud.draw_rain(surf)
    surf.blit(real_cloud.image, real_cloud.rect)
    check(True, "pinned cloud art draws without crashing")


# ── Director ──────────────────────────────────────────────────────────────────
def test_director():
    print("[director] cadence, active cap, and click routing")
    rng = random.Random(5)
    slots = make_slots(planted={0, 9}, sun_lovers={4})
    director = MiniBossDirector(rng=rng)

    elig = set(MiniBossDirector._eligible_types(slots, []))
    check(elig == {"mole", "locust", "glare"}, "cloudless busy field excludes vine")
    elig_with_cloud = set(MiniBossDirector._eligible_types(slots, [FakeCloud(center=(slots[0].rect.centerx, 120))]))
    check(elig_with_cloud == {"mole", "locust", "glare", "vine"}, "vine is eligible when crops and a free cloud exist")
    pinned_cloud = FakeCloud(center=(slots[0].rect.centerx, 120))
    pinned_cloud.pin(1.0)
    check("vine" not in MiniBossDirector._eligible_types(slots, [pinned_cloud]), "vine is ineligible while a cloud is already pinned")

    a = director.force_spawn("mole", slots=slots, clouds=[], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    b = director.force_spawn("wisp", slots=slots, clouds=[], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    c = director.force_spawn("glare", slots=slots, clouds=[], field_rect=FIELD_RECT, ground_rect=GROUND_RECT)
    check(a and b, "director spawns up to the cap")
    check(not c and director.active_count == int(MINIBOSS_MAX_ACTIVE),
          f"director caps active mini-bosses at {int(MINIBOSS_MAX_ACTIVE)}")

    # A left click on the mole (a click-counterable type) routes through.
    mole = next((m for m in director.active if isinstance(m, BurrowMole)), None)
    routed = director.handle_click(mole.rect.center) if mole else False
    check(routed, "director routes a click to the mole")

    # No crops -> nothing eligible (the director stays quiet on an empty field).
    empty = make_slots()
    check(MiniBossDirector._eligible_types(empty, []) == [], "no eligible mini-bosses on a bare field")


def main():
    test_mole()
    test_locust()
    test_glare()
    test_wisp()
    test_tangle_vine()
    test_director()

    print()
    if _FAILURES:
        print(f"RESULT: {len(_FAILURES)} FAILED")
        for f in _FAILURES:
            print("  - " + f)
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
