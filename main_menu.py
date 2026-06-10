import os
import math
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

        # Sun
        self._sun_angle = 0
        self._sun_r = SCREEN_H // 6          # diameter = 1/3 screen height
        self._sun_cx = SCREEN_W // 2
        self._sun_cy = SCREEN_H // 4         # centre of top 1/3

        img_path = os.path.join(os.path.dirname(__file__), "props", "sun.png")
        if os.path.exists(img_path):
            img_size = self._sun_r * 2 + 40
            raw = pygame.image.load(img_path).convert_alpha()
            self._sun_img = pygame.transform.smoothscale(raw, (img_size, img_size))
        else:
            self._sun_img = None

        # Drifting cloud
        cloud_path = os.path.join(os.path.dirname(__file__), "props", "cloud.png")
        if os.path.exists(cloud_path):
            raw = pygame.image.load(cloud_path).convert_alpha()
            self._cloud_surf = pygame.transform.smoothscale(raw, (240, 120))
        else:
            self._cloud_surf = self._make_cloud_surf()
        self._cloud_x = float(SCREEN_W // 4)
        self._cloud_y = SCREEN_H // 5

        # Ground props
        prop_h = SCREEN_H // 3
        self._scarecrow_img = self._load_prop("scarecrow_icon.png", prop_h)
        self._apple_img     = self._load_prop("apple_phase4.png",   int(prop_h * 1.4))
        self._carrot_img    = self._load_prop("carrot_phase3.png",   prop_h)
        self._squirrel_img  = self._make_squirrel_surf(126, 63)

        # Music
        self._music_on = True
        music_path = os.path.join(os.path.dirname(__file__), "passthegame_audio", "main_menu.wav")
        self._music_available = os.path.exists(music_path)
        if self._music_available:
            try:
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.play(-1)
            except Exception:
                self._music_available = False

        # Music toggle button (top-right corner)
        self._music_btn_center = (SCREEN_W - 35, 35)
        self._music_btn_radius = 25
        self._font_note = pygame.font.SysFont("segoeuisymbol", 24, bold=True)

    def run(self):
        while True:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.mixer.music.stop()
                    return "quit"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    cx, cy = self._music_btn_center
                    dx, dy = event.pos[0] - cx, event.pos[1] - cy
                    if dx * dx + dy * dy <= self._music_btn_radius ** 2:
                        self._toggle_music()
                        continue
                    for rect, _label, state in self.buttons:
                        if rect.collidepoint(event.pos):
                            pygame.mixer.music.stop()
                            return state

            # Fill sky color
            self.screen.fill(SKY_DAY)

            # Draw ground strip (bottom 1/4)
            ground_h = SCREEN_H // 4
            ground_rect = pygame.Rect(0, SCREEN_H - ground_h, SCREEN_W, ground_h)
            pygame.draw.rect(self.screen, (166, 124, 82), ground_rect)
            pygame.draw.rect(self.screen, (99, 67, 43), ground_rect, 3)

            # Draw ground props
            self._draw_ground_props()

            # Draw sun
            self._sun_angle = (self._sun_angle + 0.3) % 360
            self._draw_sun()

            # Draw cloud (in front of sun)
            self._cloud_x = (self._cloud_x + 1.0) % (SCREEN_W + 240)
            self.screen.blit(self._cloud_surf, (int(self._cloud_x) - 240, self._cloud_y))

            # Draw Title
            title_surf = self.font_title.render(TITLE, True, (0, 0, 0))
            t_rect = title_surf.get_rect(center=(SCREEN_W // 2, SCREEN_H // 4))
            self.screen.blit(title_surf, t_rect)

            # Draw Buttons
            for rect, label, _state in self.buttons:
                self._draw_button(rect, label)

            # Draw music toggle
            self._draw_music_btn()

            pygame.display.flip()


    def _draw_button(self, rect, text):
        mouse_pos = pygame.mouse.get_pos()
        color = (100, 150, 200) if rect.collidepoint(mouse_pos) else (70, 110, 150)
        pygame.draw.rect(self.screen, color, rect, border_radius=12)
        pygame.draw.rect(self.screen, (200, 220, 240), rect, 3, border_radius=12)

        text_surf = self.font_button.render(text, True, (255, 255, 255))
        self.screen.blit(text_surf, text_surf.get_rect(center=rect.center))

    def _toggle_music(self):
        if not self._music_available:
            return
        self._music_on = not self._music_on
        if self._music_on:
            pygame.mixer.music.unpause()
        else:
            pygame.mixer.music.pause()

    def _draw_music_btn(self):
        cx, cy = self._music_btn_center
        r = self._music_btn_radius

        # Background circle
        mouse = pygame.mouse.get_pos()
        dx0, dy0 = mouse[0] - cx, mouse[1] - cy
        hovered = dx0 * dx0 + dy0 * dy0 <= r * r
        fill = (100, 150, 200) if hovered else (70, 110, 150)
        pygame.draw.circle(self.screen, fill, (cx, cy), r)
        pygame.draw.circle(self.screen, (200, 220, 240), (cx, cy), r, 3)

        # Music note ♪
        note = self._font_note.render("♪", True, (255, 255, 255))
        self.screen.blit(note, note.get_rect(center=(cx, cy)))

        # Slash when muted
        if not self._music_on:
            pygame.draw.line(self.screen, (220, 60, 60),
                             (cx - r + 7, cy + r - 7),
                             (cx + r - 7, cy - r + 7), 3)

    @staticmethod
    def _make_cloud_surf() -> pygame.Surface:
        surf = pygame.Surface((240, 120), pygame.SRCALPHA)
        white = (255, 255, 255, 230)
        pygame.draw.ellipse(surf, white, pygame.Rect(15, 45, 210, 68))
        pygame.draw.ellipse(surf, white, pygame.Rect(15, 15,  90, 83))
        pygame.draw.ellipse(surf, white, pygame.Rect(75,  0, 105, 90))
        pygame.draw.ellipse(surf, white, pygame.Rect(135, 23, 83, 75))
        return surf

    @staticmethod
    def _make_squirrel_surf(w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        fur      = (165, 115,  70, 235)
        fur_dark = (125,  85,  55, 220)
        belly    = (215, 175, 125, 220)
        outline  = ( 35,  30,  25, 210)
        foot     = ( 90,  60,  40, 220)

        tail_rect = pygame.Rect(0, int(h * 0.05), int(w * 0.44), int(h * 0.92))
        pygame.draw.ellipse(surf, fur_dark, tail_rect)
        pygame.draw.ellipse(surf, fur, tail_rect.inflate(-int(w * 0.08), -int(h * 0.18)))
        pygame.draw.arc(surf, (235, 220, 200, 150),
                        tail_rect.inflate(-int(w * 0.14), -int(h * 0.26)), 0.2, 2.7, 3)

        body_rect = pygame.Rect(int(w * 0.18), int(h * 0.36), int(w * 0.54), int(h * 0.46))
        pygame.draw.ellipse(surf, fur, body_rect)
        pygame.draw.ellipse(surf, belly,
                            pygame.Rect(int(w * 0.34), int(h * 0.50), int(w * 0.30), int(h * 0.28)))

        for sx in (0.42, 0.50, 0.58):
            pygame.draw.rect(surf, fur_dark,
                             pygame.Rect(int(w * sx), int(h * 0.40), int(w * 0.03), int(h * 0.42)),
                             border_radius=4)

        head_center = (int(w * 0.78), int(h * 0.50))
        head_r = max(6, int(h * 0.22))
        pygame.draw.circle(surf, fur, head_center, head_r)
        pygame.draw.circle(surf, fur_dark, (int(w * 0.80), int(h * 0.32)), max(3, int(h * 0.10)))
        pygame.draw.circle(surf, (10, 10, 10), (int(w * 0.81), int(h * 0.47)), 2)
        pygame.draw.circle(surf, (20, 15, 15), (int(w * 0.90), int(h * 0.55)), 2)
        pygame.draw.line(surf, outline,
                         (int(w * 0.88), int(h * 0.58)), (int(w * 0.86), int(h * 0.60)), 2)

        pygame.draw.ellipse(surf, foot,
                            pygame.Rect(int(w * 0.35), int(h * 0.80), int(w * 0.10), int(h * 0.12)))
        pygame.draw.ellipse(surf, foot,
                            pygame.Rect(int(w * 0.52), int(h * 0.80), int(w * 0.10), int(h * 0.12)))
        return surf

    @staticmethod
    def _load_prop(filename, height):
        path = os.path.join(os.path.dirname(__file__), "props", filename)
        if not os.path.exists(path):
            return None
        raw = pygame.image.load(path).convert_alpha()
        w, h = raw.get_size()
        return pygame.transform.smoothscale(raw, (int(w * height / h), height))

    def _draw_ground_props(self):
        bottom_y = SCREEN_H - SCREEN_H // 8
        props = [
            (self._scarecrow_img, SCREEN_W // 12),           # left
            (self._apple_img,     SCREEN_W // 4),             # right of scarecrow
            (self._squirrel_img,  SCREEN_W * 5 // 6 - 150),  # left of carrot
            (self._carrot_img,    SCREEN_W * 5 // 6),         # right 1/3
        ]
        for img, cx in props:
            if img is None:
                continue
            rect = img.get_rect()
            rect.centerx = cx
            rect.bottom = bottom_y
            self.screen.blit(img, rect)

    def _draw_sun(self):
        cx, cy, r = self._sun_cx, self._sun_cy, self._sun_r
        sun_color = (255, 220, 50)

        if self._sun_img is not None:
            self.screen.blit(self._sun_img, self._sun_img.get_rect(center=(cx, cy)))
            return

        scale = r / 55  # proportional to original SUN_RADIUS
        for i in range(12):
            theta = math.radians(self._sun_angle + i * 30)
            x1 = int(cx + math.cos(theta) * (r + 6 * scale))
            y1 = int(cy + math.sin(theta) * (r + 6 * scale))
            x2 = int(cx + math.cos(theta) * (r + 18 * scale))
            y2 = int(cy + math.sin(theta) * (r + 18 * scale))
            pygame.draw.line(self.screen, sun_color, (x1, y1), (x2, y2), max(2, int(3 * scale)))

        pygame.draw.circle(self.screen, sun_color, (cx, cy), r)
        hl = max(1, int(14 * scale))
        pygame.draw.circle(self.screen, (255, 245, 150), (cx - hl, cy - hl), hl)
