import pygame
import random
import os
from settings import (
    CLOUD_START_X, CLOUD_START_Y, CLOUD_SPEED, WIND_SPEED,
    CLOUD_USE_IMAGE, SCREEN_W, SCREEN_H,
    RAIN_COLOR, RAIN_DROP_COUNT, RAIN_SPEED_MIN,
    RAIN_SPEED_MAX, RAIN_LENGTH, UI_PANEL_W,
    RAIN_INTENSITY_OFF, RAIN_INTENSITY_LIGHT, RAIN_INTENSITY_HEAVY,
    RAIN_LIGHT_DROP_COUNT, RAIN_HEAVY_DROP_COUNT,
)

PROPS_DIR = os.path.join(os.path.dirname(__file__), "props")

# default controls for the first cloud
DEFAULT_CONTROLS = {
    "left": pygame.K_LEFT,
    "right": pygame.K_RIGHT,
    "up": pygame.K_UP,
    "down": pygame.K_DOWN,
}

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
    Arrow keys/WASD  – move cloud
    Click       – toggle rain on / off
    """

    WIDTH  = 160
    HEIGHT = 80

    def __init__(self, start_pos=(CLOUD_START_X, CLOUD_START_Y), controls=None):
        super().__init__()
        # I keep a simple 3-state rain mode so the player can choose intensity.
        self.rain_intensity = int(RAIN_INTENSITY_OFF)
        self.raindrops: list[RainDrop] = []
        
        self.controls = controls or DEFAULT_CONTROLS
        self.X_float = float(start_pos[0]) #if wind_speed isn't int
        self.wind_speed = float(WIND_SPEED)

        # ── try to load prop image ────────────────────────────────────────────
        img_path = os.path.join(PROPS_DIR, "cloud.png")
        if CLOUD_USE_IMAGE and os.path.exists(img_path):
            raw = pygame.image.load(img_path).convert_alpha()
            self.image = pygame.transform.smoothscale(raw, (self.WIDTH, self.HEIGHT))
        else:
            self.image = self._draw_cloud_surface()

        self.rect = self.image.get_rect(topleft=start_pos)
        # Track when the cloud last toggled rain intensity (for perfect-block timing)
        self._last_rain_toggled_at: float | None = None

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
                self._cycle_rain_intensity()

    def update(self):
        if self.raining:
            for drop in self.raindrops:
                drop.update(self.rect)
    
    def update_movement(self):
        #called when game isn't paused
        self._handle_movement()
        self._apply_wind()

    def draw_rain(self, surface: pygame.Surface):
        if self.raining:
            for drop in self.raindrops:
                drop.draw(surface)

    @property
    def raining(self) -> bool:
        return self.rain_intensity != int(RAIN_INTENSITY_OFF)

    @property
    def heavy_rain(self) -> bool:
        return self.rain_intensity == int(RAIN_INTENSITY_HEAVY)

    def covers_sun(self, sun_rect: pygame.Rect) -> bool:
        return self.rect.colliderect(sun_rect)

    # ── private helpers ────────────────────────────────────────────────────────
    def _cycle_rain_intensity(self):
        if self.rain_intensity == int(RAIN_INTENSITY_OFF):
            self.rain_intensity = int(RAIN_INTENSITY_LIGHT)
        elif self.rain_intensity == int(RAIN_INTENSITY_LIGHT):
            self.rain_intensity = int(RAIN_INTENSITY_HEAVY)
        else:
            self.rain_intensity = int(RAIN_INTENSITY_OFF)
        self._sync_raindrops_to_intensity()
        try:
            self._last_rain_toggled_at = pygame.time.get_ticks() / 1000.0
        except Exception:
            self._last_rain_toggled_at = None

    def _sync_raindrops_to_intensity(self):
        if not self.raining:
            self.raindrops = []
            return

        if self.rain_intensity == int(RAIN_INTENSITY_HEAVY):
            count = int(RAIN_HEAVY_DROP_COUNT)
        else:
            count = int(RAIN_LIGHT_DROP_COUNT)

        # Keep it simple: rebuild the pool for the new density.
        self.raindrops = [RainDrop(self.rect) for _ in range(max(0, count))]

    def _handle_movement(self):
        keys = pygame.key.get_pressed()
        dx = dy = 0
        if keys[self.controls["left"]]:  dx -= CLOUD_SPEED
        if keys[self.controls["right"]]: dx += CLOUD_SPEED
        if keys[self.controls["up"]]:    dy -= CLOUD_SPEED
        if keys[self.controls["down"]]:  dy += CLOUD_SPEED

        self.rect.x = max(0, min(self.rect.x + dx, SCREEN_W - UI_PANEL_W - self.rect.width))
        self.rect.y = max(0, min(self.rect.y + dy, SCREEN_H - self.rect.height))
        if dx:
            self.X_float = float(self.rect.x)

        # keep raindrops tethered to the cloud when it moves
        if self.raining and (dx or dy):
            for drop in self.raindrops:
                drop.x += dx
                drop.y += dy

    def _apply_wind(self):
        old_x = self.rect.x
        self.X_float = max(0.0, min(self.X_float + float(self.wind_speed), float(SCREEN_W - UI_PANEL_W - self.rect.width)))
        self.rect.x = int(self.X_float)
        dx = self.rect.x - old_x

        if self.raining and dx:
            for drop in self.raindrops:
                drop.x += dx