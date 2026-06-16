"""Headless self-test for Pass the Game.

Run it from the repo root with no display:

    python3 tests/selftest.py

It builds the game with dummy SDL drivers (no window, no audio) and checks the
things that are easy to break and annoying to catch by eye:

  1. Per-slot state is independent even though PlantType objects are shared
     singletons (the class of bug that once made every Apple regrow wrongly).
  2. save_game / load_game round-trips money, inventory, golden inventory,
     planted crops and scarecrows.
  3. The water/sun simulation runs at the same real-time rate regardless of
     frame rate (the dt fix), and one very long frame can't drain a crop more
     than MAX_FRAME_DT allows.

Exit code is 0 if everything passes, 1 otherwise, so it can gate a commit.
This intentionally uses no test framework so anyone can run it with plain Python.
"""

import os
import sys

# Headless: no window, no sound. Must be set before pygame is imported.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Allow running from anywhere: put the repo root on the import path.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pygame  # noqa: E402

pygame.init()
# Never open a real fullscreen/scaled window during tests.
_orig_set_mode = pygame.display.set_mode
pygame.display.set_mode = lambda size, *a, **k: _orig_set_mode(size)

import settings as S  # noqa: E402
from game import Game  # noqa: E402
import game as game_mod  # noqa: E402  (for redirecting the module-level SAVE_PATH)
from settings import RAIN_INTENSITY_OFF  # noqa: E402

_FAILURES = []


def check(condition, label):
    print(("  ok  " if condition else " FAIL ") + label)
    if not condition:
        _FAILURES.append(label)


class _FakeClock:
    """Stand-in for pygame.time.Clock that reports a fixed frame time."""

    def __init__(self, frame_ms):
        self._ms = float(frame_ms)

    def get_time(self):
        return self._ms

    def tick(self, *_a, **_k):
        return self._ms


def _first_basic_seed(game):
    """A normal, immediately-plantable crop to test with."""
    for seed in game.seeds:
        if int(getattr(seed, "unlock_at", 0)) <= 0 and not getattr(seed, "seed_item_name", None):
            return seed
    return game.seeds[0]


def test_independent_slot_state(game):
    print("[1] independent per-slot state (shared-singleton guard)")
    seed = _first_basic_seed(game)
    a, b = game.slots[0], game.slots[1]
    a.clear()
    b.clear()
    a.plant(seed)
    b.plant(seed)

    # Same shared type, but state lives on the slot.
    check(a.seed is b.seed, "both slots reference the same shared PlantType")

    a.water = 12.0
    b.water = 88.0
    a._quality_eligible = False
    a.growth_stage = seed.growth_stages  # make A harvestable

    check(b.water == 88.0, "mutating slot A water does not change slot B")
    check(b._quality_eligible is True, "slot A quality flag does not leak to slot B")
    check(not b.harvestable, "slot A growth does not advance slot B")
    # The shared type must not have grown per-plant attributes.
    check(not hasattr(seed, "water"), "shared PlantType did not gain per-plant 'water'")

    a.clear()
    b.clear()


def test_save_load_round_trip(game):
    print("[2] save / load round-trip")
    seed = _first_basic_seed(game)
    pname = seed.product_name

    game.money = 1234
    game.inventory = {pname: 5}
    game._golden_inventory = {pname: 3}
    game.slots[4].clear()
    game.slots[4].plant(seed)
    game.slots[8].clear()
    game.slots[8].place_scarecrow(45.0)
    game.save_game(flash=False)

    pygame.display.set_mode = lambda size, *a, **k: _orig_set_mode(size)
    reloaded = Game(new_game=False)
    reloaded.load_game()

    check(reloaded.money == 1234, "money survived save/load")
    check(reloaded.inventory.get(pname, 0) == 5, "inventory survived save/load")
    check(reloaded._golden_inventory.get(pname, 0) == 3, "golden inventory survived save/load")
    check(reloaded.slots[4].planted, "planted crop survived save/load")
    check(reloaded.slots[8].has_scarecrow, "scarecrow survived save/load")


def _run_water_only(game, slot, seed, frame_ms, frames, start_water=80.0):
    """Re-plant the slot and step the plant sim `frames` times at a fixed frame
    time, with nothing raining, and return the resulting water level."""
    slot.clear()
    slot.plant(seed)
    slot.water = start_water
    slot.sun = 50.0
    game._weather_event = "None"
    game.clock = _FakeClock(frame_ms)
    for _ in range(frames):
        game._update_plants()
    return slot.water


def test_framerate_convergence(game):
    print("[3] framerate-independent water sim (the dt fix)")
    seed = _first_basic_seed(game)
    slot = game.slots[0]
    # Make sure nothing in the field rains on the slot during the test.
    for c in game.clouds:
        c.rain_intensity = int(RAIN_INTENSITY_OFF)

    # Two seconds of wall-clock at 60 FPS vs 30 FPS should drain the same amount.
    water_60 = _run_water_only(game, slot, seed, 1000.0 / 60.0, 120)
    water_30 = _run_water_only(game, slot, seed, 1000.0 / 30.0, 60)
    print(f"      60fps -> {water_60:.3f}, 30fps -> {water_30:.3f}")
    check(abs(water_60 - water_30) < 0.5, "60 FPS and 30 FPS converge to the same water")
    check(water_60 < 80.0, "water actually drained (sanity)")

    # One enormous frame (a stall) must be clamped, not apply 2 seconds at once.
    drained = 80.0 - _run_water_only(game, slot, seed, 2000.0, 1)
    max_expected = float(S.WATER_LOSS) * float(S.FPS) * float(S.MAX_FRAME_DT) * 1.5 + 0.01
    print(f"      single 2s stall drained {drained:.3f} (cap ~{max_expected:.3f})")
    check(drained <= max_expected, "a long stall frame is clamped by MAX_FRAME_DT")

    slot.clear()


def test_buy_locked_seed(game):
    print("[6] buying a locked seed works (no missing-method crash)")
    check(hasattr(game, "_confirm_purchase"), "_confirm_purchase method exists")
    locked = [s for s in game.seeds
              if int(getattr(s, "unlock_at", 0)) > 0 and type(s).__name__ not in game._unlocked_seeds]
    check(bool(locked), "there is at least one locked seed to test")
    if not locked:
        return
    seed = locked[0]
    game.money = 999999
    game._pending_purchase = seed
    game._show_purchase_confirm = True
    game._confirm_purchase()
    check(type(seed).__name__ in game._unlocked_seeds, "the locked seed unlocked after purchase")
    check(not game._show_purchase_confirm, "the purchase dialog closed after buying")


def main():
    # Use a per-process save file so parallel selftest runs (common when several
    # agents verify at once) never clobber a shared savegame.json mid round-trip.
    import tempfile
    game_mod.SAVE_PATH = os.path.join(tempfile.gettempdir(), f"ptg_selftest_{os.getpid()}.json")
    save_path = game_mod.SAVE_PATH
    if os.path.exists(save_path):
        os.remove(save_path)

    game = Game(new_game=True)
    try:
        test_independent_slot_state(game)
        test_framerate_convergence(game)
        test_buy_locked_seed(game)
        test_save_load_round_trip(game)
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)

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
