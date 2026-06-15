"""Headless self-test for flying crows and the Bell tool."""

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

from crows import BellTool, CrowFlock, FlyingCrowThief  # noqa: E402
from settings import CROW_GRAB_BEAT_SECONDS, CROW_MURDER_MIN_ACTIVE  # noqa: E402

_FAILURES = []


def check(condition, label):
    print(("  ok  " if condition else " FAIL ") + label)
    if not condition:
        _FAILURES.append(label)


class Seed:
    def __init__(self, product_name, harvest_yield=1):
        self.product_name = product_name
        self.harvest_yield = harvest_yield


class Slot:
    def __init__(self, x, y, seed=None):
        self.rect = pygame.Rect(x, y, 48, 48)
        self.seed = seed
        self.dead = False
        self.has_scarecrow = False
        self.cleared = False

    def clear(self):
        self.seed = None
        self.dead = False
        self.cleared = True

    def remove_scarecrow(self):
        self.has_scarecrow = False


class FixedRandom:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


FIELD = pygame.Rect(0, 0, 640, 480)
GROUND = pygame.Rect(0, 330, 640, 150)


def make_slots():
    y = 330
    return [
        Slot(64 + i * 56, y, None)
        for i in range(8)
    ]


def step_crow(crow, slots, total=8.0, dt=0.05, murder=False):
    frames = int(total / dt)
    for _ in range(frames):
        crow.update(dt, slots=slots, field_rect=FIELD, ground_rect=GROUND, murder_active=murder)


def test_spawn_dive_grab_steal_and_click():
    print("[1] crow lifecycle and click scare")
    slots = make_slots()
    slots[2].seed = Seed("Carrot")
    crow = FlyingCrowThief()
    check(crow.force_spawn(slots=slots, field_rect=FIELD, ground_rect=GROUND), "crow force spawned")

    saw_dive = False
    grab_frames = 0
    for _ in range(180):
        crow.update(0.05, slots=slots, field_rect=FIELD, ground_rect=GROUND)
        saw_dive = saw_dive or crow.state == crow.STATE_DIVE
        if crow.is_grab_window:
            grab_frames += 1
        if crow.stole_crop:
            break
    check(saw_dive, "crow entered dive state")
    check(grab_frames * 0.05 >= max(0.5, float(CROW_GRAB_BEAT_SECONDS)) - 0.05, "grab window lasted at least half a second")
    check(slots[2].seed is None and slots[2].cleared, "crow stole and cleared the crop")

    slots[2].seed = Seed("Carrot")
    slots[2].cleared = False
    crow = FlyingCrowThief()
    crow.force_spawn(slots=slots, field_rect=FIELD, ground_rect=GROUND)
    clicked_flee = False
    for _ in range(80):
        crow.update(0.05, slots=slots, field_rect=FIELD, ground_rect=GROUND)
        if crow.active:
            event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": crow.rect.center})
            if crow.handle_click(event, field_rect=FIELD):
                clicked_flee = crow.state == crow.STATE_FLEE
                break
    step_crow(crow, slots, total=2.0)
    check(slots[2].seed is not None, "clicked crow fled without stealing")
    check(clicked_flee, "clicked crow entered flee path")


def test_render_shadow_and_telegraph():
    print("[2] shadow, telegraph, and draw safety")
    slots = make_slots()
    slots[3].seed = Seed("Tomato")
    crow = FlyingCrowThief()
    crow.force_spawn(slots=slots, field_rect=FIELD, ground_rect=GROUND)
    surface = pygame.Surface((640, 480), pygame.SRCALPHA)
    crow.draw(surface)
    for _ in range(80):
        crow.update(0.05, slots=slots, field_rect=FIELD, ground_rect=GROUND)
        crow.draw(surface)
    alpha_sum = pygame.surfarray.array_alpha(surface).sum()
    check(alpha_sum > 0, "draw produced visible shadow or crow pixels")


def test_raid_spawn_bias():
    print("[3] raid spawn bias")
    slots = make_slots()
    slots[1].seed = Seed("Carrot")

    base = FlyingCrowThief(rng=FixedRandom(0.04))
    base.update(1.0, slots=slots, field_rect=FIELD, ground_rect=GROUND)
    check(not base.active, "base spawn stayed rare at the same roll")

    raid = FlyingCrowThief(rng=FixedRandom(0.04))
    raid.set_raid_active(True)
    raid.update(1.0, slots=slots, field_rect=FIELD, ground_rect=GROUND)
    check(raid.active, "raid multiplier spawned on the same roll")


def test_scarecrow_rules_and_murder():
    print("[4] scarecrow deterrence and murder attack")
    slots = make_slots()
    slots[1].has_scarecrow = True
    slots[2].seed = Seed("Tomato")
    slots[6].seed = Seed("Carrot")

    lone = FlyingCrowThief()
    lone.force_spawn(slots=slots, field_rect=FIELD, ground_rect=GROUND)
    check(lone.target_slot_index == 6, "lone crow avoided scarecrow protected crop")

    flock = CrowFlock(max_active=int(CROW_MURDER_MIN_ACTIVE))
    for _ in range(int(CROW_MURDER_MIN_ACTIVE)):
        flock.force_spawn(slots=slots, field_rect=FIELD, ground_rect=GROUND)
    check(flock.murder_active, "three active crows formed a murder")
    for _ in range(240):
        flock.update(0.05, slots=slots, field_rect=FIELD, ground_rect=GROUND)
        if not slots[1].has_scarecrow:
            break
    check(not slots[1].has_scarecrow, "murder removed the scarecrow")
    for _ in range(260):
        flock.update(0.05, slots=slots, field_rect=FIELD, ground_rect=GROUND)
        if slots[2].seed is None:
            break
    check(slots[2].seed is None, "murder stole after the scarecrow fell")


def test_bell():
    print("[5] Bell scare and cooldown")
    slots = make_slots()
    slots[2].seed = Seed("Tomato")
    flock = CrowFlock(max_active=2)
    flock.force_spawn(slots=slots, field_rect=FIELD, ground_rect=GROUND)
    flock.force_spawn(slots=slots, field_rect=FIELD, ground_rect=GROUND)
    bell = BellTool(cooldown_seconds=8.0)
    scared = bell.ring(list(flock), field_rect=FIELD)
    check(scared == 2, "Bell scared all active flying thieves")
    check(all(c.state == c.STATE_FLEE for c in flock), "Bell put every active crow in flee state")
    check(not bell.ready, "Bell entered cooldown")
    check(bell.ring(list(flock), field_rect=FIELD) == 0, "Bell cannot fire during cooldown")
    bell.update(8.0)
    check(bell.ready, "Bell became ready after cooldown")


def main():
    test_spawn_dive_grab_steal_and_click()
    test_render_shadow_and_telegraph()
    test_raid_spawn_bias()
    test_scarecrow_rules_and_murder()
    test_bell()
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
