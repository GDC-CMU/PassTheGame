from __future__ import annotations

import os
import random
import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import pygame

from settings import (
    SCREEN_W,
    UI_PANEL_W,
    STORM_TITAN_WIDTH,
    STORM_TITAN_HEIGHT,
    STORM_TITAN_Y,
    STORM_TITAN_MAX_HP,
    STORM_TITAN_SPAWN_EVERY_SECONDS,
    STORM_TITAN_STRIKE_COOLDOWN_SECONDS,
    STORM_TITAN_STRIKE_WARNING_SECONDS,
    STORM_TITAN_RETREAT_SECONDS,
    STORM_TITAN_REWARD_ITEM_NAME,
    STORM_TITAN_REWARD_ITEM_COUNT,
    STORM_TITAN_LIGHTNING_KILLS_PLANT,
    STORM_TITAN_IMAGE_FILENAME,
    STORM_TITAN_SALT_SECONDS,
    STORM_TITAN_NODAMAGE_BONUS_ITEM_NAME,
    STORM_TITAN_NODAMAGE_BONUS_ITEM_COUNT,
    PERFECT_BLOCK_TOLERANCE_PX,
    PERFECT_BLOCK_BONUS_DAMAGE,
    PERFECT_BLOCK_RING_MAX_RADIUS,
    PERFECT_BLOCK_RING_MIN_RADIUS,
    PERFECT_BLOCK_RING_WIDTH,
    PERFECT_BLOCK_RING_COLOR,
    BOSS_COMBO_THRESHOLD,
    BOSS_COMBO_DAMAGE_BONUS,
    BOSS_DIFFICULTY_HP_PER_LEVEL,
    BOSS_DIFFICULTY_SPAWN_MULT_PER_LEVEL,
)
from items import ITEMS

PROPS_DIR = os.path.join(os.path.dirname(__file__), "props")


@dataclass(frozen=True)
class StormTitanConfig:
    """Tuning parameters for Storm Titan.

    Defaults are sourced from settings.py so contributors can tweak values
    without touching the boss code.
    """

    spawn_every_seconds: float = STORM_TITAN_SPAWN_EVERY_SECONDS
    max_hp: int = STORM_TITAN_MAX_HP

    strike_cooldown_seconds: float = STORM_TITAN_STRIKE_COOLDOWN_SECONDS
    strike_warning_seconds: float = STORM_TITAN_STRIKE_WARNING_SECONDS

    retreat_seconds: float = STORM_TITAN_RETREAT_SECONDS

    reward_item_name: str = STORM_TITAN_REWARD_ITEM_NAME
    reward_item_count: int = STORM_TITAN_REWARD_ITEM_COUNT

    width: int = STORM_TITAN_WIDTH
    height: int = STORM_TITAN_HEIGHT
    y: int = STORM_TITAN_Y

    lightning_kills_plant: bool = STORM_TITAN_LIGHTNING_KILLS_PLANT

    image_filename: str = STORM_TITAN_IMAGE_FILENAME

    warning_color: tuple[int, int, int] = (220, 70, 70)
    bolt_color: tuple[int, int, int] = (255, 235, 120)
    bolt_shadow_color: tuple[int, int, int] = (255, 255, 255)

    # Movement: boss slides horizontally to the target before striking.
    move_lerp_rate: float = 5.0
    align_epsilon_px: float = 4.0

    # Damage: when unblocked, also strike adjacent slots (0 = only the target).
    aoe_radius_slots: int = 0

    # UI: health bar size on the top HUD.
    health_bar_width: int = 360
    health_bar_height: int = 18

    # Unblocked-hit soil salt + clean-fight (no-damage) bonus reward.
    salt_seconds: float = STORM_TITAN_SALT_SECONDS
    no_damage_bonus_item_name: str = STORM_TITAN_NODAMAGE_BONUS_ITEM_NAME
    no_damage_bonus_item_count: int = STORM_TITAN_NODAMAGE_BONUS_ITEM_COUNT


class StormTitan(pygame.sprite.Sprite):
    """Storm Titan boss.

    Gameplay loop:
    - Waits off-screen until its spawn timer hits 0.
    - While active: targets a planted slot, warns briefly, then strikes lightning.
    - Any player cloud can block the strike by covering the target x-position.
      If blocked, the boss takes damage.
    - If unblocked, the plant is killed.
    - When defeated, the boss retreats after a short timer and drops a reward.
    """

    STATE_WAITING = "waiting"
    STATE_ACTIVE = "active"
    STATE_RETREATING = "retreating"

    # Identity (used by HUD labels and the progression system's SURVIVE_BOSS).
    boss_id = "storm"
    display_name = "Storm Titan"
    # The shared lightning SFX should only fire for lightning bosses.
    plays_lightning_sfx = True

    # Procedural animation tuning. These drive squash/stretch game-feel on the
    # single idle sprite: a calm idle bob, an anticipation swell during the
    # warning, and a quick lunge when the strike lands. Subclasses inherit these
    # and may override any of them.
    #
    # Idle: a slow vertical bob and a gentler horizontal sway, a few pixels each.
    ANIM_IDLE_BOB_PX = 3.0
    ANIM_IDLE_BOB_PERIOD = 2.6
    ANIM_IDLE_SWAY_PX = 2.0
    ANIM_IDLE_SWAY_PERIOD = 3.7
    # Windup: the body swells and rears upward while the strike charges.
    ANIM_WINDUP_SCALE = 1.08          # peak size right before the strike
    ANIM_WINDUP_STRETCH = 0.05        # extra vertical rear-up near the peak
    ANIM_WINDUP_RISE_PX = 6.0         # how far it pulls up while charging
    ANIM_CHARGE_TINT = 0.18           # brightness pulled from warning_color
    # Strike: a short lunge toward the target plus a scale pop, then it settles.
    ANIM_STRIKE_POP_SECONDS = 0.22
    ANIM_STRIKE_POP_SCALE = 1.12
    ANIM_STRIKE_LUNGE_PX = 14.0
    # Retreat: a gentle shrink layered on top of the existing fade.
    ANIM_RETREAT_SHRINK = 0.12
    ANIM_RETREAT_ALPHA = 150

    def __init__(
        self,
        config: StormTitanConfig | None = None,
        *,
        rng: random.Random | None = None,
    ):
        super().__init__()
        self.config = config or StormTitanConfig()
        self._rng = rng or random.Random()

        self.image = self._load_image_or_fallback()
        self.rect = self.image.get_rect()

        field_w = SCREEN_W - UI_PANEL_W
        self.rect.centerx = field_w // 2
        self.rect.top = self.config.y
        self._x = float(self.rect.centerx)
        self._target_x: float | None = None

        self._state = self.STATE_WAITING

        # Escalation hook (neutral defaults == current behavior); an external
        # progression system tunes these via set_difficulty()/enabled.
        self.enabled = True
        self._difficulty_level = 1
        self._hp_scale = 1.0
        self._spawn_scale = 1.0

        self._hp = self.max_hp

        self._spawn_remaining = float(self.config.spawn_every_seconds) * self._spawn_scale
        self._cooldown_remaining = 0.0
        self._warning_remaining = 0.0
        self._retreat_remaining = 0.0

        self._target_slot_index: int | None = None

        self._bolt_flash_remaining = 0.0
        self._bolt_points: list[tuple[int, int]] | None = None

        self._pending_reward = 0
        self._pending_bonus: list[tuple[str, int]] = []  # clean-fight rewards

        # Combat tracking (combo + clean-fight bonus).
        self._block_combo = 0
        self._took_unblocked_hit = False
        self._last_perfect_at: float | None = None
        # Outcome of the most recent strike: "perfect", "block", or "hit". Read by
        # the game on the bolt-flash frame to differentiate impact feedback.
        self._last_strike_result: str | None = None
        self._last_perfect_pos: tuple[int, int] | None = None  # where a perfect block landed

        # Monotonic event counters drained by the progression/Almanac system.
        self._blocks_since_poll = 0
        self._survived_since_poll = 0
        self._unblocked_hits_since_poll: list[int] = []

        # Procedural-animation state (purely cosmetic; never touches combat).
        # A stable per-boss phase keeps the three titans from bobbing in lockstep
        # without drawing from self._rng (so combat target/bolt rolls are
        # unchanged and deterministic).
        self._anim_clock = 0.0
        self._anim_phase = (sum(ord(c) for c in self.boss_id) % 360) * math.tau / 360.0
        self._strike_pop_remaining = 0.0
        self._anim_prev_bolt_flash = 0.0
        self._anim_frame_cache: tuple[tuple[int, int, int, int], pygame.Surface] | None = None
        self._anim_debug: dict | None = None  # last transform, for headless tests

    # ── status ──────────────────────────────────────────────────────────────
    @property
    def state(self) -> str:
        return self._state

    @property
    def hp(self) -> int:
        return self._hp

    @property
    def max_hp(self) -> int:
        return max(1, int(round(self.config.max_hp * self._hp_scale)))

    @property
    def visible(self) -> bool:
        return self._state in {self.STATE_ACTIVE, self.STATE_RETREATING}

    @property
    def seconds_until_spawn(self) -> float:
        return max(0.0, self._spawn_remaining) if self._state == self.STATE_WAITING else 0.0

    @property
    def seconds_until_leave(self) -> float:
        return max(0.0, self._retreat_remaining) if self._state == self.STATE_RETREATING else 0.0

    # ── battle logic ─────────────────────────────────────────────────────────
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
            if self._retreat_remaining <= 0.0:
                self._reset_to_waiting()
            return

        # active
        self._bolt_flash_remaining = max(0.0, self._bolt_flash_remaining - dt)
        moved_this_frame = False

        # If we have a target, keep our desired x synced and slide toward it.
        if self._target_slot_index is not None:
            slot = self._get_valid_target_slot(slots)
            if slot is None:
                self._target_slot_index = None
                self._target_x = None
                self._warning_remaining = 0.0
            else:
                rect = getattr(slot, "rect", None)
                if isinstance(rect, pygame.Rect):
                    self._target_x = float(rect.centerx)
                    self._smooth_move_x(dt)
                    moved_this_frame = True

        if self._warning_remaining > 0.0:
            self._warning_remaining -= dt
            if self._warning_remaining <= 0.0:
                # Snap the boss above the strike for a clean-looking hit.
                self._snap_to_target_x()
                self._resolve_strike(slots, clouds)
            return

        self._cooldown_remaining -= dt
        if self._cooldown_remaining > 0.0:
            return

        # Acquire a target if needed.
        if self._target_slot_index is None:
            self._choose_target(slots)
            if self._target_slot_index is None:
                # No plants to target; try again soon.
                self._cooldown_remaining = 1.0
                return

            slot = self._get_valid_target_slot(slots)
            rect = getattr(slot, "rect", None) if slot is not None else None
            if not isinstance(rect, pygame.Rect):
                self._target_slot_index = None
                self._cooldown_remaining = 1.0
                return
            self._target_x = float(rect.centerx)

        # Move toward our target, then start the warning once aligned.
        if self._target_x is not None:
            if not moved_this_frame:
                self._smooth_move_x(dt)
            if abs(self._x - self._target_x) <= float(self.config.align_epsilon_px):
                self._warning_remaining = float(self.config.strike_warning_seconds)

    def tick_spawn_timer(self, dt: float) -> None:
        """Advance spawn countdown while waiting, without spawning.

        Used by the game loop to keep other bosses' schedules moving while one
        boss fight is currently active.
        """
        if dt <= 0.0:
            return
        if self._state != self.STATE_WAITING:
            return
        self._spawn_remaining = max(0.0, self._spawn_remaining - dt)

    def pop_reward(self) -> list[tuple[str, int]]:
        out: list[tuple[str, int]] = []
        if self._pending_reward > 0:
            out.append((self.config.reward_item_name, int(self._pending_reward)))
            self._pending_reward = 0
        if self._pending_bonus:
            out.extend(self._pending_bonus)
            self._pending_bonus = []
        return out

    def set_difficulty(self, level: int) -> None:
        """Progression hook. Level 1 == current tuning; scales max HP (applied at
        the next fight) and spawn cadence (applied at the next wait)."""
        level = max(1, int(level))
        self._difficulty_level = level
        self._hp_scale = 1.0 + float(BOSS_DIFFICULTY_HP_PER_LEVEL) * (level - 1)
        self._spawn_scale = float(BOSS_DIFFICULTY_SPAWN_MULT_PER_LEVEL) ** (level - 1)

    def pop_blocks(self) -> int:
        n = self._blocks_since_poll
        self._blocks_since_poll = 0
        return n

    def pop_survived(self) -> int:
        n = self._survived_since_poll
        self._survived_since_poll = 0
        return n

    def pop_unblocked_hits(self) -> list[int]:
        """Slot indices struck by an unblocked hit since the last poll (for blight)."""
        hits = self._unblocked_hits_since_poll
        self._unblocked_hits_since_poll = []
        return hits

    @property
    def block_combo(self) -> int:
        return self._block_combo

    def force_spawn_now(self) -> None:
        """Cheat/debug helper: force the boss to appear immediately."""
        if self._state == self.STATE_ACTIVE:
            return
        self._spawn_remaining = 0.0
        self._retreat_remaining = 0.0
        self._begin_fight()

    def despawn_now(self) -> None:
        """Cheat/debug helper: remove the boss immediately."""
        self._reset_to_waiting()

    # ── drawing ─────────────────────────────────────────────────────────────
    def draw_body(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return

        anim = self._compute_anim()
        self._anim_debug = anim  # exposed for the headless animation harness

        base_w, base_h = self.image.get_size()
        sw = max(1, int(round(base_w * anim["scale_x"])))
        sh = max(1, int(round(base_h * anim["scale_y"])))
        tint = anim["tint"]
        alpha = anim["alpha"]

        # Fast path: plain idle bob with no scaling, tint or fade -> blit the
        # source straight (never mutated), just offset.
        if sw == base_w and sh == base_h and tint <= 0.0 and alpha >= 255:
            frame = self.image
        else:
            frame = self._anim_frame(sw, sh, tint, alpha)

        # Recenter on self.rect so scaling stays centered; self.rect itself is
        # left untouched, keeping collision/targeting stable.
        draw_rect = frame.get_rect()
        draw_rect.center = (
            self.rect.centerx + int(round(anim["off_x"])),
            self.rect.centery + int(round(anim["off_y"])),
        )
        surface.blit(frame, draw_rect)

    def _advance_anim(self, dt: float) -> None:
        """Advance the cosmetic animation clock and strike-lunge timer.

        Called once per frame from update_battle (including the Drought override)
        before any combat work, so it stays in sync with dt and never alters
        gameplay state.
        """
        if dt > 0.0:
            self._anim_clock += dt
            if self._strike_pop_remaining > 0.0:
                self._strike_pop_remaining = max(0.0, self._strike_pop_remaining - dt)
        # A fresh bolt flash is the tell that a strike just resolved (every
        # subclass sets _bolt_flash_remaining inside _resolve_strike). Detecting
        # the rising edge here means we trigger the lunge without touching any
        # combat code.
        if self._bolt_flash_remaining > self._anim_prev_bolt_flash + 1e-6:
            self._strike_pop_remaining = float(self.ANIM_STRIKE_POP_SECONDS)
        self._anim_prev_bolt_flash = self._bolt_flash_remaining

    def _compute_anim(self) -> dict:
        """Resolve the current frame's transform from the animation clock and the
        state machine. Returns scale, pixel offset, tint strength and alpha."""
        clock = self._anim_clock
        phase = self._anim_phase

        # Idle bob/sway: always on so the titan never looks frozen.
        bob = math.sin(clock * math.tau / self.ANIM_IDLE_BOB_PERIOD + phase) * self.ANIM_IDLE_BOB_PX
        sway = math.sin(clock * math.tau / self.ANIM_IDLE_SWAY_PERIOD + phase) * self.ANIM_IDLE_SWAY_PX

        scale_x = 1.0
        scale_y = 1.0
        off_x = sway
        off_y = bob
        tint = 0.0
        alpha = 255

        # Windup anticipation: ramp 0 -> 1 across the warning window, swelling and
        # rearing up so a strike clearly reads as incoming.
        if self._state == self.STATE_ACTIVE and self._warning_remaining > 0.0:
            warn_total = max(0.001, float(self.config.strike_warning_seconds))
            p = max(0.0, min(1.0, 1.0 - self._warning_remaining / warn_total))
            ease = p * p  # slow build, snappier as the strike nears
            swell = 1.0 + (self.ANIM_WINDUP_SCALE - 1.0) * ease
            scale_x *= swell * (1.0 - self.ANIM_WINDUP_STRETCH * 0.5 * ease)
            scale_y *= swell * (1.0 + self.ANIM_WINDUP_STRETCH * ease)
            off_y -= self.ANIM_WINDUP_RISE_PX * ease
            tint = self.ANIM_CHARGE_TINT * ease

        # Strike: a brief lunge toward the target plus a scale pop that decays
        # over ANIM_STRIKE_POP_SECONDS, then settles back to idle.
        if self._strike_pop_remaining > 0.0:
            q = max(0.0, min(1.0, self._strike_pop_remaining / float(self.ANIM_STRIKE_POP_SECONDS)))
            pop = (self.ANIM_STRIKE_POP_SCALE - 1.0) * q
            scale_y *= 1.0 + pop
            scale_x *= 1.0 - pop * 0.5
            off_y += self.ANIM_STRIKE_LUNGE_PX * q
            tint = max(tint, self.ANIM_CHARGE_TINT * q)

        # Retreat: keep the existing fade and add a gentle shrink as it leaves.
        if self._state == self.STATE_RETREATING:
            alpha = int(self.ANIM_RETREAT_ALPHA)
            total = max(0.001, float(self.config.retreat_seconds))
            pr = max(0.0, min(1.0, 1.0 - self._retreat_remaining / total))
            shrink = 1.0 - self.ANIM_RETREAT_SHRINK * pr
            scale_x *= shrink
            scale_y *= shrink

        return {
            "scale_x": scale_x,
            "scale_y": scale_y,
            "off_x": off_x,
            "off_y": off_y,
            "tint": tint,
            "alpha": alpha,
        }

    def _anim_frame(self, sw: int, sh: int, tint: float, alpha: int) -> pygame.Surface:
        """Build (and cache) a transformed copy of self.image. Never mutates the
        source surface."""
        tint_level = int(round(max(0.0, tint) * 12.0))  # quantize to keep the cache useful
        alpha_level = max(0, min(255, int(alpha)))
        key = (int(sw), int(sh), tint_level, alpha_level)

        cached = self._anim_frame_cache
        if cached is not None and cached[0] == key:
            return cached[1]

        if (sw, sh) == self.image.get_size():
            frame = self.image.copy()
        else:
            frame = pygame.transform.smoothscale(self.image, (sw, sh))

        if tint_level > 0:
            amount = tint_level / 12.0
            wc = self.config.warning_color
            add = (int(wc[0] * amount), int(wc[1] * amount), int(wc[2] * amount), 0)
            frame.fill(add, special_flags=pygame.BLEND_RGB_ADD)

        if alpha_level < 255:
            frame.set_alpha(alpha_level)

        self._anim_frame_cache = (key, frame)
        return frame

    def draw_bolt(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        if self._bolt_flash_remaining <= 0.0 or not self._bolt_points:
            return

        pygame.draw.lines(surface, self.config.bolt_shadow_color, False, self._bolt_points, 6)
        pygame.draw.lines(surface, self.config.bolt_color, False, self._bolt_points, 3)

    def draw_warning(self, surface: pygame.Surface, *, slots: Sequence[object]) -> None:
        if not self.visible:
            return
        if self._state != self.STATE_ACTIVE:
            return
        if self._warning_remaining <= 0.0:
            return
        if self._target_slot_index is None:
            return
        if self._target_slot_index < 0 or self._target_slot_index >= len(slots):
            return

        slot = slots[self._target_slot_index]
        rect = getattr(slot, "rect", None)
        if not isinstance(rect, pygame.Rect):
            return

        # Shrinking reticle: the ring collapses onto the lock zone exactly at the
        # strike, teaching the player to center a cloud inside it as it locks.
        warn_total = max(0.001, float(self.config.strike_warning_seconds))
        p = max(0.0, min(1.0, 1.0 - self._warning_remaining / warn_total))  # 0 -> 1
        r_max, r_min = int(PERFECT_BLOCK_RING_MAX_RADIUS), int(PERFECT_BLOCK_RING_MIN_RADIUS)
        radius = int(r_min + (r_max - r_min) * (1.0 - p))
        wc, lc = self.config.warning_color, PERFECT_BLOCK_RING_COLOR
        color = tuple(int(wc[i] + (lc[i] - wc[i]) * p) for i in range(3))
        cx, cy = rect.center
        pygame.draw.circle(surface, color, (cx, cy), r_min, 1)  # static lock zone
        pygame.draw.circle(surface, color, (cx, cy), radius, int(PERFECT_BLOCK_RING_WIDTH))
        pygame.draw.rect(surface, self.config.warning_color, rect.inflate(6, 6), 2, border_radius=6)

    # ── internals ───────────────────────────────────────────────────────────
    def _begin_fight(self) -> None:
        self._state = self.STATE_ACTIVE
        self._hp = self.max_hp
        self._cooldown_remaining = 0.5
        self._warning_remaining = 0.0
        self._target_slot_index = None
        self._target_x = None
        self._bolt_flash_remaining = 0.0
        self._bolt_points = None
        self._block_combo = 0
        self._took_unblocked_hit = False

    def _begin_retreat(self) -> None:
        self._state = self.STATE_RETREATING
        self._retreat_remaining = float(self.config.retreat_seconds)
        self._cooldown_remaining = 0.0
        self._warning_remaining = 0.0
        self._target_slot_index = None
        self._target_x = None
        # Clear any in-flight strike bolt so it does not linger on screen through
        # the whole retreat (the retreat state skips the per-frame bolt decay).
        self._bolt_flash_remaining = 0.0
        self._bolt_points = None
        if self.config.reward_item_count > 0:
            self._pending_reward += int(self.config.reward_item_count)
        # Clean fight: defeated without losing a single plant → bonus reward.
        if not self._took_unblocked_hit and int(self.config.no_damage_bonus_item_count) > 0:
            self._pending_bonus.append(
                (self.config.no_damage_bonus_item_name, int(self.config.no_damage_bonus_item_count))
            )
        self._survived_since_poll += 1

    def _reset_to_waiting(self) -> None:
        self._state = self.STATE_WAITING
        self._spawn_remaining = float(self.config.spawn_every_seconds) * self._spawn_scale
        self._cooldown_remaining = 0.0
        self._warning_remaining = 0.0
        self._retreat_remaining = 0.0
        self._target_slot_index = None
        self._target_x = None
        self._bolt_flash_remaining = 0.0
        self._bolt_points = None
        self._block_combo = 0
        self._took_unblocked_hit = False

    def _slot_value(self, slot) -> int:
        seed = getattr(slot, "seed", None)
        if seed is None:
            return 0
        item = ITEMS.get(getattr(seed, "product_name", None))
        price = int(getattr(item, "sell_price", 0)) if item else 0
        return price * max(1, int(getattr(seed, "harvest_yield", 1)))

    def _choose_target(self, slots: Sequence[object]) -> None:
        candidates: list[int] = []
        for idx, slot in enumerate(slots):
            if getattr(slot, "seed", None) is None:
                continue
            if getattr(slot, "dead", False):
                continue
            candidates.append(idx)

        if not candidates:
            self._target_slot_index = None
            return

        # Target the player's most valuable planted slot (random tie-break, and
        # random fallback if values are unavailable).
        values = [self._slot_value(slots[i]) for i in candidates]
        best = max(values)
        if best <= 0:
            self._target_slot_index = self._rng.choice(candidates)
            return
        top = [i for i, v in zip(candidates, values) if v == best]
        self._target_slot_index = self._rng.choice(top)

    def _get_valid_target_slot(self, slots: Sequence[object]):
        if self._target_slot_index is None:
            return None
        if self._target_slot_index < 0 or self._target_slot_index >= len(slots):
            return None
        slot = slots[self._target_slot_index]
        if getattr(slot, "seed", None) is None:
            return None
        if getattr(slot, "dead", False):
            return None
        rect = getattr(slot, "rect", None)
        if not isinstance(rect, pygame.Rect):
            return None
        return slot

    def _smooth_move_x(self, dt: float) -> None:
        if self._target_x is None:
            return

        # Exponential smoothing. Rate is in 1/seconds.
        rate = max(0.0, float(self.config.move_lerp_rate))
        if rate <= 0.0:
            self._x = float(self._target_x)
        else:
            alpha = 1.0 - math.exp(-rate * dt)
            self._x = (1.0 - alpha) * self._x + alpha * float(self._target_x)

        self.rect.centerx = int(round(self._x))

    def _snap_to_target_x(self) -> None:
        if self._target_x is None:
            return
        self._x = float(self._target_x)
        self.rect.centerx = int(round(self._x))

    def _resolve_strike(self, slots: Sequence[object], clouds: Iterable[object]) -> None:
        if self._target_slot_index is None:
            self._cooldown_remaining = float(self.config.strike_cooldown_seconds)
            return

        if self._target_slot_index < 0 or self._target_slot_index >= len(slots):
            self._target_slot_index = None
            self._cooldown_remaining = float(self.config.strike_cooldown_seconds)
            return

        target_index = self._target_slot_index
        slot = slots[target_index]
        slot_rect = getattr(slot, "rect", None)
        if not isinstance(slot_rect, pygame.Rect):
            self._target_slot_index = None
            self._cooldown_remaining = float(self.config.strike_cooldown_seconds)
            return

        x = int(slot_rect.centerx)
        start_y = int(self.rect.bottom)

        blocking_cloud = self._blocking_cloud_for_x(x, clouds)
        bolt_points: list[tuple[int, int]]
        if blocking_cloud is not None:
            hit_y = max(int(blocking_cloud.rect.top), start_y)
            down = self._make_bolt(x, start_y, hit_y)
            up = self._make_bolt(x, hit_y, int(self.rect.centery))
            bolt_points = down + up[1:]
            self._bolt_flash_remaining = 0.32
        else:
            hit_y = int(slot_rect.top)
            bolt_points = self._make_bolt(x, start_y, hit_y)
            self._bolt_flash_remaining = 0.25

        self._bolt_points = bolt_points

        if blocking_cloud is not None:
            # Position-based perfect block: the blocking cloud is centered on the
            # target at strike time (skill, not rain-toggle timing).
            is_perfect = abs(int(blocking_cloud.rect.centerx) - x) <= int(PERFECT_BLOCK_TOLERANCE_PX)
            self._last_strike_result = "perfect" if is_perfect else "block"
            if is_perfect:
                self._last_perfect_pos = (int(blocking_cloud.rect.centerx), int(blocking_cloud.rect.bottom))
            damage = 1
            if is_perfect:
                damage += int(PERFECT_BLOCK_BONUS_DAMAGE)
                self._last_perfect_at = pygame.time.get_ticks() / 1000.0
            self._block_combo += 1
            if self._block_combo >= int(BOSS_COMBO_THRESHOLD):
                damage += int(BOSS_COMBO_DAMAGE_BONUS)
            self._blocks_since_poll += 1
            self._hp = max(0, self._hp - int(damage))
            if self._hp <= 0:
                self._begin_retreat()
        else:
            self._block_combo = 0
            self._took_unblocked_hit = True
            self._last_strike_result = "hit"
            self._unblocked_hits_since_poll.append(int(target_index))
            if self.config.lightning_kills_plant:
                radius = max(0, int(getattr(self.config, "aoe_radius_slots", 0)))
                for idx in range(target_index - radius, target_index + radius + 1):
                    if idx < 0 or idx >= len(slots):
                        continue
                    self._kill_slot(slots[idx])

        self._target_slot_index = None
        self._target_x = None
        self._cooldown_remaining = float(self.config.strike_cooldown_seconds)

    def _kill_slot(self, slot: object) -> None:
        if getattr(slot, "seed", None) is None:
            return
        if getattr(slot, "dead", False):
            return
        strike_fn = getattr(slot, "strike_lightning", None)
        if callable(strike_fn):
            try:
                strike_fn(salt_seconds=float(self.config.salt_seconds))
            except TypeError:
                strike_fn()  # older signature without salt
            return
        # Fallback for older PlantSlot shapes
        try:
            slot.dead = True
        except Exception:
            pass

    @staticmethod
    def _blocking_cloud_for_x(x: int, clouds: Iterable[object]):
        blockers: list[object] = []
        for cloud in clouds:
            rect = getattr(cloud, "rect", None)
            if not isinstance(rect, pygame.Rect):
                continue
            if rect.left <= x <= rect.right:
                blockers.append(cloud)

        if not blockers:
            return None

        # Highest cloud blocks first.
        return min(blockers, key=lambda c: c.rect.top)

    def _make_bolt(self, x: int, start_y: int, end_y: int) -> list[tuple[int, int]]:
        segments = 7
        points: list[tuple[int, int]] = [(x, start_y)]
        dy = end_y - start_y
        sign = 1 if dy >= 0 else -1
        height = max(1, abs(dy))
        for i in range(1, segments):
            t = i / segments
            y = start_y + sign * int(height * t)
            jitter = int(14 * (1.0 - t))
            points.append((x + self._rng.randint(-jitter, jitter), y))
        points.append((x, end_y))
        return points

    # ── visuals ─────────────────────────────────────────────────────────────
    def _load_image_or_fallback(self) -> pygame.Surface:
        img_path = os.path.join(PROPS_DIR, self.config.image_filename)
        if os.path.exists(img_path):
            try:
                raw = pygame.image.load(img_path)
                try:
                    raw = raw.convert_alpha()
                except pygame.error:
                    # convert_alpha may fail if display isn't initialized.
                    pass
                return pygame.transform.smoothscale(raw, (self.config.width, self.config.height))
            except Exception:
                pass
        return self._draw_fallback_surface(self.config.width, self.config.height)

    @staticmethod
    def _draw_fallback_surface(w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Cloud body
        base = (120, 125, 140, 240)
        pygame.draw.ellipse(surf, base, pygame.Rect(10, h // 2 - 8, w - 20, h // 2 + 12))
        pygame.draw.ellipse(surf, base, pygame.Rect(10, 18, int(w * 0.38), int(h * 0.62)))
        pygame.draw.ellipse(surf, base, pygame.Rect(int(w * 0.28), 0, int(w * 0.44), int(h * 0.68)))
        pygame.draw.ellipse(surf, base, pygame.Rect(int(w * 0.62), 16, int(w * 0.32), int(h * 0.58)))

        # Angry face
        eye = (25, 25, 30)
        left_eye = pygame.Rect(int(w * 0.33), int(h * 0.46), 18, 10)
        right_eye = pygame.Rect(int(w * 0.58), int(h * 0.46), 18, 10)
        pygame.draw.ellipse(surf, eye, left_eye)
        pygame.draw.ellipse(surf, eye, right_eye)

        pygame.draw.line(surf, eye, (left_eye.left - 2, left_eye.top - 6), (left_eye.right + 4, left_eye.top - 2), 3)
        pygame.draw.line(surf, eye, (right_eye.left - 4, right_eye.top - 2), (right_eye.right + 2, right_eye.top - 6), 3)

        pygame.draw.arc(
            surf,
            eye,
            pygame.Rect(int(w * 0.40), int(h * 0.56), int(w * 0.22), int(h * 0.18)),
            3.4,
            6.0,
            3,
        )

        return surf
