from __future__ import annotations

import math
from typing import Any, Iterable, Optional

import pygame

from items import ITEMS
from settings import (
    GOLDEN_VALUE_MULT,
    JUICE_ENABLED,
    PRIME_DANGER_COLOR,
    PRIME_DANGER_SECONDS,
    PRIME_MAX_BONUS_MULT,
    PRIME_MAX_SECONDS,
    PRIME_SPOIL_SECONDS,
    PRIME_TINT_COLOR,
    WORKER_HARVEST_SECONDS,
    WORKER_HEIGHT,
    WORKER_HIRE_COST,
    WORKER_IDLE_AMBLE_SPEED,
    WORKER_SNAKE_KILL_PADDING,
    WORKER_SPEED_PX_PER_SEC,
    WORKER_WIDTH,
)
import random


PRIME_SECONDS_ATTR = "_prime_seconds"
PRIME_SPOILED_ATTR = "_prime_spoiled"


def _slot_prime_seconds(slot: Any) -> float:
    return max(0.0, float(getattr(slot, PRIME_SECONDS_ATTR, 0.0)))


def _set_slot_prime(slot: Any, seconds: float, spoiled: bool = False) -> None:
    setattr(slot, PRIME_SECONDS_ATTR, max(0.0, float(seconds)))
    setattr(slot, PRIME_SPOILED_ATTR, bool(spoiled))


def reset_slot_prime(slot: Any) -> None:
    _set_slot_prime(slot, 0.0, False)


def prime_ratio(slot: Any) -> float:
    if PRIME_MAX_SECONDS <= 0.0:
        return 0.0
    return max(0.0, min(1.0, _slot_prime_seconds(slot) / float(PRIME_MAX_SECONDS)))


def prime_multiplier(slot: Any) -> float:
    if bool(getattr(slot, PRIME_SPOILED_ATTR, False)):
        return 0.0
    return 1.0 + float(PRIME_MAX_BONUS_MULT) * prime_ratio(slot)


def update_prime_slots(slots: Iterable[Any], dt: float) -> None:
    if dt <= 0.0:
        return
    for slot in slots:
        if not getattr(slot, "planted", False):
            reset_slot_prime(slot)
            continue
        if getattr(slot, "dead", False):
            continue
        if not getattr(slot, "harvestable", False):
            reset_slot_prime(slot)
            continue
        seconds = _slot_prime_seconds(slot) + float(dt)
        if seconds >= float(PRIME_SPOIL_SECONDS):
            _set_slot_prime(slot, seconds, True)
            slot.dead = True
        else:
            _set_slot_prime(slot, seconds, False)


def slot_prime_to_dict(slot: Any) -> dict[str, Any]:
    return {
        "prime_seconds": _slot_prime_seconds(slot),
        "prime_spoiled": bool(getattr(slot, PRIME_SPOILED_ATTR, False)),
    }


def slot_prime_from_dict(slot: Any, data: dict[str, Any]) -> None:
    _set_slot_prime(
        slot,
        float(data.get("prime_seconds", 0.0)),
        bool(data.get("prime_spoiled", False)),
    )


def prime_save_slots(slots: Iterable[Any]) -> list[dict[str, Any]]:
    return [slot_prime_to_dict(slot) for slot in slots]


def prime_load_slots(slots: Iterable[Any], data: Iterable[dict[str, Any]]) -> None:
    for slot, sdata in zip(slots, data or []):
        if isinstance(sdata, dict):
            slot_prime_from_dict(slot, sdata)


def calculate_slot_sale_value(slot: Any) -> int:
    seed = getattr(slot, "seed", None)
    if seed is None:
        return 0
    item = ITEMS.get(str(getattr(seed, "product_name", "")))
    if item is None:
        return 0
    value = float(item.sell_price) * int(getattr(seed, "harvest_yield", 1))
    value *= prime_multiplier(slot)
    if bool(getattr(slot, "is_golden", False)):
        value *= float(GOLDEN_VALUE_MULT)
    return max(0, int(round(value)))


def _play_harvest_feedback(game: Any, slot: Any, seed: Any, value: int, golden: bool) -> None:
    play_varied = getattr(game, "_play_varied", None)
    if callable(play_varied):
        play_varied(getattr(game, "_sfx_harvest_variants", []), getattr(game, "_sfx_harvest", None), base_volume=0.5)
    if not JUICE_ENABLED:
        return
    spawn_juice = getattr(game, "_spawn_harvest_juice", None)
    if callable(spawn_juice):
        spawn_juice(slot, seed, golden=golden)
    float_texts = getattr(game, "_float_texts", None)
    if isinstance(float_texts, list):
        cls = _float_text_class(game)
        if cls is not None:
            float_texts.append(cls(slot.rect.centerx, slot.rect.top - 28, f"+{value}g", color=(250, 235, 140)))
    spawn_fly = getattr(game, "_spawn_fly_coins", None)
    if callable(spawn_fly):
        spawn_fly(slot.rect.center, n=min(8, 2 + value // 25))
    if hasattr(game, "_money_bump"):
        game._money_bump = 1.0


def _float_text_class(game: Any) -> Optional[type]:
    texts = getattr(game, "_float_texts", None)
    if isinstance(texts, list) and texts:
        return type(texts[0])
    try:
        import game as game_mod

        return getattr(game_mod, "FloatText", None)
    except Exception:
        return None


def cash_harvest(game: Any, slot: Any) -> int:
    seed = getattr(slot, "seed", None)
    if seed is None or getattr(slot, "dead", False) or not getattr(slot, "harvestable", False):
        return 0
    value = calculate_slot_sale_value(slot)
    if value <= 0:
        return 0

    golden = bool(getattr(slot, "is_golden", False))
    game.money = int(getattr(game, "money", 0)) + value
    if hasattr(game, "_total_earned"):
        game._total_earned = int(getattr(game, "_total_earned", 0)) + value
    almanac = getattr(game, "_almanac", None)
    if almanac is not None:
        on_harvest = getattr(almanac, "on_harvest", None)
        if callable(on_harvest):
            on_harvest(seed.product_name, int(getattr(seed, "harvest_yield", 1)))
        on_money = getattr(almanac, "on_money_earned", None)
        if callable(on_money):
            on_money(value)

    _play_harvest_feedback(game, slot, seed, value, golden)
    _spread_if_needed(game, slot, seed)
    reset_slot_prime(slot)
    if getattr(seed, "regrow_to_stage", None) is None:
        slot.clear()
    else:
        slot.regrow(seed.regrow_to_stage)
    return value


def harvest_prime_bonus_to_money(game: Any, slot: Any) -> int:
    seed = getattr(slot, "seed", None)
    if seed is None:
        return 0
    base = calculate_slot_sale_value_without_prime(slot)
    primed = calculate_slot_sale_value(slot)
    bonus = max(0, primed - base)
    if bonus > 0:
        game.money = int(getattr(game, "money", 0)) + bonus
        if hasattr(game, "_total_earned"):
            game._total_earned = int(getattr(game, "_total_earned", 0)) + bonus
    return bonus


def calculate_slot_sale_value_without_prime(slot: Any) -> int:
    seed = getattr(slot, "seed", None)
    if seed is None:
        return 0
    item = ITEMS.get(str(getattr(seed, "product_name", "")))
    if item is None:
        return 0
    value = float(item.sell_price) * int(getattr(seed, "harvest_yield", 1))
    if bool(getattr(slot, "is_golden", False)):
        value *= float(GOLDEN_VALUE_MULT)
    return max(0, int(round(value)))


def _spread_if_needed(game: Any, slot: Any, seed: Any) -> None:
    if not getattr(seed, "spreads_on_harvest", False):
        return
    slots = getattr(game, "slots", [])
    try:
        idx = slots.index(slot)
    except ValueError:
        return
    candidates = []
    for j in (idx - 1, idx + 1):
        if 0 <= j < len(slots):
            nb = slots[j]
            if (
                not getattr(nb, "planted", False)
                and not getattr(nb, "dead", False)
                and not getattr(nb, "has_scarecrow", False)
                and not getattr(nb, "salted", False)
            ):
                candidates.append(nb)
    if candidates:
        rng = getattr(game, "_rng", None)
        choice = rng.choice(candidates) if rng is not None else candidates[0]
        choice.plant(seed)


def draw_prime_overlays(surface: pygame.Surface, slots: Iterable[Any]) -> None:
    for slot in slots:
        if not getattr(slot, "planted", False) or not getattr(slot, "harvestable", False):
            continue
        if getattr(slot, "dead", False) and not bool(getattr(slot, PRIME_SPOILED_ATTR, False)):
            continue
        rect = getattr(slot, "rect", None)
        if not isinstance(rect, pygame.Rect):
            continue
        seconds = _slot_prime_seconds(slot)
        if seconds <= 0.0:
            continue
        danger = seconds >= float(PRIME_DANGER_SECONDS)
        color = PRIME_DANGER_COLOR if danger else PRIME_TINT_COLOR
        alpha = 45 if not danger else 85
        wash = pygame.Surface(rect.size, pygame.SRCALPHA)
        wash.fill((*color, alpha))
        surface.blit(wash, rect.topleft)

        bar_w = max(8, rect.width - 10)
        bar_h = 5
        bar = pygame.Rect(rect.left + 5, rect.top + 5, bar_w, bar_h)
        pygame.draw.rect(surface, (38, 28, 18), bar, border_radius=2)
        fill_w = int(bar.width * min(1.0, seconds / float(PRIME_SPOIL_SECONDS)))
        pygame.draw.rect(surface, color, pygame.Rect(bar.left, bar.top, fill_w, bar.height), border_radius=2)
        if PRIME_SPOIL_SECONDS > 0.0:
            danger_x = bar.left + int(bar.width * min(1.0, float(PRIME_DANGER_SECONDS) / float(PRIME_SPOIL_SECONDS)))
            pygame.draw.line(surface, (255, 245, 230), (danger_x, bar.top - 2), (danger_x, bar.bottom + 2), 1)


class AutoHarvesterWorker:
    def __init__(self) -> None:
        self.active = False
        self.killed = False
        self.x: Optional[float] = None
        self.y: Optional[float] = None
        self.target_index: Optional[int] = None
        self.harvest_timer = 0.0
        self.harvest_flash = 0.0
        self.facing = 1
        self._amble_target: Optional[float] = None
        self._amble_pause = 0.0

    @property
    def rect(self) -> pygame.Rect:
        x = 0.0 if self.x is None else self.x
        y = 0.0 if self.y is None else self.y
        r = pygame.Rect(0, 0, int(WORKER_WIDTH), int(WORKER_HEIGHT))
        r.midbottom = (int(round(x)), int(round(y)))
        return r

    def can_hire(self, money: int) -> bool:
        return (not self.active) and int(money) >= int(WORKER_HIRE_COST)

    def hire(self, game: Any) -> bool:
        if self.active:
            return True
        if int(getattr(game, "money", 0)) < int(WORKER_HIRE_COST):
            if hasattr(game, "_money_flash_timer"):
                game._money_flash_timer = 20
            return False
        game.money = int(getattr(game, "money", 0)) - int(WORKER_HIRE_COST)
        self.active = True
        self.killed = False
        self.target_index = None
        self.harvest_timer = 0.0
        slots = getattr(game, "slots", [])
        if slots:
            self.x = float(slots[0].rect.centerx)
            self.y = float(slots[0].rect.bottom)
        return True

    def disable(self) -> None:
        self.active = False
        self.killed = True
        self.target_index = None
        self.harvest_timer = 0.0

    def update(self, dt: float, game: Any, ground_pests: Optional[Iterable[Any]] = None) -> None:
        if dt <= 0.0:
            return
        self.harvest_flash = max(0.0, self.harvest_flash - dt)
        if not self.active:
            return
        slots = getattr(game, "slots", [])
        if not slots:
            return
        if self.y is None:
            self.y = float(slots[0].rect.bottom)
        if self.x is None:
            self.x = float(slots[0].rect.centerx)

        if self._hit_by_pest(game, ground_pests):
            self.disable()
            return

        if not self._target_valid(slots):
            self.target_index = self._choose_target(slots)
            self.harvest_timer = 0.0
        if self.target_index is None:
            self._idle_amble(dt, slots)
            return

        slot = slots[self.target_index]
        target_x = float(slot.rect.centerx)
        dx = target_x - float(self.x)
        if abs(dx) > 3.0:
            step = float(WORKER_SPEED_PX_PER_SEC) * dt
            self.facing = 1 if dx > 0 else -1
            self.x += max(-step, min(step, dx))
            self.harvest_timer = 0.0
            return

        self.x = target_x
        self.harvest_timer += dt
        self.harvest_flash = 0.16
        if self.harvest_timer >= float(WORKER_HARVEST_SECONDS):
            self._do_harvest(game, slot)
            self.harvest_timer = 0.0
            self.target_index = None

    def _idle_amble(self, dt: float, slots: list[Any]) -> None:
        # With nothing ripe, the worker wanders the rows so it reads as a living
        # farmhand rather than a frozen sprite. Slow, with brief pauses.
        if self._amble_pause > 0.0:
            self._amble_pause = max(0.0, self._amble_pause - dt)
            return
        if self._amble_target is None or abs(self._amble_target - float(self.x)) <= 3.0:
            lo = float(slots[0].rect.centerx)
            hi = float(slots[-1].rect.centerx)
            self._amble_target = random.uniform(lo, hi)
            self._amble_pause = random.uniform(0.4, 1.4)
            return
        dx = self._amble_target - float(self.x)
        step = float(WORKER_IDLE_AMBLE_SPEED) * dt
        self.facing = 1 if dx > 0 else -1
        self.x += max(-step, min(step, dx))

    def _do_harvest(self, game: Any, slot: Any) -> None:
        # Prefer the game's own harvest so the worker behaves exactly like a player
        # pluck: the crop goes to inventory (keeping the Golden 2x and the player's
        # sell timing) and any Prime bonus is paid as cash. Fall back to a direct
        # cash sale only when no full game is present (e.g. unit tests with a mock).
        harvest = getattr(game, "_harvest", None)
        if callable(harvest):
            harvest(slot)
        else:
            cash_harvest(game, slot)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active:
            return
        r = self.rect
        t = pygame.time.get_ticks() * 0.008
        bob = int(math.sin(t) * 2)
        body = r.move(0, bob)
        pygame.draw.ellipse(surface, (33, 28, 24), pygame.Rect(body.left + 5, body.bottom - 5, body.width - 10, 5))
        pygame.draw.rect(surface, (72, 126, 88), pygame.Rect(body.left + 6, body.top + 14, body.width - 12, 18), border_radius=6)
        pygame.draw.circle(surface, (226, 174, 116), (body.centerx, body.top + 10), 8)
        pygame.draw.circle(surface, (35, 30, 25), (body.centerx + 3 * self.facing, body.top + 8), 2)
        pygame.draw.line(surface, (92, 62, 38), (body.centerx + 9 * self.facing, body.top + 22), (body.centerx + 16 * self.facing, body.top + 30), 3)
        pygame.draw.line(surface, (48, 78, 54), (body.centerx - 5, body.bottom - 10), (body.centerx - 9, body.bottom), 3)
        pygame.draw.line(surface, (48, 78, 54), (body.centerx + 5, body.bottom - 10), (body.centerx + 9, body.bottom), 3)
        if self.harvest_flash > 0.0:
            pygame.draw.circle(surface, (255, 235, 130), (body.centerx + 18 * self.facing, body.top + 30), 7, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": bool(self.active),
            "killed": bool(self.killed),
            "x": self.x,
            "y": self.y,
            "target_index": self.target_index,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self.active = bool(data.get("active", False))
        self.killed = bool(data.get("killed", False))
        self.x = _maybe_float(data.get("x"))
        self.y = _maybe_float(data.get("y"))
        idx = data.get("target_index")
        self.target_index = int(idx) if idx is not None else None
        self.harvest_timer = 0.0
        self.harvest_flash = 0.0

    def _target_valid(self, slots: list[Any]) -> bool:
        if self.target_index is None or self.target_index < 0 or self.target_index >= len(slots):
            return False
        slot = slots[self.target_index]
        return (
            getattr(slot, "planted", False)
            and getattr(slot, "harvestable", False)
            and not getattr(slot, "dead", False)
        )

    def _choose_target(self, slots: list[Any]) -> Optional[int]:
        candidates = [
            (abs(slot.rect.centerx - float(self.x or slot.rect.centerx)), i)
            for i, slot in enumerate(slots)
            if getattr(slot, "planted", False)
            and getattr(slot, "harvestable", False)
            and not getattr(slot, "dead", False)
        ]
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][1]

    def _hit_by_pest(self, game: Any, ground_pests: Optional[Iterable[Any]]) -> bool:
        pests = list(ground_pests) if ground_pests is not None else list(getattr(game, "_critters", []))
        if not pests and getattr(game, "snake", None) is not None:
            pests = [getattr(game, "snake")]
        hit_rect = self.rect.inflate(int(WORKER_SNAKE_KILL_PADDING) * 2, int(WORKER_SNAKE_KILL_PADDING) * 2)
        for pest in pests:
            if not getattr(pest, "active", False):
                continue
            rect = getattr(pest, "rect", None)
            if isinstance(rect, pygame.Rect) and hit_rect.colliderect(rect):
                return True
        return False


def _maybe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def draw_worker_hire_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    font: pygame.font.Font,
    worker: AutoHarvesterWorker,
    money: int,
) -> None:
    if worker.active:
        label = "Worker hired"
        bg = (62, 110, 78)
    elif worker.killed:
        label = f"Rehire worker ${WORKER_HIRE_COST}"
        bg = (120, 62, 56)
    else:
        label = f"Hire worker ${WORKER_HIRE_COST}"
        bg = (78, 72, 58) if int(money) >= int(WORKER_HIRE_COST) else (58, 56, 56)
    pygame.draw.rect(surface, bg, rect, border_radius=8)
    pygame.draw.rect(surface, (230, 218, 172), rect, 2, border_radius=8)
    text = font.render(label, True, (248, 240, 214))
    surface.blit(text, text.get_rect(center=rect.center))

