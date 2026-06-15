import math
import random

import pygame
from settings import (
    MOON_X, MOON_Y, MOON_COLOR, MOON_RADIUS,
    BITE_OFFSET_X, BITE_OFFSET_Y, BITE_RADIUS_RATIO,
)


# Fixed seed so the crater layout is identical every run.
CRATER_SEED = 7
CRATER_COUNT = 5


def _shade(color, f):
    return tuple(max(0, min(255, int(round(c * f)))) for c in color[:3])


class Moon(pygame.sprite.Sprite):
    """Stationary crescent moon that appears when night comes (sun is covered by the clouds)"""

    SIZE = MOON_RADIUS * 2 + 20

    def __init__(self):
        super().__init__()
        self._angle  = 0          # slow spin for ray animation
        self.covered = False

        self.image = pygame.Surface((self.SIZE, self.SIZE), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(MOON_X, MOON_Y))
        self._redraw()


    def update(self):
        #no animation, but you can add one
        pass

    def _redraw(self):
        self.image.fill((0, 0, 0, 0))
        cx = cy = self.SIZE // 2

        # full moon circle
        pygame.draw.circle(self.image, MOON_COLOR, (cx, cy), MOON_RADIUS)

        bite_radius = int(MOON_RADIUS * BITE_RADIUS_RATIO)
        bite_pos = (cx + BITE_OFFSET_X, cy + BITE_OFFSET_Y)

        # Surface detail, added before the bite so it is carved cleanly with the
        # crescent and never spills past the rim.
        self._add_terminator_shade(cx, cy)
        self._add_craters(cx, cy, bite_pos, bite_radius)

        #bite that makes it a crescent
        bite_surface = pygame.Surface((self.SIZE, self.SIZE), pygame.SRCALPHA)
        pygame.draw.circle(bite_surface, (255, 255, 255, 255), bite_pos, bite_radius)
        self.image.blit(bite_surface, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

    def _add_terminator_shade(self, cx, cy):
        # Gentle darkening that builds toward the bite side, giving the lit face a
        # little volume. A 2x2 alpha ramp smoothscaled up stays band-free, and is
        # masked to the disc so it only touches the moon.
        ramp = pygame.Surface((2, 2), pygame.SRCALPHA)
        ramp.set_at((0, 0), (0, 0, 0, 0))
        ramp.set_at((1, 0), (0, 0, 0, 80))
        ramp.set_at((0, 1), (0, 0, 0, 0))
        ramp.set_at((1, 1), (0, 0, 0, 95))
        ramp = pygame.transform.smoothscale(ramp, (self.SIZE, self.SIZE))

        mask = pygame.Surface((self.SIZE, self.SIZE), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (cx, cy), MOON_RADIUS)
        ramp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.image.blit(ramp, (0, 0))

    def _add_craters(self, cx, cy, bite_pos, bite_radius):
        crater_fill = _shade(MOON_COLOR, 0.84)
        crater_rim = tuple(min(255, c + 14) for c in MOON_COLOR[:3])

        rng = random.Random(CRATER_SEED)
        placed = []
        attempts = 0
        # Reject samples that land off the lit crescent so every crater is visible.
        while len(placed) < CRATER_COUNT and attempts < 4000:
            attempts += 1
            kx = rng.uniform(cx - MOON_RADIUS * 0.78, cx + MOON_RADIUS * 0.05)
            ky = rng.uniform(cy - MOON_RADIUS * 0.62, cy + MOON_RADIUS * 0.62)
            kr = rng.uniform(3.0, 6.5)

            if math.hypot(kx - cx, ky - cy) > MOON_RADIUS - kr - 4:
                continue
            if math.hypot(kx - bite_pos[0], ky - bite_pos[1]) < bite_radius + kr + 2:
                continue
            if any(math.hypot(kx - ox, ky - oy) < kr + orr + 4 for ox, oy, orr in placed):
                continue
            placed.append((kx, ky, kr))

        for kx, ky, kr in placed:
            self._draw_crater(kx, ky, kr, crater_fill, crater_rim)

    def _draw_crater(self, kx, ky, kr, fill, rim):
        # Build the crater on a small surface so the blit feathers it softly into
        # the lit face instead of stamping a hard disc.
        pad = int(math.ceil(kr)) + 2
        size = pad * 2
        tile = pygame.Surface((size, size), pygame.SRCALPHA)
        c = pad
        pygame.draw.circle(tile, (*fill, 110), (c, c), int(round(kr)))
        pygame.draw.circle(tile, (*fill, 150), (c, c), max(1, int(round(kr * 0.6))))
        # Faint upper-left rim catch-light for a touch of relief.
        pygame.draw.circle(tile, (*rim, 90),
                           (int(c - kr * 0.35), int(c - kr * 0.35)),
                           max(1, int(round(kr * 0.32))))
        self.image.blit(tile, (int(round(kx - c)), int(round(ky - c))))
