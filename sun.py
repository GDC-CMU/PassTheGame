import pygame
import math
import os
from settings import SUN_X, SUN_Y, SUN_RADIUS, SUN_COLOR

PROPS_DIR = os.path.join(os.path.dirname(__file__), "props")


class Sun(pygame.sprite.Sprite):
    """Stationary sun that can be covered by the cloud."""

    SIZE = SUN_RADIUS * 2 + 40   # extra room for rays

    def __init__(self):
        super().__init__()
        self._angle  = 0          # slow spin for ray animation
        self.covered = False

        img_path = os.path.join(PROPS_DIR, "sun.png")
        if os.path.exists(img_path):
            raw = pygame.image.load(img_path).convert_alpha()
            self.image = pygame.transform.smoothscale(raw, (self.SIZE, self.SIZE))
            self._use_image = True
        else:
            self._use_image = False
            self.image = pygame.Surface((self.SIZE, self.SIZE), pygame.SRCALPHA)

        self.rect = self.image.get_rect(center=(SUN_X, SUN_Y))

    # hit-box that matches just the circle (ignores ray area)
    @property
    def circle_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.rect.centerx - SUN_RADIUS,
            self.rect.centery - SUN_RADIUS,
            SUN_RADIUS * 2,
            SUN_RADIUS * 2,
        )

    def update(self):
        self._angle = (self._angle + 0.3) % 360
        if not self._use_image:
            self._redraw()

    def _redraw(self):
        self.image.fill((0, 0, 0, 0))
        cx = cy = self.SIZE // 2

        # rays
        ray_color = (*SUN_COLOR[:3], 180)
        for i in range(12):
            theta = math.radians(self._angle + i * 30)
            x1 = cx + math.cos(theta) * (SUN_RADIUS + 6)
            y1 = cy + math.sin(theta) * (SUN_RADIUS + 6)
            x2 = cx + math.cos(theta) * (SUN_RADIUS + 18)
            y2 = cy + math.sin(theta) * (SUN_RADIUS + 18)
            pygame.draw.line(self.image, ray_color, (x1, y1), (x2, y2), 3)

        # main circle
        pygame.draw.circle(self.image, SUN_COLOR, (cx, cy), SUN_RADIUS)
        # shine highlight
        pygame.draw.circle(self.image, (255, 245, 150), (cx - 14, cy - 14), 14)
