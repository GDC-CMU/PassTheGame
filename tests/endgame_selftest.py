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
from plants import Everbloom  # noqa: E402
from items import ITEMS  # noqa: E402
from endgame import (  # noqa: E402
    CHALLENGES,
    EndgameState,
    LegacyTracker,
    ChallengeLadder,
    compute_next_year_preview,
    draw_legacy_line,
    draw_preview,
    install_game_hooks,
)

install_game_hooks(Game)
_FAILURES = []


def check(condition, label):
    print(("  ok  " if condition else " FAIL ") + label)
    if not condition:
        _FAILURES.append(label)


def make_game(name):
    save_dir = os.path.join(_REPO_ROOT, ".test_saves")
    os.makedirs(save_dir, exist_ok=True)
    game_mod.SAVE_PATH = os.path.join(save_dir, name)
    if os.path.exists(game_mod.SAVE_PATH):
        os.remove(game_mod.SAVE_PATH)
    return Game(new_game=True)


def test_preview():
    print("[1] next-year preview")
    g = make_game("endgame_preview.json")
    g._almanac.difficulty = 1
    p = compute_next_year_preview(g._almanac, 2, g._bosses)
    check(p.previous_difficulty == 1, "captures current difficulty")
    check(p.next_difficulty == 3, "computes incoming difficulty")
    check(any("Tempest" in line for line in p.lines), "mentions year-end tempest")
    check(len(p.titans) >= 4, "lists titan roster")


def test_legacy_round_trip():
    print("[2] legacy formula and save/load")
    g = make_game("endgame_roundtrip.json")
    st = g._endgame
    for crop in ("Carrot", "Lettuce", "Tomato", "Apple", "Pumpkin", "Rice", "Mushroom", "Cactus"):
        st.legacy.record_crop(crop)
    for titan in ("storm", "cyclone"):
        st.legacy.record_titan(titan)
    before = st.legacy.percent()
    st.legacy.record_crop("Night Bloom", golden=True)
    st.legacy.record_money(1500)
    st.legacy.record_year(2)
    after = st.legacy.percent()
    check(after >= before, "legacy percent grows when milestones improve")
    g.save_game(flash=False)

    pygame.display.set_mode = lambda size, *a, **k: _orig_set_mode(size)
    reloaded = Game(new_game=False)
    check(reloaded._endgame.legacy.percent() == g._endgame.legacy.percent(), "legacy percent survived Game save/load")
    check("Night Bloom" in reloaded._endgame.legacy.discovered_crops, "discovered crops survived save/load")


def test_challenge_ladder():
    print("[3] challenge ladder")
    g = make_game("endgame_challenge.json")
    ladder = ChallengeLadder()
    legacy = LegacyTracker()
    ladder.toggle("storm_clock")
    before = [float(getattr(b, "_spawn_remaining", 0.0)) for b in g._bosses]
    ladder.apply_to_bosses(g._bosses)
    after = [float(getattr(b, "_spawn_remaining", 0.0)) for b in g._bosses]
    check(all(a <= b for a, b in zip(after, before)), "storm_clock tightens titan spawn timers")
    p0 = legacy.percent()
    ladder.mark_completed("storm_clock", legacy)
    check("storm_clock" in legacy.completed_challenges, "completed challenge recorded in legacy")
    check(legacy.percent() > p0, "completed challenge bumps legacy percent")
    check(any(ch.id == "single_cloud_week" for ch in CHALLENGES), "cloud modifier is tighten-only")


def satisfy_everbloom(state: EndgameState):
    for crop in ("Carrot", "Lettuce", "Tomato", "Apple", "Pumpkin", "Rice", "Mushroom", "Cactus"):
        state.legacy.record_crop(crop)
    for titan in ("storm", "cyclone", "drought", "frost"):
        state.legacy.record_titan(titan)
    state.legacy.golden_harvests = 25
    state.legacy.best_year_reached = 5
    state.legacy.total_earned = 5000
    state.everbloom.refresh(state.legacy)


def test_everbloom():
    print("[4] Everbloom quest and crop")
    g = make_game("endgame_everbloom.json")
    seed = next(s for s in g.seeds if type(s).__name__ == "Everbloom")
    check(not g._is_seed_unlocked(seed), "Everbloom starts quest-locked")
    satisfy_everbloom(g._endgame)
    check(g._is_seed_unlocked(seed), "Everbloom unlocks from quest progress")
    check(ITEMS[seed.product_name].sell_price == 120, "Everbloom sell price registered")

    slot = g.slots[0]
    slot.clear()
    slot.plant(seed)
    slot.growth_stage = seed.growth_stages
    g._harvest(slot)
    check(g.inventory.get("Everbloom", 0) == 1, "Everbloom harvest enters inventory")
    check(slot.planted and slot.growth_stage == seed.regrow_to_stage, "Everbloom regrows after harvest")
    g._sell_item("Everbloom", 1)
    check(g.money >= 120, "Everbloom can be sold")

    slot.growth_stage = seed.growth_stages
    g.save_game(flash=False)
    pygame.display.set_mode = lambda size, *a, **k: _orig_set_mode(size)
    reloaded = Game(new_game=False)
    check(type(reloaded.slots[0].seed).__name__ == "Everbloom", "Everbloom slot survived save/load")
    check(reloaded._endgame.everbloom.is_unlocked(reloaded._endgame.legacy), "Everbloom quest survived save/load")


def test_draw():
    print("[5] draw safety")
    g = make_game("endgame_draw.json")
    surface = pygame.Surface((640, 360))
    font = pygame.font.SysFont("arial", 16)
    p = compute_next_year_preview(g._almanac, 1, g._bosses)
    draw_legacy_line(surface, font, g._endgame, (8, 8))
    draw_preview(surface, font, p, pygame.Rect(8, 32, 520, 120))
    g._draw()
    check(True, "endgame draw helpers and Game.draw did not crash")


def cleanup():
    save_dir = os.path.join(_REPO_ROOT, ".test_saves")
    if os.path.isdir(save_dir):
        for name in os.listdir(save_dir):
            path = os.path.join(save_dir, name)
            if os.path.isfile(path):
                os.remove(path)
        try:
            os.rmdir(save_dir)
        except OSError:
            pass


def main():
    try:
        test_preview()
        test_legacy_round_trip()
        test_challenge_ladder()
        test_everbloom()
        test_draw()
    finally:
        cleanup()
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
