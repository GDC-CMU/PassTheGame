from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import pygame

from settings import (
    FROST_TITAN_WIDTH,
    FROST_TITAN_HEIGHT,
    FROST_TITAN_Y,
    FROST_TITAN_MAX_HP,
    FROST_TITAN_SPAWN_EVERY_SECONDS,
    FROST_TITAN_STRIKE_COOLDOWN_SECONDS,
    FROST_TITAN_STRIKE_WARNING_SECONDS,
    FROST_TITAN_RETREAT_SECONDS,
    FROST_TITAN_MARK_COUNT,
    FROST_TITAN_FREEZE_SECONDS,
    FROST_TITAN_REWARD_ITEM_NAME,
    FROST_TITAN_REWARD_ITEM_COUNT,
    FROST_TITAN_NODAMAGE_BONUS_ITEM_NAME,
    FROST_TITAN_NODAMAGE_BONUS_ITEM_COUNT,
    FROST_TITAN_IMAGE_FILENAME,
    PERFECT_BLOCK_TOLERANCE_PX,
    PERFECT_BLOCK_BONUS_DAMAGE,
    PERFECT_BLOCK_RING_MAX_RADIUS,
    PERFECT_BLOCK_RING_MIN_RADIUS,
    PERFECT_BLOCK_RING_WIDTH,
    PERFECT_BLOCK_RING_COLOR,
    BOSS_COMBO_THRESHOLD,
    BOSS_COMBO_DAMAGE_BONUS,
)
from storm_titan import StormTitan, StormTitanConfig


@dataclass(frozen=True)
class FrostTitanConfig(StormTitanConfig):
    """Tuning for the Frost Titan, the winter (4th) seasonal boss.

    Instead of striking a single slot it marks a contiguous band of planted slots
    wider than the player's two clouds can cover at once, forcing a choice of
    which crops to sacrifice. An unblocked mark freezes the slot's growth; it
    does not kill the plant.
    """

    spawn_every_seconds: float = FROST_TITAN_SPAWN_EVERY_SECONDS
    max_hp: int = FROST_TITAN_MAX_HP

    strike_cooldown_seconds: float = FROST_TITAN_STRIKE_COOLDOWN_SECONDS
    strike_warning_seconds: float = FROST_TITAN_STRIKE_WARNING_SECONDS

    retreat_seconds: float = FROST_TITAN_RETREAT_SECONDS

    width: int = FROST_TITAN_WIDTH
    height: int = FROST_TITAN_HEIGHT
    y: int = FROST_TITAN_Y

    reward_item_name: str = FROST_TITAN_REWARD_ITEM_NAME
    reward_item_count: int = FROST_TITAN_REWARD_ITEM_COUNT
    no_damage_bonus_item_name: str = FROST_TITAN_NODAMAGE_BONUS_ITEM_NAME
    no_damage_bonus_item_count: int = FROST_TITAN_NODAMAGE_BONUS_ITEM_COUNT

    image_filename: str = FROST_TITAN_IMAGE_FILENAME

    # It freezes the crop instead of killing it; no one-shot kill.
    lightning_kills_plant: bool = False

    # Multi-mark tuning.
    mark_count: int = FROST_TITAN_MARK_COUNT
    freeze_seconds: float = FROST_TITAN_FREEZE_SECONDS

    # Cold palette (a charge tint pulled from warning_color while it winds up).
    warning_color: tuple[int, int, int] = (120, 190, 235)   # pale ice blue
    bolt_color: tuple[int, int, int] = (210, 240, 255)      # icy white-blue
    bolt_shadow_color: tuple[int, int, int] = (255, 255, 255)

    health_bar_width: int = 440
    health_bar_height: int = 20

    move_lerp_rate: float = 4.0


class FrostTitan(StormTitan):
    """Frost Titan: winter boss that paints a band of adjacent crop slots wider
    than two clouds can cover.

    Each mark is blocked independently by a cloud over that slot's x at strike
    time (a cloud centered within PERFECT_BLOCK_TOLERANCE_PX is a perfect block).
    With only two clouds the player cannot save every mark, so some always land;
    an unblocked mark freezes that crop's growth (cozy, not a kill) and is fed to
    the game's existing blight path via pop_unblocked_hits().
    """

    boss_id = "frost"
    display_name = "Frost Titan"
    # No thunderclap of its own; it reuses the shared strike SFX as an ice crack.
    plays_lightning_sfx = True

    def __init__(self, config: FrostTitanConfig | None = None, *, rng=None):
        super().__init__(config or FrostTitanConfig(), rng=rng)
        # Slot indices marked for the current volley; telegraphed during warning
        # and frozen at warning start so the reticles match what the strike hits.
        self._mark_indices: list[int] = []
        # Per-mark resolved visuals captured at strike time for draw_bolt:
        # (x, slot_top_y, blocked, impact_y).
        self._frost_marks: list[tuple[int, int, bool, int]] = []

    # ── battle loop (thin override: lock in the band when the warning opens) ───
    def update_battle(self, dt: float, *, slots: Sequence[object], clouds: Iterable[object]) -> None:
        warn_before = self._warning_remaining
        super().update_battle(dt, slots=slots, clouds=clouds)
        if dt <= 0.0:
            return
        # The base stops decrementing the bolt flash once it leaves the active
        # state, so fade the death-strike frost shards out during the retreat.
        if self._state == self.STATE_RETREATING:
            self._bolt_flash_remaining = max(0.0, self._bolt_flash_remaining - dt)
        # The base opens the warning window once aligned over the center target.
        # Snapshot the marked band exactly then so the telegraph is stable.
        if warn_before <= 0.0 and self._warning_remaining > 0.0:
            self._compute_marks(slots)

    def _compute_marks(self, slots: Sequence[object]) -> None:
        """Pick a contiguous band of mark_count planted slots centered on the
        current (most valuable) target, clamped to the planted run."""
        self._mark_indices = []
        center = self._target_slot_index
        if center is None:
            return

        planted = [
            i for i, s in enumerate(slots)
            if getattr(s, "seed", None) is not None and not getattr(s, "dead", False)
        ]
        if not planted:
            return
        if center not in planted:
            center = min(planted, key=lambda i: abs(i - center))

        count = max(1, int(self.config.mark_count))
        pos = planted.index(center)
        if len(planted) <= count:
            self._mark_indices = list(planted)
            return

        start = pos - count // 2
        start = max(0, min(start, len(planted) - count))
        self._mark_indices = list(planted[start:start + count])

    # ── multi-mark strike resolution ──────────────────────────────────────────
    def _resolve_strike(self, slots: Sequence[object], clouds: Iterable[object]) -> None:
        marks = [i for i in self._mark_indices if self._slot_targetable(slots, i)]
        self._mark_indices = []

        if not marks:
            self._frost_marks = []
            self._target_slot_index = None
            self._target_x = None
            self._cooldown_remaining = float(self.config.strike_cooldown_seconds)
            return

        damage = 0
        blocked_count = 0
        perfect_count = 0
        any_unblocked = False
        first_perfect_pos: tuple[int, int] | None = None
        frost_marks: list[tuple[int, int, bool, int]] = []

        for idx in marks:
            rect = slots[idx].rect
            x = int(rect.centerx)
            blocker = self._blocking_cloud_for_x(x, clouds)
            if blocker is not None:
                blocked_count += 1
                damage += 1
                is_perfect = abs(int(blocker.rect.centerx) - x) <= int(PERFECT_BLOCK_TOLERANCE_PX)
                if is_perfect:
                    perfect_count += 1
                    damage += int(PERFECT_BLOCK_BONUS_DAMAGE)
                    if first_perfect_pos is None:
                        first_perfect_pos = (int(blocker.rect.centerx), int(blocker.rect.bottom))
                impact_y = max(int(blocker.rect.top), int(self.rect.bottom))
                frost_marks.append((x, int(rect.top), True, impact_y))
            else:
                any_unblocked = True
                self._took_unblocked_hit = True
                self._unblocked_hits_since_poll.append(int(idx))
                self._freeze_slot(slots[idx])
                frost_marks.append((x, int(rect.top), False, int(rect.top)))

        self._frost_marks = frost_marks
        self._bolt_points = None
        self._bolt_flash_remaining = 0.30  # drives the frost-flash + strike lunge

        # Result tag the game reads on the flash frame for impact feedback. Any
        # landed mark means the volley overall "hit"; otherwise it is a clean
        # block, upgraded to "perfect" if at least one mark was a perfect block.
        if any_unblocked:
            self._last_strike_result = "hit"
        elif perfect_count > 0:
            self._last_strike_result = "perfect"
        else:
            self._last_strike_result = "block"
        if first_perfect_pos is not None:
            self._last_perfect_pos = first_perfect_pos
            self._last_perfect_at = pygame.time.get_ticks() / 1000.0

        # Combo: only a fully blocked volley extends the streak; any landed mark
        # breaks it. This mirrors the base single-mark combo, made fittingly
        # harder for a multi-mark attack.
        if blocked_count > 0 and not any_unblocked:
            self._block_combo += 1
            if self._block_combo >= int(BOSS_COMBO_THRESHOLD):
                damage += int(BOSS_COMBO_DAMAGE_BONUS)
        elif any_unblocked:
            self._block_combo = 0

        # One block event per defended strike keeps frost's Almanac cadence in
        # line with the other bosses (it does not count each mark separately).
        if blocked_count > 0:
            self._blocks_since_poll += 1

        if damage > 0:
            self._hp = max(0, self._hp - int(damage))
            if self._hp <= 0:
                self._begin_retreat()

        self._target_slot_index = None
        self._target_x = None
        self._cooldown_remaining = float(self.config.strike_cooldown_seconds)

    # ── helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _slot_targetable(slots: Sequence[object], idx: int) -> bool:
        if idx < 0 or idx >= len(slots):
            return False
        slot = slots[idx]
        if getattr(slot, "seed", None) is None or getattr(slot, "dead", False):
            return False
        return isinstance(getattr(slot, "rect", None), pygame.Rect)

    def _freeze_slot(self, slot: object) -> None:
        """Stall this slot's growth for freeze_seconds without killing it. The
        slot-side growth stall + visual are wired on the PlantSlot; here we only
        set/refresh the data."""
        try:
            prev = float(getattr(slot, "_frozen_seconds", 0.0) or 0.0)
        except (TypeError, ValueError):
            prev = 0.0
        try:
            slot._frozen_seconds = max(prev, float(self.config.freeze_seconds))
        except Exception:
            pass

    # ── telegraph: one cold reticle per marked slot + a band shimmer ──────────
    def draw_warning(self, surface: pygame.Surface, *, slots: Sequence[object]) -> None:
        if not self.visible:
            return
        if self._state != self.STATE_ACTIVE or self._warning_remaining <= 0.0:
            return
        if not self._mark_indices:
            return

        warn_total = max(0.001, float(self.config.strike_warning_seconds))
        p = max(0.0, min(1.0, 1.0 - self._warning_remaining / warn_total))  # 0 -> 1
        r_max, r_min = int(PERFECT_BLOCK_RING_MAX_RADIUS), int(PERFECT_BLOCK_RING_MIN_RADIUS)
        radius = int(r_min + (r_max - r_min) * (1.0 - p))
        wc, lc = self.config.warning_color, PERFECT_BLOCK_RING_COLOR
        color = tuple(int(wc[i] + (lc[i] - wc[i]) * p) for i in range(3))

        rects: list[pygame.Rect] = []
        for idx in self._mark_indices:
            if idx < 0 or idx >= len(slots):
                continue
            rect = getattr(slots[idx], "rect", None)
            if isinstance(rect, pygame.Rect):
                rects.append(rect)
        if not rects:
            return

        # Faint frost shimmer over the whole marked band, so the volley reads as
        # one coordinated AoE the player must split two clouds across.
        if p > 0.0:
            band = rects[0].unionall(rects[1:]).inflate(14, 14)
            shimmer = pygame.Surface((band.width, band.height), pygame.SRCALPHA)
            shimmer.fill((wc[0], wc[1], wc[2], int(60 * p)))
            surface.blit(shimmer, band.topleft)

        # One shrinking reticle per marked slot (reused from the base approach).
        for rect in rects:
            cx, cy = rect.center
            pygame.draw.circle(surface, color, (cx, cy), r_min, 1)  # static lock zone
            pygame.draw.circle(surface, color, (cx, cy), radius, int(PERFECT_BLOCK_RING_WIDTH))
            pygame.draw.rect(surface, wc, rect.inflate(6, 6), 2, border_radius=6)

    # ── strike flash: ice shards / cracks at each mark (no lightning) ─────────
    def draw_bolt(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        if self._bolt_flash_remaining <= 0.0 or not self._frost_marks:
            return

        t = max(0.0, min(1.0, self._bolt_flash_remaining / 0.30))
        for x, slot_top, blocked, impact_y in self._frost_marks:
            self._draw_frost_shards(surface, int(x), int(impact_y), bool(blocked), t)

    def _draw_frost_shards(self, surface: pygame.Surface, x: int, impact_y: int, blocked: bool, t: float) -> None:
        bolt = self.config.bolt_color
        glow = self.config.bolt_shadow_color

        # A cold burst ring at the impact point.
        overlay = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        ring_r = int(10 + 26 * (1.0 - t))
        pygame.draw.circle(overlay, (bolt[0], bolt[1], bolt[2], int(150 * t)), (x, impact_y), ring_r, 3)
        surface.blit(overlay, (0, 0))

        # Six radiating ice shards. Angles are fixed (no self._rng) so drawing can
        # never perturb the deterministic combat roll stream.
        reach = int(20 + 26 * t)
        spin = 0.0 if blocked else 0.4
        for k in range(6):
            ang = math.tau * (k / 6.0) + spin
            x2 = int(x + math.cos(ang) * reach)
            y2 = int(impact_y + math.sin(ang) * reach * 0.7)
            mid = (
                int(x + math.cos(ang) * reach * 0.5) + (4 if k % 2 else -4),
                int(impact_y + math.sin(ang) * reach * 0.35),
            )
            pygame.draw.lines(surface, glow, False, [(x, impact_y), mid, (x2, y2)], 3)
            pygame.draw.lines(surface, bolt, False, [(x, impact_y), mid, (x2, y2)], 1)

        # An icicle falling from the titan onto the crop for an unblocked mark, or
        # a short deflection spark where a cloud caught it.
        if blocked:
            pygame.draw.line(surface, bolt, (x, impact_y), (x, impact_y - 14), 2)
        else:
            pygame.draw.line(surface, glow, (x, int(self.rect.bottom)), (x, impact_y), 4)
            pygame.draw.line(surface, bolt, (x, int(self.rect.bottom)), (x, impact_y), 2)

    # ── fallback art: a cold ice giant when no PNG is provided ────────────────
    @staticmethod
    def _draw_fallback_surface(w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        ice = (150, 205, 235, 240)
        ice_dark = (95, 150, 195, 235)
        ice_light = (220, 240, 255, 250)
        outline = (20, 30, 45)

        # Frost-cloud body from stacked cold ellipses.
        body = pygame.Rect(12, h // 2 - 6, w - 24, h // 2 + 10)
        pygame.draw.ellipse(surf, ice, body)
        pygame.draw.ellipse(surf, ice_dark, pygame.Rect(14, 20, int(w * 0.40), int(h * 0.62)))
        pygame.draw.ellipse(surf, ice, pygame.Rect(int(w * 0.30), 6, int(w * 0.42), int(h * 0.66)))
        pygame.draw.ellipse(surf, ice_dark, pygame.Rect(int(w * 0.60), 18, int(w * 0.32), int(h * 0.58)))

        # Jagged ice-shard crown across the top, dark-outlined for readability.
        base_y = int(h * 0.34)
        n = 7
        seg = (w - 40) / n
        for i in range(n):
            x0 = int(20 + i * seg)
            x1 = int(20 + (i + 1) * seg)
            tip = (int((x0 + x1) / 2), int(base_y - (18 + (i % 3) * 12)))
            pts = [(x0, base_y), tip, (x1, base_y)]
            pygame.draw.polygon(surf, ice_light, pts)
            pygame.draw.polygon(surf, outline, pts, 2)

        # A near-black danger outline around the body.
        pygame.draw.ellipse(surf, outline, body, 3)

        # Angry frozen eyes + a frown.
        eye = (30, 45, 70)
        le = pygame.Rect(int(w * 0.36), int(h * 0.54), 20, 11)
        re = pygame.Rect(int(w * 0.57), int(h * 0.54), 20, 11)
        pygame.draw.ellipse(surf, eye, le)
        pygame.draw.ellipse(surf, eye, re)
        pygame.draw.line(surf, eye, (le.left - 3, le.top - 6), (le.right + 4, le.top - 1), 3)
        pygame.draw.line(surf, eye, (re.left - 4, re.top - 1), (re.right + 3, re.top - 6), 3)
        pygame.draw.arc(
            surf,
            eye,
            pygame.Rect(int(w * 0.42), int(h * 0.64), int(w * 0.20), int(h * 0.16)),
            3.4,
            6.0,
            3,
        )

        # A few frost flecks for texture.
        for fx, fy in ((int(w * 0.22), int(h * 0.70)), (int(w * 0.50), int(h * 0.80)), (int(w * 0.74), int(h * 0.70))):
            pygame.draw.circle(surf, ice_light, (fx, fy), 3)

        return surf
