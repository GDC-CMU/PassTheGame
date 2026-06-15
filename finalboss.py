from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable, Sequence

import pygame

from settings import (
    SCREEN_W,
    UI_PANEL_W,
    SUN_X,
    SUN_Y,
    SUN_RADIUS,
    PERFECT_BLOCK_TOLERANCE_PX,
    PERFECT_BLOCK_BONUS_DAMAGE,
    PERFECT_BLOCK_RING_MAX_RADIUS,
    PERFECT_BLOCK_RING_MIN_RADIUS,
    PERFECT_BLOCK_RING_WIDTH,
    PERFECT_BLOCK_RING_COLOR,
    BOSS_COMBO_THRESHOLD,
    BOSS_COMBO_DAMAGE_BONUS,
    IN_GAME_WEEK_SECONDS,
)
from storm_titan import StormTitan, StormTitanConfig


INFERNO_TITAN_WIDTH = 420
INFERNO_TITAN_HEIGHT = 220
INFERNO_TITAN_Y = 4
INFERNO_TITAN_MAX_HP = 24
INFERNO_TITAN_SPAWN_EVERY_SECONDS = IN_GAME_WEEK_SECONDS * 4.0
INFERNO_TITAN_STRIKE_COOLDOWN_SECONDS = 1.7
INFERNO_TITAN_STRIKE_WARNING_SECONDS = 1.45
INFERNO_TITAN_RETREAT_SECONDS = 4.5
INFERNO_TITAN_REWARD_ITEM_NAME = "Inferno Heart"
INFERNO_TITAN_REWARD_ITEM_COUNT = 1
INFERNO_TITAN_NODAMAGE_BONUS_ITEM_NAME = "Inferno Heart"
INFERNO_TITAN_NODAMAGE_BONUS_ITEM_COUNT = 1
INFERNO_TITAN_IMAGE_FILENAME = "inferno_titan.png"

INFERNO_CYCLONE_AOE_RADIUS_SLOTS = 1
INFERNO_FROST_MARK_COUNT = 3
INFERNO_FROST_FREEZE_SECONDS = 5.0
INFERNO_FIRESTORM_MARK_COUNT = 5
INFERNO_FIRESTORM_SCORCH_SECONDS = 4.5
INFERNO_FIRESTORM_WATER_LOSS = 12.0
INFERNO_FIRESTORM_GROWTH_LOSS = 0.35
INFERNO_LAVA_SCORCH_SECONDS = 7.0
INFERNO_LAVA_WATER_LOSS = 24.0
INFERNO_LAVA_SALT_SECONDS = 10.0
INFERNO_LAVA_GROWTH_LOSS = 0.75
INFERNO_HEAT_VEIL_SUN_SPIKE = 8.0
INFERNO_HEAT_VEIL_WATER_DRAIN = 4.0

PHASE_STORM = "storm"
PHASE_CYCLONE = "cyclone"
PHASE_DROUGHT = "drought"
PHASE_FROST = "frost"
PHASE_INFERNO = "inferno"
PHASE_ORDER = (PHASE_STORM, PHASE_CYCLONE, PHASE_DROUGHT, PHASE_FROST, PHASE_INFERNO)

FIRE_FIRESTORM = "firestorm"
FIRE_LAVA = "lava"

PHASE_COLORS = {
    PHASE_STORM: (255, 235, 120),
    PHASE_CYCLONE: (180, 80, 235),
    PHASE_DROUGHT: (255, 160, 60),
    PHASE_FROST: (140, 210, 255),
    PHASE_INFERNO: (255, 72, 28),
}


@dataclass(frozen=True)
class InfernoTitanConfig(StormTitanConfig):
    spawn_every_seconds: float = INFERNO_TITAN_SPAWN_EVERY_SECONDS
    max_hp: int = INFERNO_TITAN_MAX_HP
    strike_cooldown_seconds: float = INFERNO_TITAN_STRIKE_COOLDOWN_SECONDS
    strike_warning_seconds: float = INFERNO_TITAN_STRIKE_WARNING_SECONDS
    retreat_seconds: float = INFERNO_TITAN_RETREAT_SECONDS
    reward_item_name: str = INFERNO_TITAN_REWARD_ITEM_NAME
    reward_item_count: int = INFERNO_TITAN_REWARD_ITEM_COUNT
    width: int = INFERNO_TITAN_WIDTH
    height: int = INFERNO_TITAN_HEIGHT
    y: int = INFERNO_TITAN_Y
    lightning_kills_plant: bool = True
    image_filename: str = INFERNO_TITAN_IMAGE_FILENAME
    warning_color: tuple[int, int, int] = PHASE_COLORS[PHASE_INFERNO]
    bolt_color: tuple[int, int, int] = (255, 210, 80)
    bolt_shadow_color: tuple[int, int, int] = (255, 250, 220)
    move_lerp_rate: float = 4.6
    align_epsilon_px: float = 5.0
    aoe_radius_slots: int = 0
    health_bar_width: int = 540
    health_bar_height: int = 24
    salt_seconds: float = 16.0
    no_damage_bonus_item_name: str = INFERNO_TITAN_NODAMAGE_BONUS_ITEM_NAME
    no_damage_bonus_item_count: int = INFERNO_TITAN_NODAMAGE_BONUS_ITEM_COUNT


class InfernoTitan(StormTitan):
    boss_id = "inferno"
    display_name = "Inferno Titan"

    def __init__(self, config: InfernoTitanConfig | None = None, *, rng: random.Random | None = None):
        super().__init__(config or InfernoTitanConfig(), rng=rng)
        self.current_phase = PHASE_STORM
        self._phase_index = 0
        self._inferno_next = FIRE_FIRESTORM
        self._fire_ability: str | None = None
        self._mark_indices: list[int] = []
        self._fire_marks: list[tuple[int, int, bool, int, str]] = []

    @property
    def plays_lightning_sfx(self) -> bool:
        return self.current_phase in {PHASE_STORM, PHASE_CYCLONE, PHASE_FROST}

    def _begin_fight(self) -> None:
        super()._begin_fight()
        self._phase_index = 0
        self.current_phase = PHASE_ORDER[self._phase_index]
        self._fire_ability = None
        self._mark_indices = []
        self._fire_marks = []

    def _reset_to_waiting(self) -> None:
        super()._reset_to_waiting()
        self._phase_index = 0
        self.current_phase = PHASE_ORDER[self._phase_index]
        self._fire_ability = None
        self._mark_indices = []
        self._fire_marks = []

    def update_battle(self, dt: float, *, slots: Sequence[object], clouds: Iterable[object]) -> None:
        self._advance_anim(dt)
        if dt <= 0.0:
            return

        if self._state == self.STATE_WAITING:
            if not self.enabled:
                return
            self._spawn_remaining -= dt
            if self._spawn_remaining <= 0.0:
                self._begin_fight()
            return

        if self._state == self.STATE_RETREATING:
            self._retreat_remaining -= dt
            self._bolt_flash_remaining = max(0.0, self._bolt_flash_remaining - dt)
            if self._retreat_remaining <= 0.0:
                self._reset_to_waiting()
            return

        self._bolt_flash_remaining = max(0.0, self._bolt_flash_remaining - dt)
        phase = self.current_phase

        if phase == PHASE_DROUGHT:
            self._target_x = float(SUN_X)
            self._smooth_move_x(dt)
        elif self._target_slot_index is not None:
            slot = self._get_valid_target_slot(slots)
            if slot is None:
                self._clear_attack_target()
            else:
                rect = getattr(slot, "rect", None)
                if isinstance(rect, pygame.Rect):
                    self._target_x = float(rect.centerx)
                    self._smooth_move_x(dt)

        if self._warning_remaining > 0.0:
            self._warning_remaining -= dt
            if self._warning_remaining <= 0.0:
                self._snap_to_target_x()
                self._resolve_phase_strike(slots, clouds)
            return

        self._cooldown_remaining -= dt
        if self._cooldown_remaining > 0.0:
            return

        if phase == PHASE_DROUGHT:
            if self._living_planted(slots):
                self._warning_remaining = float(self.config.strike_warning_seconds)
            else:
                self._cooldown_remaining = 1.0
            return

        if phase == PHASE_INFERNO and self._fire_ability is None:
            self._fire_ability = self._inferno_next

        if self._target_slot_index is None:
            self._choose_target(slots)
            if self._target_slot_index is None:
                self._cooldown_remaining = 1.0
                return
            slot = self._get_valid_target_slot(slots)
            rect = getattr(slot, "rect", None) if slot is not None else None
            if not isinstance(rect, pygame.Rect):
                self._clear_attack_target()
                self._cooldown_remaining = 1.0
                return
            self._target_x = float(rect.centerx)

        if self._target_x is not None:
            self._smooth_move_x(dt)
            if abs(self._x - self._target_x) <= float(self.config.align_epsilon_px):
                self._warning_remaining = float(self.config.strike_warning_seconds)
                self._on_warning_open(slots)

    def _on_warning_open(self, slots: Sequence[object]) -> None:
        if self.current_phase == PHASE_FROST:
            self._compute_mark_band(slots, INFERNO_FROST_MARK_COUNT)
        elif self.current_phase == PHASE_INFERNO and self._fire_ability == FIRE_FIRESTORM:
            self._compute_mark_band(slots, INFERNO_FIRESTORM_MARK_COUNT)
        else:
            self._mark_indices = []

    def _resolve_phase_strike(self, slots: Sequence[object], clouds: Iterable[object]) -> None:
        clouds = list(clouds)
        phase = self.current_phase
        if phase == PHASE_STORM:
            self._resolve_slot_strike(slots, clouds, require_rain=False, aoe_radius=0, kill=True)
        elif phase == PHASE_CYCLONE:
            self._resolve_slot_strike(slots, clouds, require_rain=True, aoe_radius=INFERNO_CYCLONE_AOE_RADIUS_SLOTS, kill=True)
        elif phase == PHASE_DROUGHT:
            self._resolve_drought_strike(slots, clouds)
        elif phase == PHASE_FROST:
            self._resolve_frost_strike(slots, clouds)
        else:
            if self._fire_ability == FIRE_LAVA:
                self._resolve_lava_strike(slots, clouds)
            else:
                self._resolve_firestorm(slots, clouds)
        if self._state == self.STATE_ACTIVE:
            self._advance_phase()

    def _advance_phase(self) -> None:
        if self.current_phase == PHASE_INFERNO:
            self._inferno_next = FIRE_LAVA if self._inferno_next == FIRE_FIRESTORM else FIRE_FIRESTORM
        self._phase_index = (self._phase_index + 1) % len(PHASE_ORDER)
        self.current_phase = PHASE_ORDER[self._phase_index]
        self._fire_ability = None
        self._mark_indices = []

    def _clear_attack_target(self) -> None:
        self._target_slot_index = None
        self._target_x = None
        self._warning_remaining = 0.0
        self._mark_indices = []

    def _compute_mark_band(self, slots: Sequence[object], count: int) -> None:
        self._mark_indices = []
        center = self._target_slot_index
        if center is None:
            return
        planted = [i for i, s in enumerate(slots) if getattr(s, "seed", None) is not None and not getattr(s, "dead", False)]
        if not planted:
            return
        if center not in planted:
            center = min(planted, key=lambda i: abs(i - center))
        count = max(1, int(count))
        pos = planted.index(center)
        if len(planted) <= count:
            self._mark_indices = list(planted)
            return
        start = max(0, min(pos - count // 2, len(planted) - count))
        self._mark_indices = list(planted[start:start + count])

    @staticmethod
    def _living_planted(slots: Sequence[object]) -> list[object]:
        return [s for s in slots if getattr(s, "seed", None) is not None and not getattr(s, "dead", False)]

    @staticmethod
    def _sun_rect() -> pygame.Rect:
        return pygame.Rect(SUN_X - SUN_RADIUS, SUN_Y - SUN_RADIUS, SUN_RADIUS * 2, SUN_RADIUS * 2)

    @staticmethod
    def _slot_targetable(slots: Sequence[object], idx: int) -> bool:
        if idx < 0 or idx >= len(slots):
            return False
        slot = slots[idx]
        return getattr(slot, "seed", None) is not None and not getattr(slot, "dead", False) and isinstance(getattr(slot, "rect", None), pygame.Rect)

    def _blocking_cloud_for_x_mode(self, x: int, clouds: Iterable[object], *, require_rain: bool = False):
        blockers: list[object] = []
        for cloud in clouds:
            rect = getattr(cloud, "rect", None)
            if not isinstance(rect, pygame.Rect):
                continue
            if require_rain and not getattr(cloud, "raining", False):
                continue
            if rect.left <= x <= rect.right:
                blockers.append(cloud)
        return min(blockers, key=lambda c: c.rect.top) if blockers else None

    def _covering_sun_cloud(self, clouds: Iterable[object]):
        sun_rect = self._sun_rect()
        blockers: list[object] = []
        for cloud in clouds:
            rect = getattr(cloud, "rect", None)
            if not isinstance(rect, pygame.Rect):
                continue
            cover_fn = getattr(cloud, "covers_sun", None)
            covered = cover_fn(sun_rect) if callable(cover_fn) else rect.colliderect(sun_rect)
            if covered:
                blockers.append(cloud)
        return min(blockers, key=lambda c: c.rect.top) if blockers else None

    def _resolve_slot_strike(self, slots: Sequence[object], clouds: Iterable[object], *, require_rain: bool, aoe_radius: int, kill: bool) -> None:
        if self._target_slot_index is None or not self._slot_targetable(slots, self._target_slot_index):
            self._clear_attack_target()
            self._cooldown_remaining = float(self.config.strike_cooldown_seconds)
            return
        target_index = int(self._target_slot_index)
        slot_rect = slots[target_index].rect
        x = int(slot_rect.centerx)
        start_y = int(self.rect.bottom)
        blocker = self._blocking_cloud_for_x_mode(x, clouds, require_rain=require_rain)
        if blocker is not None:
            hit_y = max(int(blocker.rect.top), start_y)
            down = self._make_bolt(x, start_y, hit_y)
            up = self._make_bolt(x, hit_y, int(self.rect.centery))
            self._bolt_points = down + up[1:]
            self._bolt_flash_remaining = 0.32
            self._apply_block_damage(blocker, x)
        else:
            self._bolt_points = self._make_bolt(x, start_y, int(slot_rect.top))
            self._bolt_flash_remaining = 0.25
            self._register_unblocked(target_index)
            if kill:
                for idx in range(target_index - max(0, int(aoe_radius)), target_index + max(0, int(aoe_radius)) + 1):
                    if 0 <= idx < len(slots):
                        self._kill_slot(slots[idx])
        self._target_slot_index = None
        self._target_x = None
        self._cooldown_remaining = float(self.config.strike_cooldown_seconds)

    def _resolve_drought_strike(self, slots: Sequence[object], clouds: Iterable[object]) -> None:
        blocker = self._covering_sun_cloud(clouds)
        self._bolt_points = None
        self._bolt_flash_remaining = 0.30
        if blocker is not None:
            self._apply_block_damage(blocker, int(SUN_X), perfect_pos=(int(SUN_X), int(SUN_Y)))
        else:
            self._block_combo = 0
            self._took_unblocked_hit = True
            self._last_strike_result = "hit"
            for slot in self._living_planted(slots):
                try:
                    slot.sun = min(100.0, float(slot.sun) + INFERNO_HEAT_VEIL_SUN_SPIKE * 2.5)
                    slot.water = max(0.0, float(slot.water) - INFERNO_HEAT_VEIL_WATER_DRAIN * 3.0)
                except Exception:
                    pass
        self._cooldown_remaining = float(self.config.strike_cooldown_seconds)

    def _resolve_frost_strike(self, slots: Sequence[object], clouds: Iterable[object]) -> None:
        marks = [i for i in self._mark_indices if self._slot_targetable(slots, i)]
        self._mark_indices = []
        self._fire_marks = []
        if not marks:
            self._clear_attack_target()
            self._cooldown_remaining = float(self.config.strike_cooldown_seconds)
            return
        damage = 0
        blocked_count = 0
        perfect_count = 0
        any_unblocked = False
        first_perfect: tuple[int, int] | None = None
        visuals: list[tuple[int, int, bool, int, str]] = []
        for idx in marks:
            rect = slots[idx].rect
            x = int(rect.centerx)
            blocker = self._blocking_cloud_for_x_mode(x, clouds)
            if blocker is not None:
                blocked_count += 1
                damage += 1
                if abs(int(blocker.rect.centerx) - x) <= int(PERFECT_BLOCK_TOLERANCE_PX):
                    perfect_count += 1
                    damage += int(PERFECT_BLOCK_BONUS_DAMAGE)
                    first_perfect = first_perfect or (int(blocker.rect.centerx), int(blocker.rect.bottom))
                visuals.append((x, int(rect.top), True, max(int(blocker.rect.top), int(self.rect.bottom)), PHASE_FROST))
            else:
                any_unblocked = True
                self._register_unblocked(idx)
                self._freeze_slot(slots[idx])
                visuals.append((x, int(rect.top), False, int(rect.top), PHASE_FROST))
        self._finish_multi_mark(damage, blocked_count, perfect_count, any_unblocked, first_perfect)
        self._fire_marks = visuals
        self._bolt_points = None
        self._bolt_flash_remaining = 0.30
        self._clear_after_strike()

    def _resolve_firestorm(self, slots: Sequence[object], clouds: Iterable[object]) -> None:
        marks = [i for i in self._mark_indices if self._slot_targetable(slots, i)]
        self._mark_indices = []
        self._fire_marks = []
        if not marks:
            self._clear_attack_target()
            self._cooldown_remaining = float(self.config.strike_cooldown_seconds)
            return
        self._apply_heat_veil(slots)
        damage = 0
        blocked_count = 0
        perfect_count = 0
        any_unblocked = False
        first_perfect: tuple[int, int] | None = None
        visuals: list[tuple[int, int, bool, int, str]] = []
        for idx in marks:
            rect = slots[idx].rect
            x = int(rect.centerx)
            blocker = self._blocking_cloud_for_x_mode(x, clouds)
            if blocker is not None:
                blocked_count += 1
                damage += 1
                if abs(int(blocker.rect.centerx) - x) <= int(PERFECT_BLOCK_TOLERANCE_PX):
                    perfect_count += 1
                    damage += int(PERFECT_BLOCK_BONUS_DAMAGE)
                    first_perfect = first_perfect or (int(blocker.rect.centerx), int(blocker.rect.bottom))
                visuals.append((x, int(rect.top), True, max(int(blocker.rect.top), int(self.rect.bottom)), FIRE_FIRESTORM))
            else:
                any_unblocked = True
                self._register_unblocked(idx)
                self._scorch_slot(slots[idx], INFERNO_FIRESTORM_SCORCH_SECONDS, INFERNO_FIRESTORM_WATER_LOSS)
                self._burn_growth(slots[idx], INFERNO_FIRESTORM_GROWTH_LOSS)
                visuals.append((x, int(rect.top), False, int(rect.top), FIRE_FIRESTORM))
        self._finish_multi_mark(damage, blocked_count, perfect_count, any_unblocked, first_perfect)
        self._fire_marks = visuals
        self._bolt_points = None
        self._bolt_flash_remaining = 0.34
        self._clear_after_strike()

    def _resolve_lava_strike(self, slots: Sequence[object], clouds: Iterable[object]) -> None:
        if self._target_slot_index is None or not self._slot_targetable(slots, self._target_slot_index):
            self._clear_attack_target()
            self._cooldown_remaining = float(self.config.strike_cooldown_seconds)
            return
        idx = int(self._target_slot_index)
        rect = slots[idx].rect
        x = int(rect.centerx)
        blocker = self._blocking_cloud_for_x_mode(x, clouds)
        self._bolt_points = None
        if blocker is not None:
            self._fire_marks = [(x, int(rect.top), True, max(int(blocker.rect.top), int(self.rect.bottom)), FIRE_LAVA)]
            self._apply_block_damage(blocker, x)
        else:
            self._fire_marks = [(x, int(rect.top), False, int(rect.top), FIRE_LAVA)]
            self._register_unblocked(idx)
            self._scorch_slot(slots[idx], INFERNO_LAVA_SCORCH_SECONDS, INFERNO_LAVA_WATER_LOSS)
            self._burn_growth(slots[idx], INFERNO_LAVA_GROWTH_LOSS)
            salt_fn = getattr(slots[idx], "salt", None)
            if callable(salt_fn):
                salt_fn(INFERNO_LAVA_SALT_SECONDS)
        self._bolt_flash_remaining = 0.34
        self._clear_after_strike()

    def _apply_block_damage(self, blocker: object, x: int, *, perfect_pos: tuple[int, int] | None = None) -> None:
        is_perfect = abs(int(blocker.rect.centerx) - int(x)) <= int(PERFECT_BLOCK_TOLERANCE_PX)
        self._last_strike_result = "perfect" if is_perfect else "block"
        damage = 1
        if is_perfect:
            damage += int(PERFECT_BLOCK_BONUS_DAMAGE)
            self._last_perfect_at = pygame.time.get_ticks() / 1000.0
            self._last_perfect_pos = perfect_pos or (int(blocker.rect.centerx), int(blocker.rect.bottom))
        self._block_combo += 1
        if self._block_combo >= int(BOSS_COMBO_THRESHOLD):
            damage += int(BOSS_COMBO_DAMAGE_BONUS)
        self._blocks_since_poll += 1
        self._hp = max(0, self._hp - int(damage))
        if self._hp <= 0:
            self._begin_retreat()

    def _finish_multi_mark(self, damage: int, blocked_count: int, perfect_count: int, any_unblocked: bool, first_perfect: tuple[int, int] | None) -> None:
        if any_unblocked:
            self._last_strike_result = "hit"
        elif perfect_count > 0:
            self._last_strike_result = "perfect"
        else:
            self._last_strike_result = "block"
        if first_perfect is not None:
            self._last_perfect_pos = first_perfect
            self._last_perfect_at = pygame.time.get_ticks() / 1000.0
        if blocked_count > 0 and not any_unblocked:
            self._block_combo += 1
            if self._block_combo >= int(BOSS_COMBO_THRESHOLD):
                damage += int(BOSS_COMBO_DAMAGE_BONUS)
        elif any_unblocked:
            self._block_combo = 0
        if blocked_count > 0:
            self._blocks_since_poll += 1
        if damage > 0:
            self._hp = max(0, self._hp - int(damage))
            if self._hp <= 0:
                self._begin_retreat()

    def _register_unblocked(self, idx: int) -> None:
        self._block_combo = 0
        self._took_unblocked_hit = True
        self._last_strike_result = "hit"
        self._unblocked_hits_since_poll.append(int(idx))

    def _clear_after_strike(self) -> None:
        self._target_slot_index = None
        self._target_x = None
        self._cooldown_remaining = float(self.config.strike_cooldown_seconds)

    @staticmethod
    def _freeze_slot(slot: object) -> None:
        try:
            slot._frozen_seconds = max(float(getattr(slot, "_frozen_seconds", 0.0) or 0.0), INFERNO_FROST_FREEZE_SECONDS)
        except Exception:
            pass

    @staticmethod
    def _scorch_slot(slot: object, seconds: float, water_loss: float) -> None:
        scorch_fn = getattr(slot, "scorch", None)
        if callable(scorch_fn):
            scorch_fn(seconds, water_loss=water_loss)
            return
        try:
            slot.water = max(0.0, float(getattr(slot, "water", 50.0)) - float(water_loss))
            slot._scorch_seconds = max(float(getattr(slot, "_scorch_seconds", 0.0) or 0.0), float(seconds))
        except Exception:
            pass

    @staticmethod
    def _burn_growth(slot: object, stages: float) -> None:
        try:
            if hasattr(slot, "_growth_frames"):
                slot._growth_frames = max(0.0, float(slot._growth_frames) - float(stages))
            if hasattr(slot, "growth_stage"):
                slot.growth_stage = max(0, int(slot.growth_stage) - (1 if stages >= 0.7 else 0))
            slot._quality_eligible = False
        except Exception:
            pass

    @staticmethod
    def _apply_heat_veil(slots: Sequence[object]) -> None:
        for slot in slots:
            if getattr(slot, "seed", None) is None or getattr(slot, "dead", False):
                continue
            try:
                slot.sun = min(100.0, float(slot.sun) + INFERNO_HEAT_VEIL_SUN_SPIKE)
                slot.water = max(0.0, float(slot.water) - INFERNO_HEAT_VEIL_WATER_DRAIN)
            except Exception:
                pass

    def _phase_color(self) -> tuple[int, int, int]:
        return PHASE_COLORS.get(self.current_phase, PHASE_COLORS[PHASE_INFERNO])

    def draw_body(self, surface: pygame.Surface) -> None:
        super().draw_body(surface)
        if not self.visible:
            return
        cx, cy = self.rect.centerx, self.rect.centery
        color = self._phase_color()
        pulse = 0.5 + 0.5 * math.sin(self._anim_clock * math.tau * 1.4)
        aura = pygame.Surface((self.rect.width + 80, self.rect.height + 80), pygame.SRCALPHA)
        ar = aura.get_rect(center=(cx, cy))
        pygame.draw.ellipse(aura, (*color, int(40 + 35 * pulse)), aura.get_rect().inflate(-8, -16), 4)
        pygame.draw.circle(aura, (*color, 150), (aura.get_width() // 2, 28), 12)
        surface.blit(aura, ar.topleft)

    def draw_warning(self, surface: pygame.Surface, *, slots: Sequence[object]) -> None:
        if not self.visible or self._state != self.STATE_ACTIVE or self._warning_remaining <= 0.0:
            return
        phase = self.current_phase
        if phase == PHASE_DROUGHT:
            self._draw_drought_warning(surface)
        elif phase in (PHASE_FROST, PHASE_INFERNO) and self._mark_indices:
            self._draw_mark_warning(surface, slots)
        else:
            self._draw_single_slot_warning(surface, slots)

    def _warning_progress(self) -> float:
        total = max(0.001, float(self.config.strike_warning_seconds))
        return max(0.0, min(1.0, 1.0 - self._warning_remaining / total))

    def _draw_single_slot_warning(self, surface: pygame.Surface, slots: Sequence[object]) -> None:
        if self._target_slot_index is None or not (0 <= self._target_slot_index < len(slots)):
            return
        rect = getattr(slots[self._target_slot_index], "rect", None)
        if not isinstance(rect, pygame.Rect):
            return
        p = self._warning_progress()
        r = int(PERFECT_BLOCK_RING_MIN_RADIUS + (PERFECT_BLOCK_RING_MAX_RADIUS - PERFECT_BLOCK_RING_MIN_RADIUS) * (1.0 - p))
        color = self._phase_color()
        pygame.draw.circle(surface, PERFECT_BLOCK_RING_COLOR, rect.center, int(PERFECT_BLOCK_RING_MIN_RADIUS), 1)
        pygame.draw.circle(surface, color, rect.center, r, int(PERFECT_BLOCK_RING_WIDTH))
        pygame.draw.rect(surface, color, rect.inflate(8, 8), 2, border_radius=6)
        if self.current_phase == PHASE_CYCLONE:
            pygame.draw.arc(surface, color, rect.inflate(48, 48), self._anim_clock * 4.0, self._anim_clock * 4.0 + math.pi * 1.4, 4)
        if self.current_phase == PHASE_INFERNO and self._fire_ability == FIRE_LAVA:
            pygame.draw.polygon(surface, color, [(rect.centerx, rect.top - 18), (rect.centerx - 18, rect.top + 18), (rect.centerx + 18, rect.top + 18)])

    def _draw_mark_warning(self, surface: pygame.Surface, slots: Sequence[object]) -> None:
        rects = [slots[i].rect for i in self._mark_indices if 0 <= i < len(slots) and isinstance(getattr(slots[i], "rect", None), pygame.Rect)]
        if not rects:
            return
        p = self._warning_progress()
        color = self._phase_color()
        band = rects[0].unionall(rects[1:]).inflate(16, 18)
        haze = pygame.Surface((band.width, band.height), pygame.SRCALPHA)
        alpha = int((70 if self.current_phase == PHASE_INFERNO else 55) * max(0.2, p))
        haze.fill((*color, alpha))
        surface.blit(haze, band.topleft)
        r = int(PERFECT_BLOCK_RING_MIN_RADIUS + (PERFECT_BLOCK_RING_MAX_RADIUS - PERFECT_BLOCK_RING_MIN_RADIUS) * (1.0 - p))
        for rect in rects:
            pygame.draw.circle(surface, PERFECT_BLOCK_RING_COLOR, rect.center, int(PERFECT_BLOCK_RING_MIN_RADIUS), 1)
            pygame.draw.circle(surface, color, rect.center, r, int(PERFECT_BLOCK_RING_WIDTH))
            pygame.draw.rect(surface, color, rect.inflate(6, 6), 2, border_radius=6)
            if self.current_phase == PHASE_INFERNO:
                pygame.draw.line(surface, (255, 220, 120), (rect.centerx, rect.top - 16), (rect.centerx, rect.bottom + 8), 2)

    def _draw_drought_warning(self, surface: pygame.Surface) -> None:
        p = self._warning_progress()
        color = self._phase_color()
        r = int(SUN_RADIUS + 8 + (52 * (1.0 - p)))
        pygame.draw.circle(surface, PERFECT_BLOCK_RING_COLOR, (SUN_X, SUN_Y), SUN_RADIUS + 6, 1)
        pygame.draw.circle(surface, color, (SUN_X, SUN_Y), r, int(PERFECT_BLOCK_RING_WIDTH))
        field_w = SCREEN_W - UI_PANEL_W
        haze = pygame.Surface((field_w, surface.get_height()), pygame.SRCALPHA)
        haze.fill((255, 120, 35, int(75 * p)))
        surface.blit(haze, (0, 0))

    def draw_bolt(self, surface: pygame.Surface) -> None:
        if not self.visible or self._bolt_flash_remaining <= 0.0:
            return
        if self._fire_marks:
            self._draw_fire_marks(surface)
            return
        if self.current_phase == PHASE_DROUGHT or self._bolt_points is None:
            self._draw_sun_flare(surface)
            return
        super().draw_bolt(surface)

    def _draw_fire_marks(self, surface: pygame.Surface) -> None:
        t = max(0.0, min(1.0, self._bolt_flash_remaining / 0.34))
        for x, slot_top, blocked, impact_y, kind in self._fire_marks:
            color = PHASE_COLORS[PHASE_FROST] if kind == PHASE_FROST else PHASE_COLORS[PHASE_INFERNO]
            if kind == PHASE_FROST:
                for k in range(6):
                    ang = math.tau * k / 6.0
                    end = (int(x + math.cos(ang) * 36 * t), int(impact_y + math.sin(ang) * 24 * t))
                    pygame.draw.line(surface, (230, 250, 255), (x, impact_y), end, 2)
                continue
            pygame.draw.circle(surface, (255, 230, 120), (x, impact_y), int(10 + 26 * (1.0 - t)), 3)
            top = int(slot_top if not blocked else impact_y)
            for k in range(4):
                off = (k - 1.5) * 11
                pts = [(int(x + off), top + 26), (int(x + off - 12), top + 58), (int(x + off + 10), top + 58)]
                pygame.draw.polygon(surface, color, pts)
                pygame.draw.polygon(surface, (255, 205, 75), [(pts[0][0], pts[0][1] + 8), (pts[1][0] + 6, pts[1][1]), (pts[2][0] - 6, pts[2][1])])

    def _draw_sun_flare(self, surface: pygame.Surface) -> None:
        t = max(0.0, min(1.0, self._bolt_flash_remaining / 0.30))
        for k, rr in enumerate((SUN_RADIUS + 12, SUN_RADIUS + 32, SUN_RADIUS + 54)):
            layer = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
            pygame.draw.circle(layer, (255, 170, 50, int(150 * t / (k + 1))), (SUN_X, SUN_Y), int(rr), 4)
            surface.blit(layer, (0, 0))
        for i in range(12):
            ang = math.tau * i / 12.0
            end = (SUN_X + int(math.cos(ang) * (SUN_RADIUS + 72) * t), SUN_Y + int(math.sin(ang) * (SUN_RADIUS + 72) * t))
            pygame.draw.line(surface, (255, 220, 90), (SUN_X, SUN_Y), end, 2)

    @staticmethod
    def _draw_fallback_surface(w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        outline = (45, 15, 20)
        dark = (95, 24, 26, 245)
        fire = (235, 58, 26, 245)
        hot = (255, 190, 70, 250)
        cx = w // 2
        body = pygame.Rect(int(w * 0.14), int(h * 0.35), int(w * 0.72), int(h * 0.48))
        for i in range(9):
            x = int(w * (0.14 + i * 0.09))
            tip_y = int(h * (0.06 + 0.08 * (i % 3)))
            base_y = int(h * 0.46)
            pygame.draw.polygon(surf, fire if i % 2 else hot, [(x, base_y), (x + int(w * 0.05), tip_y), (x + int(w * 0.11), base_y)])
        pygame.draw.ellipse(surf, dark, body)
        pygame.draw.ellipse(surf, fire, body.inflate(-34, -28))
        pygame.draw.ellipse(surf, hot, pygame.Rect(int(w * 0.36), int(h * 0.43), int(w * 0.28), int(h * 0.22)))
        horn_l = [(int(w * 0.26), int(h * 0.42)), (int(w * 0.08), int(h * 0.20)), (int(w * 0.34), int(h * 0.32))]
        horn_r = [(int(w * 0.74), int(h * 0.42)), (int(w * 0.92), int(h * 0.20)), (int(w * 0.66), int(h * 0.32))]
        pygame.draw.polygon(surf, hot, horn_l)
        pygame.draw.polygon(surf, hot, horn_r)
        pygame.draw.ellipse(surf, outline, body, 4)
        eye = (25, 10, 10)
        pygame.draw.polygon(surf, eye, [(cx - 54, int(h * 0.56)), (cx - 22, int(h * 0.53)), (cx - 26, int(h * 0.62))])
        pygame.draw.polygon(surf, eye, [(cx + 54, int(h * 0.56)), (cx + 22, int(h * 0.53)), (cx + 26, int(h * 0.62))])
        pygame.draw.arc(surf, eye, pygame.Rect(cx - 46, int(h * 0.62), 92, 40), 3.35, 6.08, 4)
        return surf
