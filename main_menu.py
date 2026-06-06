import os
import pygame
from settings import SCREEN_W, SCREEN_H, TITLE, FPS, SKY_DAY
from game import SAVE_PATH

class MainMenu:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font_title = pygame.font.SysFont("arial", 64, bold=True)
        self.font_button = pygame.font.SysFont("arial", 32)

        # Offer "Continue" only when there is a save to continue from.
        has_save = os.path.exists(SAVE_PATH)
        entries = []
        if has_save:
            entries.append(("Continue", "continue"))
        entries.append(("New Game", "new_game"))
        entries.append(("Tutorial", "tutorial"))
        entries.append(("Quit", "quit"))

        btn_w, btn_h = 240, 60
        gap = 20
        center_x = SCREEN_W // 2
        # Anchor the buttons well below the title (top-aligned) so the list
        # doesn't crowd the title when there are more entries (e.g. Continue).
        start_y = int(SCREEN_H * 0.42)

        self.buttons = []
        for i, (label, state) in enumerate(entries):
            rect = pygame.Rect(center_x - btn_w // 2, start_y + i * (btn_h + gap), btn_w, btn_h)
            self.buttons.append((rect, label, state))

    def run(self):
        while True:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, _label, state in self.buttons:
                        if rect.collidepoint(event.pos):
                            return state

            # Fill sky color
            self.screen.fill(SKY_DAY)

            # Draw Title
            title_surf = self.font_title.render(TITLE, True, (255, 255, 255))
            title_shadow = self.font_title.render(TITLE, True, (50, 50, 50))
            t_rect = title_surf.get_rect(center=(SCREEN_W // 2, SCREEN_H // 4))
            self.screen.blit(title_shadow, (t_rect.x + 4, t_rect.y + 4))
            self.screen.blit(title_surf, t_rect)

            # Draw Buttons
            for rect, label, _state in self.buttons:
                self._draw_button(rect, label)

            pygame.display.flip()


    def _draw_button(self, rect, text):
        mouse_pos = pygame.mouse.get_pos()
        color = (100, 150, 200) if rect.collidepoint(mouse_pos) else (70, 110, 150)
        pygame.draw.rect(self.screen, color, rect, border_radius=12)
        pygame.draw.rect(self.screen, (200, 220, 240), rect, 3, border_radius=12)

        text_surf = self.font_button.render(text, True, (255, 255, 255))
        self.screen.blit(text_surf, text_surf.get_rect(center=rect.center))
