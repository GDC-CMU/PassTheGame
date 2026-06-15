import pygame
import math
import random
from settings import (
    SCREEN_W, SCREEN_H, GROUND_HEIGHT_PCT, UI_PANEL_W,
    STAR_COLOR, STAR_COUNT, SPARKLING_SPEED,
)

# Fixed seed so the field is identical every run.
STAR_SEED = 1337
# Trim the field a touch from STAR_COUNT (owner request: "reduce by a bit").
STAR_COUNT_SCALE = 0.70

# Tiers: faint single-pixel pinpoints, medium haloed twinkles, a few bright
# 4-point stars. Fractions of the (reduced) total.
TIER_FAINT, TIER_MEDIUM, TIER_BRIGHT = 0, 1, 2

WARM_STAR = (255, 240, 200)
COOL_STAR = (200, 210, 245)
WHITE_CORE = (255, 255, 245)


def _lerp3(a, b, t):
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


class Stars:
    """Randomly placed sparkling stars that appear at night.

    Three tiers over the field: many faint pinpoints, fewer medium twinkles with
    a soft halo, and a handful of bright 4-point stars. Placement is seeded so the
    layout is identical every run.
    """

    def __init__(self):
        ground_top = int(SCREEN_H * (1 - GROUND_HEIGHT_PCT))
        field_w = SCREEN_W - UI_PANEL_W
        rng = random.Random(STAR_SEED)

        total = max(1, round(STAR_COUNT * STAR_COUNT_SCALE))
        n_bright = max(1, round(total * 0.07))
        n_medium = max(1, round(total * 0.24))
        n_faint = max(0, total - n_medium - n_bright)
        self._count = total

        self._stars = []
        # [x, y, phase, tier, tint, size]
        for tier, n, pad in (
            (TIER_FAINT, n_faint, 10),
            (TIER_MEDIUM, n_medium, 12),
            (TIER_BRIGHT, n_bright, 16),
        ):
            for _ in range(n):
                x = rng.randint(pad, field_w - pad)
                y = rng.randint(pad, ground_top - pad)
                phase = rng.uniform(0, math.pi * 2)
                if tier == TIER_FAINT:
                    tint = _lerp3(STAR_COLOR, COOL_STAR, rng.random() * 0.5)
                    size = 1
                elif tier == TIER_MEDIUM:
                    tint = _lerp3(STAR_COLOR, COOL_STAR, rng.random() * 0.35)
                    size = rng.choice([1, 1, 2])
                else:
                    tint = _lerp3(STAR_COLOR, WARM_STAR, 0.4)
                    size = rng.choice([0, 1])
                self._stars.append([x, y, phase, tier, tint, size])

        # Reused once instead of allocating a fullscreen surface every night frame.
        self._layer = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

    def update(self, dt):
        for star in self._stars:
            star[2] += dt * SPARKLING_SPEED

    def draw(self, surface, darkness):
        # darkness: 0.0 is day, 1.0 is night
        if darkness <= 0.1:
            return

        self._layer.fill((0, 0, 0, 0))
        for x, y, phase, tier, tint, size in self._stars:
            sparkling = (math.sin(phase) + 1) / 2
            if tier == TIER_FAINT:
                self._draw_faint(x, y, tint, darkness, sparkling)
            elif tier == TIER_MEDIUM:
                self._draw_medium(x, y, tint, size, darkness, sparkling)
            else:
                self._draw_bright(x, y, tint, size, darkness, sparkling)
        surface.blit(self._layer, (0, 0))

    @staticmethod
    def _a(value):
        return max(0, min(255, int(value)))

    def _draw_faint(self, x, y, tint, darkness, sparkling):
        alpha = self._a(darkness * (50 + 85 * sparkling))
        if alpha < 8:
            return
        self._layer.set_at((x, y), (*tint, alpha))

    def _draw_medium(self, x, y, tint, size, darkness, sparkling):
        core_a = self._a(darkness * (150 + 95 * sparkling))
        if core_a < 8:
            return
        halo_a = self._a(darkness * (32 + 34 * sparkling))
        if halo_a > 0:
            pygame.draw.circle(self._layer, (*tint, halo_a), (x, y), size + 2)
        pygame.draw.circle(self._layer, (*tint, core_a), (x, y), size)

    def _draw_bright(self, x, y, tint, size, darkness, sparkling):
        arm_a = self._a(darkness * (170 + 85 * sparkling))
        if arm_a < 8:
            return
        halo_outer = self._a(darkness * (26 + 26 * sparkling))
        halo_inner = self._a(darkness * (60 + 50 * sparkling))
        pygame.draw.circle(self._layer, (*tint, halo_outer), (x, y), 6 + size)
        pygame.draw.circle(self._layer, (*tint, halo_inner), (x, y), 3 + size)
        arm = 5 + size
        for dx, dy in ((0, -arm), (0, arm), (-arm, 0), (arm, 0)):
            pygame.draw.line(self._layer, (*tint, arm_a), (x, y), (x + dx, y + dy), 1)
        core_a = self._a(darkness * (200 + 55 * sparkling))
        pygame.draw.line(self._layer, (*WHITE_CORE, core_a), (x - 2, y), (x + 2, y), 1)
        pygame.draw.line(self._layer, (*WHITE_CORE, core_a), (x, y - 2), (x, y + 2), 1)