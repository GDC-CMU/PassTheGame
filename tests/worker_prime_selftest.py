"""Headless checks for worker_prime.py.

Run from the repo root:

    python3 tests/worker_prime_selftest.py
"""

import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pygame  # noqa: E402

pygame.init()
pygame.font.init()
_orig_set_mode = pygame.display.set_mode
pygame.display.set_mode = lambda size, *a, **k: _orig_set_mode(size)

import game as game_mod  # noqa: E402
from game import Game  # noqa: E402
from items import ITEMS  # noqa: E402
from settings import GOLDEN_VALUE_MULT, PRIME_MAX_BONUS_MULT, PRIME_MAX_SECONDS, PRIME_SPOIL_SECONDS, WORKER_HIRE_COST  # noqa: E402
from worker_prime import (  # noqa: E402
    AutoHarvesterWorker,
    calculate_slot_sale_value,
    draw_prime_overlays,
    prime_load_slots,
    prime_save_slots,
    reset_slot_prime,
    update_prime_slots,
)


_FAILURES = []


def check(condition, label):
    print(("  ok  " if condition else " FAIL ") + label)
    if not condition:
        _FAILURES.append(label)


class FakePest:
    active = True

    def __init__(self, rect):
        self.rect = rect


def _save_path():
    root = os.path.join(_REPO_ROOT, ".test_saves")
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, f"worker_prime_{os.getpid()}.json")


def _fresh_game():
    pygame.display.set_mode = lambda size, *a, **k: _orig_set_mode(size)
    game_mod.SAVE_PATH = _save_path()
    if os.path.exists(game_mod.SAVE_PATH):
        os.remove(game_mod.SAVE_PATH)
    return Game(new_game=True)


def _seed(game):
    for seed in game.seeds:
        if int(getattr(seed, "unlock_at", 0)) <= 0 and not getattr(seed, "seed_item_name", None):
            return seed
    return game.seeds[0]


def _make_ripe(slot, seed):
    slot.clear()
    reset_slot_prime(slot)
    slot.plant(seed)
    slot.growth_stage = seed.growth_stages


def test_worker_hire_save_load(game):
    print("[1] worker hire and save/load hooks")
    worker = AutoHarvesterWorker()
    game.money = int(WORKER_HIRE_COST) + 25
    hired = worker.hire(game)
    check(hired and worker.active, "worker can be hired")
    check(game.money == 25, "hire cost is paid")

    _make_ripe(game.slots[0], _seed(game))
    update_prime_slots(game.slots, 7.0)
    data = {"worker": worker.to_dict(), "prime_slots": prime_save_slots(game.slots)}
    with open(game_mod.SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)
    loaded_worker = AutoHarvesterWorker()
    with open(game_mod.SAVE_PATH, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    loaded_worker.from_dict(loaded["worker"])
    prime_load_slots(game.slots, loaded["prime_slots"])
    check(loaded_worker.active, "worker active state survives module save/load")
    check(calculate_slot_sale_value(game.slots[0]) > ITEMS[_seed(game).product_name].sell_price, "prime state survives module save/load")


def test_worker_harvests_for_money(game):
    print("[2] worker auto-harvests ripe crop into inventory")
    seed = _seed(game)
    slot = game.slots[0]
    _make_ripe(slot, seed)
    worker = AutoHarvesterWorker()
    game.money = int(WORKER_HIRE_COST)
    worker.hire(game)
    worker.x = float(slot.rect.centerx)
    worker.y = float(slot.rect.bottom + 36)
    product = seed.product_name
    have_before = game.inventory.get(product, 0) + game._golden_inventory.get(product, 0)
    for _ in range(12):
        worker.update(0.1, game, ground_pests=[])
    have_after = game.inventory.get(product, 0) + game._golden_inventory.get(product, 0)
    check(not slot.planted, "worker cleared the harvested crop")
    # The worker harvests like a player pluck: the crop goes to inventory (keeping
    # the Golden 2x and the player's sell timing), it does not auto-sell for cash.
    check(have_after > have_before, "worker added the crop to inventory")


def test_worker_keystone_guard(game):
    print("[3] worker does not touch water, sun, or clouds")
    seed = _seed(game)
    slot = game.slots[1]
    slot.clear()
    slot.plant(seed)
    slot.growth_stage = 1
    slot.water = 33.0
    slot.sun = 77.0
    cloud_state = sorted((c.rect.x, c.rect.y, c.rain_intensity) for c in game.clouds)
    worker = AutoHarvesterWorker()
    game.money = int(WORKER_HIRE_COST)
    worker.hire(game)
    for _ in range(5):
        worker.update(0.2, game, ground_pests=[])
    check(slot.water == 33.0 and slot.sun == 77.0, "worker did not change crop water or sun")
    check(cloud_state == sorted((c.rect.x, c.rect.y, c.rain_intensity) for c in game.clouds), "worker did not move or toggle clouds")


def test_snake_kills_worker(game):
    print("[4] ground pest collision disables worker")
    worker = AutoHarvesterWorker()
    game.money = int(WORKER_HIRE_COST)
    worker.hire(game)
    pest = FakePest(worker.rect.copy())
    worker.update(0.1, game, ground_pests=[pest])
    check((not worker.active) and worker.killed, "colliding pest kills the worker")


def test_prime_values_and_downside(game):
    print("[5] prime value, spoil downside, and golden stack")
    seed = _seed(game)
    slot = game.slots[2]
    _make_ripe(slot, seed)
    base = calculate_slot_sale_value(slot)
    update_prime_slots([slot], 12.0)
    mid = calculate_slot_sale_value(slot)
    check(mid > base, "prime raises value over time")

    _make_ripe(slot, seed)
    update_prime_slots([slot], PRIME_SPOIL_SECONDS + 0.5)
    check(slot.dead and calculate_slot_sale_value(slot) == 0, "ignored prime crop spoils into a loss")

    _make_ripe(slot, seed)
    slot._alive_seconds = 999.0
    slot._in_range_seconds = 999.0
    update_prime_slots([slot], PRIME_MAX_SECONDS)
    expected = round(ITEMS[seed.product_name].sell_price * seed.harvest_yield * GOLDEN_VALUE_MULT * (1.0 + PRIME_MAX_BONUS_MULT))
    actual = calculate_slot_sale_value(slot)
    check(actual == expected, "golden and prime multiply once each")


def test_draw_never_crashes(game):
    print("[6] draw helpers do not crash")
    surf = pygame.Surface((960, 600), pygame.SRCALPHA)
    seed = _seed(game)
    _make_ripe(game.slots[3], seed)
    update_prime_slots([game.slots[3]], 10.0)
    worker = AutoHarvesterWorker()
    game.money = int(WORKER_HIRE_COST)
    worker.hire(game)
    draw_prime_overlays(surf, game.slots)
    worker.draw(surf)
    check(True, "prime and worker drawing completed")


def main():
    game = _fresh_game()
    try:
        test_worker_hire_save_load(game)
        test_worker_harvests_for_money(game)
        test_worker_keystone_guard(game)
        test_snake_kills_worker(game)
        test_prime_values_and_downside(game)
        test_draw_never_crashes(game)
    finally:
        if os.path.exists(game_mod.SAVE_PATH):
            os.remove(game_mod.SAVE_PATH)
    print()
    if _FAILURES:
        print(f"RESULT: {len(_FAILURES)} FAILED")
        for failure in _FAILURES:
            print("  - " + failure)
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
