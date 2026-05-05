import pygame
from settings import (
    TITLE, SCREEN_W, SCREEN_H, FPS,
    SKY_DAY, SKY_DARK,
)
from cloud import Cloud
from sun import Sun


class Game:
    """
    Core game loop.  All state lives here; sprites are kept in groups so that
    future contributors can easily add more sprites or layers.
    """

    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption(TITLE)
        self.clock  = pygame.time.Clock()

        # ── sprites ───────────────────────────────────────────────────────────
        self.sun   = Sun()
        self.cloud = Cloud()

        self.all_sprites = pygame.sprite.Group(self.sun, self.cloud)

        # ── sky transition ────────────────────────────────────────────────────
        self._sky_color = list(SKY_DAY)   # mutable for lerp
        self._font = pygame.font.SysFont("arial", 18)

    # ── main loop ─────────────────────────────────────────────────────────────
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                self.cloud.handle_event(event)

            self._update()
            self._draw()

    # ── update ────────────────────────────────────────────────────────────────
    def _update(self):
        self.all_sprites.update()

        # lerp sky colour toward target
        target = SKY_DARK if self.cloud.covers_sun(self.sun.circle_rect) else SKY_DAY
        for i in range(3):
            diff = target[i] - self._sky_color[i]
            self._sky_color[i] += diff * 0.04   # smooth transition speed

    # ── draw ──────────────────────────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(tuple(int(c) for c in self._sky_color))

        self.screen.blit(self.sun.image, self.sun.rect)
        self.cloud.draw_rain(self.screen)
        self.screen.blit(self.cloud.image, self.cloud.rect)

        self._draw_hud()
        pygame.display.flip()

    def _draw_hud(self):
        hints = [
            "Arrow keys: move cloud",
            "Click cloud: toggle rain",
            "Cover the sun to darken the sky",
            "ESC: quit",
        ]
        y = 8
        for hint in hints:
            surf = self._font.render(hint, True, (255, 255, 255))
            shadow = self._font.render(hint, True, (0, 0, 0))
            self.screen.blit(shadow, (11, y + 1))
            self.screen.blit(surf,   (10, y))
            y += 22
