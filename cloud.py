import pygame
import random
import os
from settings import (
    CLOUD_START_X, CLOUD_START_Y, CLOUD_SPEED,
    CLOUD_USE_IMAGE, SCREEN_W, SCREEN_H,
    RAIN_COLOR, RAIN_DROP_COUNT, RAIN_SPEED_MIN,
    RAIN_SPEED_MAX, RAIN_LENGTH,
)

PROPS_DIR = os.path.join(os.path.dirname(__file__), "props")


class RainDrop:
    """A single falling raindrop that originates below the cloud."""

    def __init__(self, cloud_rect):
        self._reset(cloud_rect)

    def _reset(self, cloud_rect):
        self.x = random.randint(cloud_rect.left, cloud_rect.right)
        self.y = cloud_rect.bottom + random.randint(0, 30)
        self.speed = random.randint(RAIN_SPEED_MIN, RAIN_SPEED_MAX)

    def update(self, cloud_rect):
        self.y += self.speed
        # recycle drop back to cloud when it falls off screen
        if self.y > SCREEN_H + RAIN_LENGTH:
            self._reset(cloud_rect)

    def draw(self, surface):
        pygame.draw.line(
            surface, RAIN_COLOR,
            (self.x, self.y),
            (self.x - 2, self.y + RAIN_LENGTH), 2,
        )


class Cloud(pygame.sprite.Sprite):
    """
    Player-controlled cloud.

    Controls
    --------
    Arrow keys  – move cloud
    Click       – toggle rain on / off
    """

    WIDTH  = 160
    HEIGHT = 80

    def __init__(self):
        super().__init__()
        self.raining = False
        self.raindrops: list[RainDrop] = []

        # ── try to load prop image ────────────────────────────────────────────
        img_path = os.path.join(PROPS_DIR, "cloud.png")
        if CLOUD_USE_IMAGE and os.path.exists(img_path):
            raw = pygame.image.load(img_path).convert_alpha()
            self.image = pygame.transform.smoothscale(raw, (self.WIDTH, self.HEIGHT))
        else:
            self.image = self._draw_cloud_surface()

        self.rect = self.image.get_rect(topleft=(CLOUD_START_X, CLOUD_START_Y))

    # ── fallback drawn cloud ───────────────────────────────────────────────────
    @staticmethod
    def _draw_cloud_surface() -> pygame.Surface:
        surf = pygame.Surface((Cloud.WIDTH, Cloud.HEIGHT), pygame.SRCALPHA)
        white = (255, 255, 255, 230)
        # bottom bar
        pygame.draw.ellipse(surf, white, pygame.Rect(10, 30, 140, 45))
        # three puffs on top
        pygame.draw.ellipse(surf, white, pygame.Rect(10, 10, 60, 55))
        pygame.draw.ellipse(surf, white, pygame.Rect(50, 0,  70, 60))
        pygame.draw.ellipse(surf, white, pygame.Rect(90, 15, 55, 50))
        return surf

    # ── public interface ───────────────────────────────────────────────────────
    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._toggle_rain()

    def update(self):
        self._handle_movement()
        if self.raining:
            for drop in self.raindrops:
                drop.update(self.rect)

    def draw_rain(self, surface: pygame.Surface):
        if self.raining:
            for drop in self.raindrops:
                drop.draw(surface)

    def covers_sun(self, sun_rect: pygame.Rect) -> bool:
        return self.rect.colliderect(sun_rect)

    # ── private helpers ────────────────────────────────────────────────────────
    def _toggle_rain(self):
        self.raining = not self.raining
        if self.raining:
            self.raindrops = [RainDrop(self.rect) for _ in range(RAIN_DROP_COUNT)]
        else:
            self.raindrops = []

    def _handle_movement(self):
        keys = pygame.key.get_pressed()
        dx = dy = 0
        if keys[pygame.K_LEFT]:  dx -= CLOUD_SPEED
        if keys[pygame.K_RIGHT]: dx += CLOUD_SPEED
        if keys[pygame.K_UP]:    dy -= CLOUD_SPEED
        if keys[pygame.K_DOWN]:  dy += CLOUD_SPEED

        self.rect.x = max(0, min(self.rect.x + dx, SCREEN_W - self.rect.width))
        self.rect.y = max(0, min(self.rect.y + dy, SCREEN_H - self.rect.height))

        # keep raindrops tethered to cloud x-position when it moves
        if self.raining and (dx or dy):
            for drop in self.raindrops:
                drop.x += dx
