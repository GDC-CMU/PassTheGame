from __future__ import annotations

import pygame
from plants import PlantType


class PlantSlot:
    """Runtime state for a single plant slot.

    Interface used by Game:
    - plant(seed): assign a PlantType and reset stats
    - clear(): remove plant and reset stats
    - update(...): evolve water/sun/growth and death state
    - draw(...): render slot and plant visuals
    - stats_lines(): tooltip content
    """
    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.seed: PlantType | None = None
        self.growth_stage = 0
        self._growth_frames = 0
        self.water = 50.0
        self.sun = 50.0
        self.dead = False
        self._bad_frames = 0.0

        # ── slot effects / tools ─────────────────────────────────────────
        # Scarecrow occupies an empty slot and protects nearby slots.
        self.has_scarecrow = False

        # Lightning rod protects a planted slot from boss lightning.
        self.lightning_rod_charges = 0

        # Compost temporarily boosts growth speed.
        self._compost_boost_remaining = 0.0

    @property
    def planted(self) -> bool:
        return self.seed is not None

    @property
    def harvestable(self) -> bool:
        return self.seed is not None and self.growth_stage >= self.seed.growth_stages

    def plant(self, seed: PlantType):
        self.seed = seed
        self.growth_stage = 1
        self._growth_frames = 0
        self.water = 50.0
        self.sun = 50.0
        self.dead = False
        self._bad_frames = 0.0
        self.lightning_rod_charges = 0
        self._compost_boost_remaining = 0.0

    def clear(self):
        self.seed = None
        self.growth_stage = 0
        self._growth_frames = 0
        self.water = 50.0
        self.sun = 50.0
        self.dead = False
        self._bad_frames = 0.0
        self.lightning_rod_charges = 0
        self._compost_boost_remaining = 0.0
    
    def regrow(self, stage):
        #reset to a specific grow stage, but keep seed planted
        self.growth_stage = stage
        self._growth_frames = 0
        self.water = 50.0
        self.sun = 50.0
        self._bad_frames = 0.0

    # ── tools / effects ──────────────────────────────────────────────────
    @property
    def compost_boost_remaining(self) -> float:
        return float(self._compost_boost_remaining)

    def apply_compost(self, seconds: float) -> None:
        self._compost_boost_remaining = max(0.0, float(seconds))

    def place_scarecrow(self) -> None:
        self.has_scarecrow = True

    def remove_scarecrow(self) -> None:
        self.has_scarecrow = False

    def add_lightning_rod_charges(self, charges: int) -> None:
        self.lightning_rod_charges = max(0, int(charges))

    def update(
        self,
        water_delta: float,
        sun_delta: float,
        *,
        water_kill: float,
        sun_kill: float,
        bad_seconds_to_die: float,
        bad_recovery_rate: float,
        growth_rate_good: float,
        growth_rate_bad: float,
        dt: float,
    ):
        self.water = max(0.0, min(100.0, self.water + water_delta))
        self.sun = max(0.0, min(100.0, self.sun + sun_delta))

        if self._compost_boost_remaining > 0.0:
            self._compost_boost_remaining = max(0.0, self._compost_boost_remaining - dt)

        if not self.seed or self.harvestable or self.dead:
            return

        in_range = self.seed.water_min <= self.water <= self.seed.water_max and self.seed.sun_min <= self.sun <= self.seed.sun_max
        in_over = self.water >= water_kill or self.sun >= sun_kill
        if in_range:
            self._bad_frames = max(0.0, self._bad_frames - bad_recovery_rate * dt)
            self._growth_frames += growth_rate_good * dt
        else:
            rate = 2.0 if in_over else 1.0
            self._bad_frames += rate * dt
            self._growth_frames += growth_rate_bad * dt

        if self._bad_frames >= bad_seconds_to_die:
            self.dead = True
            return

        if self._growth_frames >= self.seed.seconds_per_stage:
            self._growth_frames = 0
            self.growth_stage += 1

    def strike_lightning(self):
        """Apply an instant lightning strike to this slot.

        Kept intentionally small so other systems (bosses, events, etc.) can
        damage plants without rewriting the core update loop.
        """
        if not self.seed or self.dead:
            return

        if self.lightning_rod_charges > 0:
            # I consume a charge and keep the plant alive.
            self.lightning_rod_charges = max(0, int(self.lightning_rod_charges) - 1)
            return

        self.dead = True
        # Optional flavor: a struck plant is dried out and over-sunned.
        self.water = 0.0
        self.sun = 100.0

    def draw(
        self,
        surface: pygame.Surface,
        empty_color: tuple[int, int, int],
        border_color: tuple[int, int, int],
        *,
        phase_image: pygame.Surface | None = None,
        dead_image: pygame.Surface | None = None,
    ):
        pygame.draw.rect(surface, empty_color, self.rect, border_radius=4)
        pygame.draw.rect(surface, border_color, self.rect, 2, border_radius=4)

        if self.harvestable and not self.dead:
            glow_rect = self.rect.inflate(4, 4)
            pygame.draw.rect(surface, (80, 200, 90), glow_rect, 3, border_radius=6)

        if not self.seed:
            if self.has_scarecrow:
                self._draw_scarecrow(surface)
            return

        cx, cy = self.rect.center
        stage = min(self.growth_stage, self.seed.growth_stages)
        size = 4 + stage * 3
        color = self.seed.base_color
        if self.dead:
            color = (90, 90, 90)
        elif self.harvestable:
            color = (min(color[0] + 30, 255), min(color[1] + 30, 255), min(color[2] + 30, 255))

        stem_color = (80, 120, 80) if not self.dead else (80, 80, 80)
        if self.dead and dead_image:
            img_rect = dead_image.get_rect(midbottom=(cx, self.rect.bottom - 4))
            surface.blit(dead_image, img_rect)
        elif phase_image:
            img_rect = phase_image.get_rect(midbottom=(cx, self.rect.bottom - 4))
            surface.blit(phase_image, img_rect)
        else:
            pygame.draw.line(surface, stem_color, (cx, self.rect.bottom - 6), (cx, cy), 2)
            pygame.draw.circle(surface, color, (cx, cy), size)

        self._draw_minibars(surface)

    def _draw_scarecrow(self, surface: pygame.Surface) -> None:
        # Simple placeholder (no sprite required).
        cx, cy = self.rect.center
        post_top = self.rect.top + 10
        post_bottom = self.rect.bottom - 8
        color = (95, 70, 50)
        accent = (160, 120, 80)

        # Post
        pygame.draw.line(surface, color, (cx, post_top), (cx, post_bottom), 4)
        # Arms
        arm_y = self.rect.top + int(self.rect.height * 0.45)
        pygame.draw.line(surface, color, (cx - 14, arm_y), (cx + 14, arm_y), 4)
        # Head
        pygame.draw.circle(surface, accent, (cx, self.rect.top + 14), 7)
        # Hat brim
        pygame.draw.line(surface, (40, 35, 30), (cx - 10, self.rect.top + 8), (cx + 10, self.rect.top + 8), 3)

    def _draw_minibars(self, surface: pygame.Surface):
        bar_margin = 4
        bar_height = 3
        bar_width = self.rect.width - bar_margin * 2
        if bar_width <= 8:
            return

        water_y = self.rect.bottom - bar_margin - bar_height
        sun_y = water_y - bar_height - 2

        water_pct = max(0.0, min(1.0, self.water / 100.0))
        sun_pct = max(0.0, min(1.0, self.sun / 100.0))

        water_color = self._water_bar_color()
        sun_color = self._sun_bar_color()

        self._draw_bar(surface, sun_y, sun_pct, sun_color)
        self._draw_bar(surface, water_y, water_pct, water_color)

    def _draw_bar(self, surface: pygame.Surface, y: int, pct: float, color: tuple[int, int, int]):
        bar_margin = 4
        bar_height = 3
        bar_width = self.rect.width - bar_margin * 2
        bg_rect = pygame.Rect(self.rect.left + bar_margin, y, bar_width, bar_height)
        pygame.draw.rect(surface, (40, 45, 55), bg_rect, border_radius=2)
        fill_rect = pygame.Rect(bg_rect.left, y, int(bar_width * pct), bar_height)
        pygame.draw.rect(surface, color, fill_rect, border_radius=2)

    def _sun_bar_color(self) -> tuple[int, int, int]:
        if not self.seed:
            return (120, 120, 120)
        if self.sun < self.seed.sun_min:
            return (120, 120, 120)
        if self.sun > self.seed.sun_max:
            return (210, 60, 60)
        return (90, 200, 90)

    def _water_bar_color(self) -> tuple[int, int, int]:
        if not self.seed:
            return (120, 120, 120)
        if self.water < self.seed.water_min:
            return (80, 140, 220)
        if self.water > self.seed.water_max:
            return (150, 80, 180)
        return (90, 200, 90)

    def stats_lines(self) -> list[str]:
        if not self.seed:
            return []
        stage = min(self.growth_stage, self.seed.growth_stages)
        status = "Dead" if self.dead else "Alive"
        lines = [
            f"{self.seed.name}",
            f"Status: {status}",
            f"Stage: {stage}/{self.seed.growth_stages}",
            f"Water: {int(self.water)}",
            f"Water range: {int(self.seed.water_min)}-{int(self.seed.water_max)}",
            f"Sun: {int(self.sun)}",
            f"Sun range: {int(self.seed.sun_min)}-{int(self.seed.sun_max)}",
        ]

        if self.lightning_rod_charges > 0:
            lines.append(f"Lightning rod charges: {int(self.lightning_rod_charges)}")
        if self._compost_boost_remaining > 0.0:
            lines.append(f"Compost boost: {max(0, int(self._compost_boost_remaining) + 1)}s")
        return lines
