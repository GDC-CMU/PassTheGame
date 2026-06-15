"""Headless self-test for Inventory and Market overlays."""

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
from game import Game, TOOL_SCARECROW  # noqa: E402
from market import THREAT_GROUND_CRITTER  # noqa: E402

_FAILURES = []


def check(condition, label):
    print(("  ok  " if condition else " FAIL ") + label)
    if not condition:
        _FAILURES.append(label)


def make_game(name, new=True):
    save_dir = os.path.join(_REPO_ROOT, ".test_saves")
    os.makedirs(save_dir, exist_ok=True)
    game_mod.SAVE_PATH = os.path.join(save_dir, name)
    if new and os.path.exists(game_mod.SAVE_PATH):
        os.remove(game_mod.SAVE_PATH)
    return Game(new_game=new)


def test_overlay_toggles_and_draw():
    print("[1] overlays")
    g = make_game("market_overlay.json")
    g.inventory = {"Carrot": 2}
    g._draw_ui_panel()
    check(not g._inventory_rows, "right panel has no inline inventory rows")
    g._toggle_inventory_overlay()
    check(g._show_inventory_overlay, "inventory overlay toggles on")
    g._draw()
    check(g._inventory_rows, "inventory overlay draws rows")
    g._toggle_inventory_overlay()
    check(not g._show_inventory_overlay, "inventory overlay toggles off")
    g._toggle_market_overlay()
    check(g._show_market_overlay, "market overlay toggles on")
    g._draw()
    check(True, "draw succeeds with market overlay")


def test_tool_unlock_purchase_persists():
    print("[2] tool unlock purchase")
    g = make_game("market_tool.json")
    check(not g._is_tool_unlocked(TOOL_SCARECROW), "scarecrow starts locked")
    g._market.mark_threat(THREAT_GROUND_CRITTER)
    offer = next(o for o in g._market_offers() if o.kind == "tool" and o.item_id == TOOL_SCARECROW)
    g.money = offer.cost
    check(g._buy_market_offer(offer), "scarecrow unlock purchase succeeds")
    check(g._is_tool_unlocked(TOOL_SCARECROW), "scarecrow is unlocked")
    g.save_game(flash=False)
    reloaded = make_game("market_tool.json", new=False)
    check(reloaded._is_tool_unlocked(TOOL_SCARECROW), "tool unlock persisted")


def test_everbloom_and_featured_seed():
    print("[3] rare seeds")
    g = make_game("market_rare.json")
    g._endgame.everbloom.unlocked = True
    offers = g._market_offers()
    check(any(o.kind == "seed" and o.item_id == "Everbloom" for o in offers), "Everbloom appears after quest")

    g._market.force_featured_seed("Apple")
    offers = g._market_offers()
    check(any(o.kind == "seed" and o.item_id == "Apple" and o.reason == "Featured rare seed" for o in offers),
          "featured rare slot can surface a locked crop")


def main():
    test_overlay_toggles_and_draw()
    test_tool_unlock_purchase_persists()
    test_everbloom_and_featured_seed()
    if _FAILURES:
        print("\nRESULT: FAIL")
        for failure in _FAILURES:
            print(" - " + failure)
        raise SystemExit(1)
    print("\nRESULT: ALL PASS")


if __name__ == "__main__":
    main()
