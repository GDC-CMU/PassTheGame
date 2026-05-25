import pygame
import math
import random
from settings import (
    SCREEN_W, SCREEN_H, GROUND_HEIGHT_PCT, UI_PANEL_W,
    STAR_COLOR, STAR_COUNT, SPARKLING_SPEED,
)

class Stars:
    """Randomly placed sparkling stars that appear at night."""
    def __init__(self):
        ground_top = int(SCREEN_H * (1 - GROUND_HEIGHT_PCT))
        field_w = SCREEN_W - UI_PANEL_W
        self._stars = []

        for i in range (STAR_COUNT):
            x = random.randint(10, field_w - 10)
            y = random.randint(10, ground_top - 10)
            phase = random.uniform(0, math.pi *2)
            radius = random.choice([1, 1, 1, 2])
            self._stars.append([x, y, phase, radius])
    
    def update(self, dt):
        for star in self._stars:
            star[2] += dt * SPARKLING_SPEED

    def draw(self, surface, darkness):
        # darkness: 0.0 is day, 1.0 is night
        if darkness <= 0.1:
            return

        stars_surface = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for x, y, phase, radius in self._stars:
            sparkling = (math.sin(phase) + 1) / 2
            alpha = int(darkness * (130 + 100*sparkling))
            alpha = max(0, min(255, alpha))

            if alpha < 10:
                continue
            pygame.draw.circle(stars_surface, (*STAR_COLOR, alpha), (x, y), radius)
        surface.blit(stars_surface, (0, 0))