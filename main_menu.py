import pygame
from settings import SCREEN_W, SCREEN_H, TITLE, FPS, SKY_DAY

class MainMenu:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font_title = pygame.font.SysFont("arial", 64, bold=True)
        self.font_button = pygame.font.SysFont("arial", 32)

        # Button dimensions and positions
        btn_w, btn_h = 240, 60
        center_x = SCREEN_W // 2
        start_y = SCREEN_H // 2
        tut_y = SCREEN_H // 2 + 80

        self.btn_start = pygame.Rect(center_x - btn_w // 2, start_y, btn_w, btn_h)
        self.btn_tut = pygame.Rect(center_x - btn_w // 2, tut_y, btn_w, btn_h)

    def run(self):
        running = True
        while running:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.btn_start.collidepoint(event.pos):
                        return "start"
                    if self.btn_tut.collidepoint(event.pos):
                        return "tutorial"

            # Fill sky color
            self.screen.fill(SKY_DAY)

            # Draw Title
            title_surf = self.font_title.render(TITLE, True, (255, 255, 255))
            title_shadow = self.font_title.render(TITLE, True, (50, 50, 50))
            t_rect = title_surf.get_rect(center=(SCREEN_W // 2, SCREEN_H // 3))
            self.screen.blit(title_shadow, (t_rect.x + 4, t_rect.y + 4))
            self.screen.blit(title_surf, t_rect)

            # Draw Buttons
            self._draw_button(self.btn_start, "Start Game")
            self._draw_button(self.btn_tut, "Tutorial")

            pygame.display.flip()

    def _draw_button(self, rect, text):
        mouse_pos = pygame.mouse.get_pos()
        color = (100, 150, 200) if rect.collidepoint(mouse_pos) else (70, 110, 150)
        pygame.draw.rect(self.screen, color, rect, border_radius=12)
        pygame.draw.rect(self.screen, (200, 220, 240), rect, 3, border_radius=12)

        text_surf = self.font_button.render(text, True, (255, 255, 255))
        self.screen.blit(text_surf, text_surf.get_rect(center=rect.center))
