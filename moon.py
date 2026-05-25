import pygame
from settings import (
    MOON_X, MOON_Y, MOON_COLOR, MOON_RADIUS,
    BITE_OFFSET_X, BITE_OFFSET_Y, BITE_RADIUS_RATIO,
)



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

        #bite that makes it a crescent
        bite_radius = int(MOON_RADIUS * BITE_RADIUS_RATIO)
        bite_pos = (cx + BITE_OFFSET_X, cy + BITE_OFFSET_Y)
        bite_surface = pygame.Surface((self.SIZE, self.SIZE), pygame.SRCALPHA)
        pygame.draw.circle(bite_surface, (255, 255, 255, 255), bite_pos, bite_radius)
        self.image.blit(bite_surface, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
