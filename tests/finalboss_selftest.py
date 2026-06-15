"""Headless self-test for the Inferno Titan finale boss."""

import os
import sys
import types
import random

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

from settings import SCREEN_W, SCREEN_H, SUN_X, SUN_Y  # noqa: E402
from finalboss import (  # noqa: E402
    InfernoTitan,
    PHASE_ORDER,
    PHASE_STORM,
    PHASE_CYCLONE,
    PHASE_DROUGHT,
    PHASE_FROST,
    PHASE_INFERNO,
    FIRE_FIRESTORM,
    FIRE_LAVA,
    INFERNO_FROST_FREEZE_SECONDS,
    INFERNO_FIRESTORM_SCORCH_SECONDS,
    INFERNO_LAVA_SALT_SECONDS,
)

DT = 1.0 / 30.0
_FAILURES = []


def check(condition, label):
    print(("  ok  " if condition else " FAIL ") + label)
    if not condition:
        _FAILURES.append(label)


class FakeSlot:
    def __init__(self, x, y=440, planted=True, product_name="Carrot", yield_=1):
        self.rect = pygame.Rect(0, 0, 76, 76)
        self.rect.center = (x, y)
        self.seed = types.SimpleNamespace(product_name=product_name, harvest_yield=yield_) if planted else None
        self.dead = False
        self.water = 50.0
        self.sun = 50.0
        self.growth_stage = 2
        self._growth_frames = 2.0
        self._frozen_seconds = 0.0
        self._scorch_seconds = 0.0
        self._salted_seconds_remaining = 0.0
        self._quality_eligible = True

    def strike_lightning(self, salt_seconds=0.0):
        if self.seed is None or self.dead:
            return
        self.dead = True
        if salt_seconds:
            self.salt(salt_seconds)

    def scorch(self, seconds, water_loss=0.0):
        self._scorch_seconds = max(self._scorch_seconds, float(seconds))
        self.water = max(0.0, self.water - float(water_loss))

    def salt(self, seconds):
        self._salted_seconds_remaining = max(self._salted_seconds_remaining, float(seconds))


class FakeCloud:
    def __init__(self, center, size=(160, 80), raining=True):
        self.rect = pygame.Rect(0, 0, *size)
        self.rect.center = center
        self.raining = raining

    def covers_sun(self, sun_rect):
        return self.rect.colliderect(sun_rect)


def make_slots(all_planted=True):
    slots = []
    for i in range(10):
        planted = all_planted or i % 2 == 0
        product = "Tomato" if i == 4 else "Carrot"
        slots.append(FakeSlot(80 + i * 92, planted=planted, product_name=product))
    return slots


def covers(cloud, x):
    return cloud.rect.left <= x <= cloud.rect.right


def step(titan, surface, slots, clouds):
    titan.update_battle(DT, slots=slots, clouds=clouds)
    titan.draw_body(surface)
    titan.draw_warning(surface, slots=slots)
    titan.draw_bolt(surface)


def run_to_warning(titan, surface, slots, clouds, max_frames=600):
    for _ in range(max_frames):
        step(titan, surface, slots, clouds)
        if titan._warning_remaining > 0.0:
            return True
    return False


def run_to_flash(titan, surface, slots, clouds, max_frames=240):
    prev = titan._bolt_flash_remaining
    for _ in range(max_frames):
        step(titan, surface, slots, clouds)
        if titan._bolt_flash_remaining > 0.0 and prev <= 0.0:
            return True
        prev = titan._bolt_flash_remaining
    return False



def run_to_result(titan, surface, slots, clouds, max_frames=240):
    titan._last_strike_result = None
    for _ in range(max_frames):
        step(titan, surface, slots, clouds)
        if titan._last_strike_result is not None and titan._warning_remaining <= 0.0:
            return True
    return False

def force_phase(titan, phase, ability=None):
    titan.current_phase = phase
    titan._phase_index = PHASE_ORDER.index(phase)
    titan._fire_ability = ability
    titan._target_slot_index = None
    titan._target_x = None
    titan._warning_remaining = 0.0
    titan._cooldown_remaining = 0.0
    titan._mark_indices = []
    titan._fire_marks = []


def cloud_for_slot(slots, idx, raining=True):
    return FakeCloud((slots[idx].rect.centerx, 150), raining=raining)


def scenario_headless_game_constructs():
    print("[0] headless Game construction")
    import game as game_mod
    from game import Game

    save_path = os.path.join(_REPO_ROOT, f"ptg_final_{os.getpid()}.json")
    game_mod.SAVE_PATH = save_path
    if os.path.exists(save_path):
        os.remove(save_path)
    try:
        g = Game(new_game=True)
        check(len(g.slots) == 10, "Game constructed headlessly with 10 slots")
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)
    print()


def scenario_phase_rotation():
    print("[1] phase rotation")
    titan = InfernoTitan(rng=random.Random(1))
    titan.force_spawn_now()
    seen = [titan.current_phase]
    for _ in range(len(PHASE_ORDER) - 1):
        titan._advance_phase()
        seen.append(titan.current_phase)
    check(tuple(seen) == PHASE_ORDER, f"rotation visits all phases in order: {seen}")
    titan._advance_phase()
    check(titan.current_phase == PHASE_ORDER[0], "rotation wraps to storm")
    print()


def scenario_borrowed_phases():
    print("[2] borrowed phase block rules")
    surface = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

    for phase in (PHASE_STORM, PHASE_CYCLONE, PHASE_DROUGHT, PHASE_FROST):
        titan = InfernoTitan(rng=random.Random(2))
        slots = make_slots(all_planted=True)
        titan.force_spawn_now()
        force_phase(titan, phase)
        clouds = []
        check(run_to_warning(titan, surface, slots, clouds), f"{phase} telegraphs")

        if phase == PHASE_DROUGHT:
            clouds = [FakeCloud((SUN_X, SUN_Y), size=(150, 120), raining=False)]
            hp_before = titan.hp
            check(run_to_flash(titan, surface, slots, clouds), "drought resolves")
            check(titan._last_strike_result in ("block", "perfect"), "drought blocks by covering the sun")
            check(titan.hp < hp_before, "drought block damages boss")
            continue

        if phase == PHASE_FROST:
            marks = list(titan._mark_indices)
            check(len(marks) >= 2, "frost marks multiple slots")
            clouds = [cloud_for_slot(slots, marks[0])]
            uncovered = [i for i in marks if not any(covers(c, slots[i].rect.centerx) for c in clouds)]
            check(run_to_flash(titan, surface, slots, clouds), "frost resolves")
            hits = titan.pop_unblocked_hits()
            check(sorted(hits) == sorted(uncovered), "frost unblocked marks are reported")
            if uncovered:
                check(slots[uncovered[0]]._frozen_seconds == INFERNO_FROST_FREEZE_SECONDS, "frost freezes unblocked marks")
            continue

        target = titan._target_slot_index
        assert target is not None
        raining = phase == PHASE_CYCLONE
        clouds = [cloud_for_slot(slots, target, raining=raining)]
        hp_before = titan.hp
        check(run_to_flash(titan, surface, slots, clouds), f"{phase} resolves")
        check(titan._last_strike_result in ("block", "perfect"), f"{phase} blocks with correct cloud rule")
        check(titan.hp < hp_before, f"{phase} block damages boss")

        if phase == PHASE_CYCLONE:
            titan2 = InfernoTitan(rng=random.Random(3))
            slots2 = make_slots(all_planted=True)
            titan2.force_spawn_now()
            force_phase(titan2, PHASE_CYCLONE)
            run_to_warning(titan2, surface, slots2, [])
            target2 = titan2._target_slot_index
            clouds2 = [cloud_for_slot(slots2, target2, raining=False)]
            run_to_flash(titan2, surface, slots2, clouds2)
            check(titan2._last_strike_result == "hit", "cyclone ignores non-raining clouds")
    print()


def scenario_fire_abilities():
    print("[3] inferno fire abilities")
    surface = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

    titan = InfernoTitan(rng=random.Random(4))
    slots = make_slots(all_planted=True)
    titan.force_spawn_now()
    force_phase(titan, PHASE_INFERNO, FIRE_FIRESTORM)
    check(run_to_warning(titan, surface, slots, []), "firestorm telegraphs")
    marks = list(titan._mark_indices)
    check(len(marks) >= 4, f"firestorm marks a wide band ({len(marks)})")
    clouds = [cloud_for_slot(slots, marks[0]), cloud_for_slot(slots, marks[1])]
    uncovered = [i for i in marks if not any(covers(c, slots[i].rect.centerx) for c in clouds)]
    check(run_to_flash(titan, surface, slots, clouds), "firestorm resolves")
    check(sorted(titan.pop_unblocked_hits()) == sorted(uncovered), "firestorm reports only uncovered marks")
    check(any(slots[i]._scorch_seconds >= INFERNO_FIRESTORM_SCORCH_SECONDS for i in uncovered), "firestorm scorches uncovered marks")
    check(sum(1 for s in slots if s.dead) < len(slots), "firestorm never kills the whole field")

    titan_blocked = InfernoTitan(rng=random.Random(5))
    slots_blocked = make_slots(all_planted=True)
    titan_blocked.force_spawn_now()
    force_phase(titan_blocked, PHASE_INFERNO, FIRE_FIRESTORM)
    run_to_warning(titan_blocked, surface, slots_blocked, [])
    marks_blocked = list(titan_blocked._mark_indices)
    all_clouds = [cloud_for_slot(slots_blocked, i) for i in marks_blocked]
    hp_before = titan_blocked.hp
    run_to_flash(titan_blocked, surface, slots_blocked, all_clouds)
    check(titan_blocked._last_strike_result in ("block", "perfect"), "firestorm is fully blockable with enough positioned clouds")
    check(titan_blocked.hp < hp_before, "blocked firestorm damages boss")

    titan_lava = InfernoTitan(rng=random.Random(6))
    slots_lava = make_slots(all_planted=True)
    titan_lava.force_spawn_now()
    force_phase(titan_lava, PHASE_INFERNO, FIRE_LAVA)
    check(run_to_warning(titan_lava, surface, slots_lava, []), "lava surge telegraphs")
    target = titan_lava._target_slot_index
    check(run_to_flash(titan_lava, surface, slots_lava, []), "lava surge resolves unblocked")
    check(target in titan_lava.pop_unblocked_hits(), "lava surge reports its hit slot")
    check(slots_lava[target]._salted_seconds_remaining == INFERNO_LAVA_SALT_SECONDS, "lava surge salts unblocked slot")
    check(slots_lava[target].dead is False, "lava surge does not instant-kill")

    titan_lava_block = InfernoTitan(rng=random.Random(7))
    slots_lava_block = make_slots(all_planted=True)
    titan_lava_block.force_spawn_now()
    force_phase(titan_lava_block, PHASE_INFERNO, FIRE_LAVA)
    run_to_warning(titan_lava_block, surface, slots_lava_block, [])
    target = titan_lava_block._target_slot_index
    hp_before = titan_lava_block.hp
    run_to_flash(titan_lava_block, surface, slots_lava_block, [cloud_for_slot(slots_lava_block, target)])
    check(titan_lava_block._last_strike_result in ("block", "perfect"), "lava surge is blockable by covering the slot")
    check(titan_lava_block.hp < hp_before, "blocked lava surge damages boss")
    print()


def scenario_combo_draw_retreat():
    print("[4] perfect block, drawing, and retreat")
    surface = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    titan = InfernoTitan(rng=random.Random(8))
    slots = make_slots(all_planted=True)
    titan.force_spawn_now()
    titan._hp = 1
    force_phase(titan, PHASE_STORM)
    check(run_to_warning(titan, surface, slots, []), "storm warning before finishing block")
    target = titan._target_slot_index
    run_to_result(titan, surface, slots, [cloud_for_slot(slots, target)])
    check(titan._last_strike_result == "perfect", "perfect block result survives on final boss")
    check(titan.pop_blocks() >= 1, "perfect block records a block")
    check(titan.state in (titan.STATE_RETREATING, titan.STATE_WAITING) and titan.hp <= 0, "boss reaches retreat after HP hits zero")
    for _ in range(20):
        step(titan, surface, slots, [])
    check(True, "draw_body, draw_warning, and draw_bolt did not crash")
    print()


def main():
    scenario_headless_game_constructs()
    scenario_phase_rotation()
    scenario_borrowed_phases()
    scenario_fire_abilities()
    scenario_combo_draw_retreat()

    if _FAILURES:
        print(f"RESULT: {len(_FAILURES)} FAILED")
        for failure in _FAILURES:
            print("  - " + failure)
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
