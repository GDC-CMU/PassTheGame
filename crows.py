from __future__ import annotations

import math
import random
from collections.abc import Sequence

import pygame

from items import ITEMS
from settings import (
    CRITTER_SPAWN_CHECK_SECONDS,
    CRITTER_SCARECROW_AVOID_RADIUS_SLOTS,
    CROW_ALTITUDE_PX,
    CROW_CLIMB_SECONDS,
    CROW_DIVE_SECONDS,
    CROW_FLEE_SPEED_PX_PER_SEC,
    CROW_GRAB_BEAT_SECONDS,
    CROW_HEIGHT,
    CROW_MAX_ACTIVE,
    CROW_MURDER_MIN_ACTIVE,
    CROW_RAID_SPAWN_MULT,
    CROW_SCARECROW_PECK_SECONDS,
    CROW_SPAWN_CHANCE,
    CROW_SPEED_PX_PER_SEC,
    CROW_WIDTH,
    BELL_COOLDOWN_SECONDS,
)


class FlyingCrowThief:
    STATE_INACTIVE = "inactive"
    STATE_FLY_IN = "fly_in"
    STATE_DIVE = "dive"
    STATE_GRAB = "grab"
    STATE_CLIMB = "climb"
    STATE_ATTACK_SCARECROW = "attack_scarecrow"
    STATE_FLEE = "flee"

    def __init__(self, *, rng: random.Random | None = None):
        self._rng = rng or random.Random()
        self._state = self.STATE_INACTIVE
        self._spawn_accum = 0.0
        self._anim_time = 0.0
        self._x = 0.0
        self._y = 0.0
        self._dive_from_y = 0.0
        self._phase_remaining = 0.0
        self._side = "left"
        self._direction = 1
        self._target_idx: int | None = None
        self._target_kind = "plant"
        self._stolen = False
        self._raid_active = False
        self._difficulty_scale = 1.0
        self._shadow_y = 0.0
        self.rect = pygame.Rect(0, 0, int(CROW_WIDTH), int(CROW_HEIGHT))
        self._juice_events: list[dict] = []

    @property
    def active(self) -> bool:
        return self._state != self.STATE_INACTIVE

    @property
    def state(self) -> str:
        return self._state

    @property
    def target_slot_index(self) -> int | None:
        return self._target_idx

    @property
    def is_grab_window(self) -> bool:
        return self._state == self.STATE_GRAB

    @property
    def stole_crop(self) -> bool:
        return self._stolen

    def set_raid_active(self, active: bool) -> None:
        self._raid_active = bool(active)

    def set_difficulty_scale(self, scale: float) -> None:
        self._difficulty_scale = max(0.0, float(scale))

    def force_spawn(
        self,
        *,
        slots: Sequence[object],
        field_rect: pygame.Rect,
        ground_rect: pygame.Rect,
        murder_active: bool = False,
    ) -> bool:
        if self.active:
            return False
        return self._spawn(slots, field_rect, murder_active=murder_active)

    def scare_away(self, *, field_rect: pygame.Rect) -> None:
        if not self.active:
            return
        self._begin_flee(field_rect)

    def pop_juice_events(self) -> list[dict]:
        events = self._juice_events
        self._juice_events = []
        return events

    def update(
        self,
        dt: float,
        *,
        slots: Sequence[object],
        field_rect: pygame.Rect,
        ground_rect: pygame.Rect,
        murder_active: bool = False,
    ) -> None:
        if dt <= 0.0:
            return
        self._anim_time += dt
        self._stolen = False

        if self._state == self.STATE_INACTIVE:
            self._spawn_accum += dt
            chance = float(CROW_SPAWN_CHANCE) * (float(CROW_RAID_SPAWN_MULT) if self._raid_active else 1.0) * self._difficulty_scale
            while self._spawn_accum >= float(CRITTER_SPAWN_CHECK_SECONDS):
                self._spawn_accum -= float(CRITTER_SPAWN_CHECK_SECONDS)
                if self._rng.random() < chance and self._spawn(slots, field_rect, murder_active=murder_active):
                    break
            return

        if murder_active and self._target_kind != "scarecrow" and self._nearest_scarecrow(slots) is not None:
            self._choose_scarecrow_target(slots)
            self._state = self.STATE_FLY_IN

        if self._state == self.STATE_FLEE:
            edge_x = -50.0 if self._side == "left" else float(field_rect.width) + 50.0
            self._move_toward(edge_x, max(10.0, self._y - 35.0), dt, speed=float(CROW_FLEE_SPEED_PX_PER_SEC))
            if self._x < -40.0 or self._x > field_rect.width + 40.0:
                self._deactivate()
            self._sync_rect()
            return

        if self._target_kind == "scarecrow":
            if not self._scarecrow_target_valid(slots):
                self._choose_plant_target(slots, ignore_scarecrow=murder_active)
                if self._target_idx is None:
                    self._begin_flee(field_rect)
                    self._sync_rect()
                    return
                self._state = self.STATE_FLY_IN
        elif not self._plant_target_valid(slots, ignore_scarecrow=murder_active):
            self._choose_plant_target(slots, ignore_scarecrow=murder_active)
            if self._target_idx is None:
                self._begin_flee(field_rect)
                self._sync_rect()
                return
            self._state = self.STATE_FLY_IN

        hover_x, hover_y = self._hover_point(slots, self._target_idx)
        crop_x, crop_y = self._crop_point(slots, self._target_idx)
        self._shadow_y = crop_y + 24.0

        if self._state == self.STATE_FLY_IN:
            if self._move_toward(hover_x, hover_y, dt, speed=float(CROW_SPEED_PX_PER_SEC)):
                self._state = self.STATE_DIVE
                self._dive_from_y = self._y
                self._phase_remaining = float(CROW_DIVE_SECONDS)
                self._juice_events.append({"kind": "dive", "pos": self.rect.center})
        elif self._state == self.STATE_DIVE:
            self._x = crop_x
            self._phase_remaining -= dt
            dur = max(0.001, float(CROW_DIVE_SECONDS))
            done = max(0.0, min(1.0, 1.0 - self._phase_remaining / dur))
            self._y = self._dive_from_y + (crop_y - self._dive_from_y) * done
            if self._phase_remaining <= 0.0:
                if self._target_kind == "scarecrow":
                    self._state = self.STATE_ATTACK_SCARECROW
                    self._phase_remaining = float(CROW_SCARECROW_PECK_SECONDS)
                else:
                    self._state = self.STATE_GRAB
                    self._phase_remaining = max(0.5, float(CROW_GRAB_BEAT_SECONDS))
        elif self._state == self.STATE_GRAB:
            self._x = crop_x
            self._y = crop_y + math.sin(self._anim_time * 16.0) * 2.0
            self._phase_remaining -= dt
            if self._phase_remaining <= 0.0:
                self._steal_target(slots, ignore_scarecrow=murder_active)
                self._state = self.STATE_CLIMB
                self._phase_remaining = float(CROW_CLIMB_SECONDS)
        elif self._state == self.STATE_ATTACK_SCARECROW:
            self._x = crop_x
            self._y = crop_y + math.sin(self._anim_time * 24.0) * 3.0
            self._phase_remaining -= dt
            if self._phase_remaining <= 0.0:
                self._remove_target_scarecrow(slots)
                self._choose_plant_target(slots, ignore_scarecrow=True)
                if self._target_idx is None:
                    self._begin_flee(field_rect)
                else:
                    self._state = self.STATE_FLY_IN
        elif self._state == self.STATE_CLIMB:
            self._phase_remaining -= dt
            self._y -= max(35.0, float(CROW_ALTITUDE_PX)) * dt / max(0.001, float(CROW_CLIMB_SECONDS))
            if self._phase_remaining <= 0.0:
                self._begin_flee(field_rect)

        self._sync_rect()

    def handle_click(self, event: pygame.event.Event, *, field_rect: pygame.Rect) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if not self.active or event.pos[0] > field_rect.width:
            return False
        if self.rect.collidepoint(event.pos):
            self.scare_away(field_rect=field_rect)
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active:
            return
        self._draw_shadow(surface)
        self._draw_telegraph(surface)
        self._draw_crow(surface)

    def _spawn(self, slots: Sequence[object], field_rect: pygame.Rect, *, murder_active: bool) -> bool:
        if murder_active and self._nearest_scarecrow(slots) is not None:
            self._choose_scarecrow_target(slots)
        else:
            self._choose_plant_target(slots, ignore_scarecrow=murder_active)
        if self._target_idx is None:
            return False
        hover_x, hover_y = self._hover_point(slots, self._target_idx)
        _crop_x, crop_y = self._crop_point(slots, self._target_idx)
        self._shadow_y = crop_y + 24.0
        self._side = "left" if hover_x >= field_rect.width / 2 else "right"
        self._direction = 1 if self._side == "left" else -1
        self._x = -40.0 if self._side == "left" else float(field_rect.width) + 40.0
        self._y = hover_y
        self._phase_remaining = 0.0
        self._anim_time = 0.0
        self._state = self.STATE_FLY_IN
        self._sync_rect()
        self._juice_events.append({"kind": "spawn", "pos": self.rect.center})
        return True

    def _choose_plant_target(self, slots: Sequence[object], *, ignore_scarecrow: bool) -> None:
        best_idx: int | None = None
        best_value = -1
        for idx, slot in enumerate(slots):
            if not self._plant_slot_valid(slots, idx, ignore_scarecrow=ignore_scarecrow):
                continue
            value = self._slot_value(slot)
            if value > best_value:
                best_idx = idx
                best_value = value
        self._target_idx = best_idx
        self._target_kind = "plant"

    def _choose_scarecrow_target(self, slots: Sequence[object]) -> None:
        idx = self._nearest_scarecrow(slots)
        self._target_idx = idx
        self._target_kind = "scarecrow" if idx is not None else "plant"

    def _nearest_scarecrow(self, slots: Sequence[object]) -> int | None:
        best_idx: int | None = None
        best_dist = float("inf")
        for idx, slot in enumerate(slots):
            if not getattr(slot, "has_scarecrow", False):
                continue
            rect = getattr(slot, "rect", None)
            if not isinstance(rect, pygame.Rect):
                continue
            dist = abs(rect.centerx - self._x) + abs(rect.centery - self._y)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        return best_idx

    def _slot_value(self, slot: object) -> int:
        seed = getattr(slot, "seed", None)
        if seed is None:
            return 0
        item = ITEMS.get(getattr(seed, "product_name", None))
        price = int(getattr(item, "sell_price", 0)) if item else 0
        return price * max(1, int(getattr(seed, "harvest_yield", 1)))

    def _plant_slot_valid(self, slots: Sequence[object], idx: int, *, ignore_scarecrow: bool) -> bool:
        if idx < 0 or idx >= len(slots):
            return False
        slot = slots[idx]
        if getattr(slot, "seed", None) is None or getattr(slot, "dead", False):
            return False
        rect = getattr(slot, "rect", None)
        if not isinstance(rect, pygame.Rect):
            return False
        if not ignore_scarecrow and self._scarecrow_protects(slots, idx):
            return False
        return True

    def _plant_target_valid(self, slots: Sequence[object], *, ignore_scarecrow: bool) -> bool:
        return self._target_idx is not None and self._plant_slot_valid(slots, self._target_idx, ignore_scarecrow=ignore_scarecrow)

    def _scarecrow_target_valid(self, slots: Sequence[object]) -> bool:
        if self._target_idx is None or self._target_idx < 0 or self._target_idx >= len(slots):
            return False
        return bool(getattr(slots[self._target_idx], "has_scarecrow", False))

    def _scarecrow_protects(self, slots: Sequence[object], idx: int) -> bool:
        target = slots[idx]
        trect = getattr(target, "rect", None)
        if not isinstance(trect, pygame.Rect):
            return False
        radius = max(0, int(CRITTER_SCARECROW_AVOID_RADIUS_SLOTS))
        if radius <= 0:
            return bool(getattr(target, "has_scarecrow", False))
        pitch = max(trect.width, trect.height) * 1.4
        reach = radius * pitch
        for slot in slots:
            if not getattr(slot, "has_scarecrow", False):
                continue
            srect = getattr(slot, "rect", None)
            if not isinstance(srect, pygame.Rect):
                continue
            if abs(srect.centerx - trect.centerx) <= reach and abs(srect.centery - trect.centery) <= reach:
                return True
        return False

    def _hover_point(self, slots: Sequence[object], idx: int | None) -> tuple[float, float]:
        if idx is None or idx < 0 or idx >= len(slots):
            return self._x, self._y
        rect = slots[idx].rect
        return float(rect.centerx), float(max(14, rect.top - int(CROW_ALTITUDE_PX)))

    def _crop_point(self, slots: Sequence[object], idx: int | None) -> tuple[float, float]:
        if idx is None or idx < 0 or idx >= len(slots):
            return self._x, self._y
        rect = slots[idx].rect
        return float(rect.centerx), float(rect.top + max(8, rect.height * 0.25))

    def _shadow_point(self) -> tuple[int, int]:
        return int(round(self._x)), int(round(self._shadow_y))

    def _move_toward(self, tx: float, ty: float, dt: float, *, speed: float) -> bool:
        dx, dy = tx - self._x, ty - self._y
        dist = math.hypot(dx, dy)
        step = max(1.0, speed) * dt
        if dist <= max(2.0, step):
            self._x, self._y = tx, ty
            return True
        self._x += step * dx / dist
        self._y += step * dy / dist
        self._direction = 1 if dx >= 0.0 else -1
        return False

    def _steal_target(self, slots: Sequence[object], *, ignore_scarecrow: bool) -> None:
        if not self._plant_target_valid(slots, ignore_scarecrow=ignore_scarecrow):
            return
        clear_fn = getattr(slots[self._target_idx], "clear", None)
        if callable(clear_fn):
            rect = getattr(slots[self._target_idx], "rect", None)
            pos = rect.center if isinstance(rect, pygame.Rect) else self.rect.center
            clear_fn()
            self._stolen = True
            self._juice_events.append({"kind": "steal", "target": "plant", "pos": pos})

    def _remove_target_scarecrow(self, slots: Sequence[object]) -> None:
        if not self._scarecrow_target_valid(slots):
            return
        remove_fn = getattr(slots[self._target_idx], "remove_scarecrow", None)
        if callable(remove_fn):
            remove_fn()
        else:
            try:
                slots[self._target_idx].has_scarecrow = False
            except Exception:
                pass
        rect = getattr(slots[self._target_idx], "rect", None)
        pos = rect.center if isinstance(rect, pygame.Rect) else self.rect.center
        self._juice_events.append({"kind": "steal", "target": "scarecrow", "pos": pos})

    def _begin_flee(self, field_rect: pygame.Rect) -> None:
        left_dist = abs(self._x)
        right_dist = abs(float(field_rect.width) - self._x)
        self._side = "left" if left_dist <= right_dist else "right"
        self._direction = -1 if self._side == "left" else 1
        self._target_idx = None
        self._target_kind = "plant"
        self._state = self.STATE_FLEE

    def _deactivate(self) -> None:
        self._state = self.STATE_INACTIVE
        self._spawn_accum = 0.0
        self._target_idx = None
        self._target_kind = "plant"
        self._phase_remaining = 0.0

    def _sync_rect(self) -> None:
        self.rect.center = (int(round(self._x)), int(round(self._y)))

    def _draw_shadow(self, surface: pygame.Surface) -> None:
        sx, sy = self._shadow_point()
        shadow = pygame.Surface((46, 16), pygame.SRCALPHA)
        alpha = 115 if self._state in (self.STATE_GRAB, self.STATE_ATTACK_SCARECROW) else 72
        pygame.draw.ellipse(shadow, (25, 20, 18, alpha), shadow.get_rect())
        surface.blit(shadow, shadow.get_rect(center=(sx, sy)))

    def _draw_telegraph(self, surface: pygame.Surface) -> None:
        if self._state not in (self.STATE_FLY_IN, self.STATE_DIVE):
            return
        flash = abs(math.sin(self._anim_time * 16.0))
        col = (245, 245, 235, int(80 + 105 * flash))
        wing = pygame.Surface((18, 10), pygame.SRCALPHA)
        pygame.draw.polygon(wing, col, [(1, 5), (17, 1), (13, 9)])
        offset = 18 if self._direction >= 0 else -36
        surface.blit(wing, (int(self._x + offset), int(self._y - 10)))

    def _draw_crow(self, surface: pygame.Surface) -> None:
        w, h = int(CROW_WIDTH), int(CROW_HEIGHT)
        crow = pygame.Surface((w + 12, h + 12), pygame.SRCALPHA)
        cx, cy = (w + 12) // 2, (h + 12) // 2
        flap = math.sin(self._anim_time * 24.0)
        wing_y = int(5 + abs(flap) * 7)
        body_col = (28, 29, 34, 245)
        wing_col = (18, 19, 24, 235)
        eye_col = (245, 225, 80, 245)
        pygame.draw.polygon(crow, wing_col, [(cx - 3, cy), (cx - 20, cy - wing_y), (cx - 12, cy + 9)])
        pygame.draw.polygon(crow, wing_col, [(cx + 3, cy), (cx + 20, cy - wing_y), (cx + 12, cy + 9)])
        pygame.draw.ellipse(crow, body_col, pygame.Rect(cx - 11, cy - 7, 22, 14))
        beak_dir = 1 if self._direction >= 0 else -1
        beak_x = cx + beak_dir * 12
        pygame.draw.polygon(crow, (210, 175, 60, 245), [(beak_x, cy), (beak_x + beak_dir * 8, cy - 3), (beak_x + beak_dir * 8, cy + 3)])
        pygame.draw.circle(crow, eye_col, (cx + beak_dir * 6, cy - 3), 2)
        if beak_dir < 0:
            crow = pygame.transform.flip(crow, True, False)
        surface.blit(crow, crow.get_rect(center=self.rect.center))


class BellTool:
    def __init__(self, *, cooldown_seconds: float = BELL_COOLDOWN_SECONDS):
        self.cooldown_seconds = max(0.1, float(cooldown_seconds))
        self._remaining = 0.0

    @property
    def cooldown_remaining(self) -> float:
        return max(0.0, self._remaining)

    @property
    def ready(self) -> bool:
        return self._remaining <= 0.0

    @property
    def cooldown_ratio(self) -> float:
        return max(0.0, min(1.0, self._remaining / self.cooldown_seconds))

    def update(self, dt: float) -> None:
        if dt > 0.0:
            self._remaining = max(0.0, self._remaining - dt)

    def ring(self, flyers: Sequence[FlyingCrowThief], *, field_rect: pygame.Rect) -> int:
        if not self.ready:
            return 0
        scared = 0
        for flyer in flyers:
            if flyer.active:
                flyer.scare_away(field_rect=field_rect)
                scared += 1
        self._remaining = self.cooldown_seconds
        return scared

    def force_ready(self) -> None:
        self._remaining = 0.0


class CrowFlock:
    def __init__(self, *, rng: random.Random | None = None, max_active: int = CROW_MAX_ACTIVE):
        self._rng = rng or random.Random()
        self.crows = [FlyingCrowThief(rng=self._rng) for _ in range(max(1, int(max_active)))]
        self._raid_active = False

    def __iter__(self):
        return iter(self.crows)

    def __len__(self) -> int:
        return len(self.crows)

    @property
    def active_count(self) -> int:
        return sum(1 for crow in self.crows if crow.active)

    @property
    def murder_active(self) -> bool:
        return self.active_count >= int(CROW_MURDER_MIN_ACTIVE)

    def set_raid_active(self, active: bool) -> None:
        self._raid_active = bool(active)
        for crow in self.crows:
            crow.set_raid_active(active)

    def set_difficulty_scale(self, scale: float) -> None:
        for crow in self.crows:
            crow.set_difficulty_scale(scale)

    def force_spawn(self, *, slots: Sequence[object], field_rect: pygame.Rect, ground_rect: pygame.Rect) -> bool:
        for crow in self.crows:
            if not crow.active:
                return crow.force_spawn(
                    slots=slots,
                    field_rect=field_rect,
                    ground_rect=ground_rect,
                    murder_active=self.murder_active,
                )
        return False

    def update(self, dt: float, *, slots: Sequence[object], field_rect: pygame.Rect, ground_rect: pygame.Rect) -> None:
        murder = self.murder_active
        for crow in self.crows:
            crow.update(dt, slots=slots, field_rect=field_rect, ground_rect=ground_rect, murder_active=murder)
        murder = self.murder_active
        if murder:
            for crow in self.crows:
                if crow.active:
                    crow.update(0.001, slots=slots, field_rect=field_rect, ground_rect=ground_rect, murder_active=True)

    def pop_juice_events(self) -> list[dict]:
        events: list[dict] = []
        for crow in self.crows:
            events.extend(crow.pop_juice_events())
        return events

    def handle_click(self, event: pygame.event.Event, *, field_rect: pygame.Rect) -> bool:
        for crow in self.crows:
            if crow.handle_click(event, field_rect=field_rect):
                return True
        return False

    def scare_all(self, *, field_rect: pygame.Rect) -> int:
        scared = 0
        for crow in self.crows:
            if crow.active:
                crow.scare_away(field_rect=field_rect)
                scared += 1
        return scared

    def draw(self, surface: pygame.Surface) -> None:
        for crow in self.crows:
            crow.draw(surface)


def make_crow(*, rng: random.Random | None = None) -> FlyingCrowThief:
    return FlyingCrowThief(rng=rng)
