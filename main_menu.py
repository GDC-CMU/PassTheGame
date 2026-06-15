import os
import math
import random
import pygame

from settings import SCREEN_W, SCREEN_H, TITLE, FPS
from game import SAVE_PATH
from effects import vertical_gradient, vignette, radial_glow, pulse, clamp
from ui_theme import soft_glow, soft_shadow

PROPS_DIR = os.path.join(os.path.dirname(__file__), "props")

# Cozy daytime palette, kept local so settings.py stays untouched.
SKY_TOP      = (118, 182, 226)
SKY_HORIZON  = (224, 232, 214)
HILL_FAR     = (162, 200, 148)
HILL_MID     = (126, 180, 110)
HILL_NEAR    = (98, 156, 86)
SOIL_TOP     = (160, 118, 84)
SOIL_BOTTOM  = (104, 74, 52)
FURROW_DARK  = (118, 84, 58)
FURROW_LIGHT = (182, 140, 102)
GRASS_LIP    = (104, 164, 88)
GRASS_DARK   = (76, 132, 66)

INK          = (40, 30, 22)
CREAM        = (255, 246, 218)
AMBER        = (250, 196, 104)
TEAL_GLOW    = (122, 198, 214)
LEAF_GREEN   = (92, 160, 82)


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_col(c1, c2, t):
    t = clamp(t)
    return (
        int(_lerp(c1[0], c2[0], t)),
        int(_lerp(c1[1], c2[1], t)),
        int(_lerp(c1[2], c2[2], t)),
    )


class MainMenu:
    """The cozy farm main menu: a layered, gently animated scene.

    The public contract is unchanged. run() still drives the real event loop and
    returns one of the same state strings ("continue", "new_game", "tutorial",
    "quit") when a button is clicked. Everything else here is presentation, and
    the per-frame draw lives in _draw_frame(dt) so it can be rendered headlessly.
    """

    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self._t = 0.0  # seconds of animation time, advanced by dt each frame

        self.font_button = pygame.font.SysFont("arial", 30, bold=True)
        self.font_title = pygame.font.SysFont("arial", 72, bold=True)
        self.font_sub = pygame.font.SysFont("arial", 30, bold=True)
        self.font_note = pygame.font.SysFont("arial", 18, bold=True)

        # Offer "Continue" only when there is a save to continue from.
        has_save = os.path.exists(SAVE_PATH)
        entries = []
        if has_save:
            entries.append(("Continue", "continue"))
        entries.append(("New Game", "new_game"))
        entries.append(("Tutorial", "tutorial"))
        entries.append(("Quit", "quit"))

        self._build_buttons(entries)

        # Static, cached scene. Built once; never rebuilt in the draw path.
        self._field_top = int(SCREEN_H * 0.74)
        self._bg = self._build_background()
        self._vignette = vignette(SCREEN_W, SCREEN_H, strength=38)

        self._build_sun()
        self._build_clouds()
        self._build_particles()
        self._build_living_field()
        # A soft, reusable contact shadow for grounding props.
        self._shadow = self._make_shadow(220, 60)
        self._build_props()
        self._build_title()
        self._build_affordances()

        self._fade_overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self._intro_t = 0.0

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

        self._hover_sound = self._load_sound("seed_select.ogg", 0.22)
        self._click_sound = self._load_sound("ui_click.ogg", 0.35)
        self._hover_idx = -1

        # Music toggle button (top-right corner). Hit-test kept identical to before.
        self._music_btn_center = (SCREEN_W - 35, 35)
        self._music_btn_radius = 25

    # ── build helpers (run once) ────────────────────────────────────────────
    def _build_buttons(self, entries):
        # The first entry is the primary action (Continue when a save exists,
        # otherwise New Game). It gets a larger, warmer panel and a soft glow.
        prim_w, prim_h = 312, 70
        sec_w, sec_h = 264, 56
        gap = 16

        total = 0
        sizes = []
        for i, _ in enumerate(entries):
            w, h = (prim_w, prim_h) if i == 0 else (sec_w, sec_h)
            sizes.append((w, h))
            total += h
        total += gap * (len(entries) - 1)

        center_x = SCREEN_W // 2
        start_y = int(SCREEN_H * 0.60) - total // 2

        self.buttons = []
        y = start_y
        for i, (label, state) in enumerate(entries):
            w, h = sizes[i]
            rect = pygame.Rect(center_x - w // 2, y, w, h)
            self.buttons.append((rect, label, state))
            y += h + gap

        self._primary_idx = 0
        # Smoothed per-button hover and scale, animated toward their targets.
        self._btn_hover = [0.0] * len(self.buttons)
        self._btn_scale = [1.0] * len(self.buttons)
        self._press_idx = -1
        self._mouse_down = False
        self._button_text = {}
        for _rect, label, _state in self.buttons:
            cream = self.font_button.render(label, True, CREAM).convert_alpha()
            ink = self.font_button.render(label, True, INK).convert_alpha()
            dark_shadow = self.font_button.render(label, True, (0, 0, 0)).convert_alpha()
            light_shadow = self.font_button.render(label, True, (255, 244, 210)).convert_alpha()
            self._button_text[(label, CREAM)] = (cream, dark_shadow)
            self._button_text[(label, INK)] = (ink, light_shadow)

    def _build_background(self):
        surf = pygame.Surface((SCREEN_W, SCREEN_H)).convert()

        # Sky gradient across the top portion.
        sky_h = int(SCREEN_H * 0.66)
        surf.blit(vertical_gradient(SCREEN_W, sky_h, SKY_TOP, SKY_HORIZON), (0, 0))
        surf.fill(SKY_HORIZON, (0, sky_h, SCREEN_W, SCREEN_H - sky_h))

        # Rolling hills, far to near, for a little depth.
        self._draw_hill(surf, int(SCREEN_H * 0.60), 26, 0.0070, 0.6, HILL_FAR)
        self._draw_hill(surf, int(SCREEN_H * 0.65), 30, 0.0090, 2.3, HILL_MID)
        self._draw_hill(surf, int(SCREEN_H * 0.70), 18, 0.0130, 4.1, HILL_NEAR)

        # Tilled field. Soil gradient, then a grassy lip, then furrow rows.
        field_top = self._field_top
        soil = vertical_gradient(SCREEN_W, SCREEN_H - field_top, SOIL_TOP, SOIL_BOTTOM)
        surf.blit(soil, (0, field_top))
        self._draw_fence(surf, field_top - 18)
        self._draw_grass_lip(surf, field_top)
        self._draw_furrows(surf, field_top)

        # Soft warm haze along the horizon.
        haze = pygame.Surface((SCREEN_W, 40), pygame.SRCALPHA)
        haze.fill((255, 244, 210, 46))
        surf.blit(haze, (0, int(SCREEN_H * 0.58)))
        return surf

    @staticmethod
    def _draw_hill(surf, base_y, amp, freq, phase, color):
        pts = [(0, SCREEN_H)]
        x = 0
        while x <= SCREEN_W:
            y = base_y + int(math.sin(x * freq + phase) * amp)
            pts.append((x, y))
            x += 12
        pts.append((SCREEN_W, base_y))
        pts.append((SCREEN_W, SCREEN_H))
        pygame.draw.polygon(surf, color, pts)

    def _draw_grass_lip(self, surf, field_top):
        rng = random.Random(404)
        lip = []
        x = 0
        while x <= SCREEN_W:
            lip.append((x, field_top - 4 + int(math.sin(x * 0.05) * 3)))
            x += 10
        lip.append((SCREEN_W, field_top + 10))
        lip.append((0, field_top + 10))
        pygame.draw.polygon(surf, GRASS_LIP, lip)
        for bx in range(0, SCREEN_W, 13):
            bh = rng.randint(5, 11)
            lean = rng.randint(-3, 3)
            base_y = field_top - 2 + int(math.sin(bx * 0.05) * 3)
            col = GRASS_DARK if (bx // 13) % 2 else GRASS_LIP
            pygame.draw.line(surf, col, (bx, base_y), (bx + lean, base_y - bh), 2)

    @staticmethod
    def _draw_fence(surf, y):
        rail = (174, 124, 74)
        rail_dark = (112, 76, 48)
        for ry in (y, y + 18):
            pygame.draw.line(surf, rail_dark, (0, ry + 3), (SCREEN_W, ry + 3), 6)
            pygame.draw.line(surf, rail, (0, ry), (SCREEN_W, ry), 5)
        for x in range(-10, SCREEN_W + 20, 64):
            post = pygame.Rect(x, y - 22, 12, 54)
            pygame.draw.rect(surf, rail_dark, post.move(2, 3), border_radius=3)
            pygame.draw.rect(surf, rail, post, border_radius=3)
            pygame.draw.polygon(surf, (198, 148, 92),
                                [(x, y - 22), (x + 6, y - 33), (x + 12, y - 22)])

    def _draw_furrows(self, surf, field_top):
        y = field_top + 18
        gap = 15
        while y < SCREEN_H:
            pygame.draw.line(surf, FURROW_LIGHT, (0, y - 3), (SCREEN_W, y - 3), 2)
            pygame.draw.line(surf, FURROW_DARK, (0, y), (SCREEN_W, y), 3)
            gap += 3
            y += gap

    def _build_sun(self):
        self._sun_r = 80
        self._sun_cx = int(SCREEN_W * 0.16)
        self._sun_cy = int(SCREEN_H * 0.25)

        img_path = os.path.join(PROPS_DIR, "sun.png")
        if os.path.exists(img_path):
            size = self._sun_r * 2
            raw = pygame.image.load(img_path).convert_alpha()
            self._sun_img = pygame.transform.smoothscale(raw, (size, size))
        else:
            self._sun_img = None

        self._sun_glow = radial_glow(int(self._sun_r * 1.35), (255, 234, 176), 92)

        # A faint sunburst that slowly turns behind the crisp sun for shimmer.
        d = int(self._sun_r * 2.9)
        rays = pygame.Surface((d, d), pygame.SRCALPHA)
        cx = cy = d // 2
        r_in, r_out = self._sun_r * 0.92, self._sun_r * 1.34
        for i in range(12):
            a = math.radians(i * 30)
            da = math.radians(4.5)
            tip = (cx + math.cos(a) * r_out, cy + math.sin(a) * r_out)
            b1 = (cx + math.cos(a - da) * r_in, cy + math.sin(a - da) * r_in)
            b2 = (cx + math.cos(a + da) * r_in, cy + math.sin(a + da) * r_in)
            pygame.draw.polygon(rays, (255, 238, 176, 64), (tip, b1, b2))
        self._sun_rays = rays
        self._sun_ray_frames = [
            pygame.transform.rotozoom(self._sun_rays, a, 1.0).convert_alpha()
            for a in range(0, 360, 12)
        ]
        self._sun_glow_frames = [
            pygame.transform.rotozoom(self._sun_glow, 0, scale).convert_alpha()
            for scale in (0.95, 0.985, 1.02, 1.055)
        ]

    def _build_clouds(self):
        path = os.path.join(PROPS_DIR, "cloud.png")
        raw = pygame.image.load(path).convert_alpha() if os.path.exists(path) else self._make_cloud_surf()

        # depth: (scale, y, speed px/s, alpha, start fraction across the wrap)
        layers = [
            (0.70, int(SCREEN_H * 0.16), 9.0, 150, 0.10),
            (1.05, int(SCREEN_H * 0.27), 15.0, 205, 0.55),
            (1.40, int(SCREEN_H * 0.09), 23.0, 235, 0.80),
        ]
        self._clouds = []
        for scale, y, speed, alpha, frac in layers:
            w = int(160 * scale)
            h = int(80 * scale)
            img = pygame.transform.smoothscale(raw, (w, h)).convert_alpha()
            img.set_alpha(alpha)
            span = SCREEN_W + w
            self._clouds.append({"img": img, "w": w, "y": y, "speed": speed,
                                 "span": span, "offset": frac * span})

    def _build_particles(self):
        rng = random.Random(2024)
        tints = [(255, 236, 168), (255, 248, 224), (250, 214, 120)]
        self._particle_sprites = {}
        for size in (2, 3, 4):
            d = size * 4
            for tint in tints:
                for level in range(6):
                    tw = 0.35 + 0.13 * level
                    dot = pygame.Surface((d, d), pygame.SRCALPHA)
                    pygame.draw.circle(dot, (*tint, int(60 * tw)), (d // 2, d // 2), size * 2)
                    pygame.draw.circle(dot, (*tint, int(210 * tw)), (d // 2, d // 2), size)
                    self._particle_sprites[(size, tint, level)] = dot
        self._particles = []
        for _ in range(28):
            size = rng.randint(2, 4)
            tint = rng.choice(tints)
            self._particles.append({
                "x": rng.uniform(0, SCREEN_W),
                "y": rng.uniform(SCREEN_H * 0.12, SCREEN_H * 0.72),
                "vy": rng.uniform(7.0, 16.0),
                "amp": rng.uniform(6.0, 18.0),
                "freq": rng.uniform(0.4, 0.9),
                "phase": rng.uniform(0.0, math.tau),
                "size": size,
                "tint": tint,
                "tw_freq": rng.uniform(0.8, 1.7),
                "tw_phase": rng.uniform(0.0, math.tau),
            })

    def _build_living_field(self):
        rng = random.Random(808)
        self._crop_frames = [self._make_crop_clump(32, 46, lean) for lean in (-3, -1, 0, 1, 3)]
        self._sprout_frames = [self._make_crop_clump(22, 30, lean, small=True) for lean in (-2, 0, 2)]
        self._field_crops = []
        for row, y in enumerate((self._field_top + 42, self._field_top + 78, self._field_top + 120)):
            for x in range(72 + row * 24, SCREEN_W, 118):
                self._field_crops.append({
                    "x": x + rng.randint(-14, 14),
                    "y": y + rng.randint(-4, 5),
                    "phase": rng.uniform(0.0, math.tau),
                    "small": row == 0,
                })

        self._bee_img = self._make_bee_surf(34, 22)
        self._birds = [
            {"x": 570, "y": 118, "speed": 7.0, "phase": 0.2, "scale": 1.0},
            {"x": 630, "y": 142, "speed": 5.0, "phase": 1.4, "scale": 0.8},
        ]

    def _build_affordances(self):
        self._audio_label = self.font_note.render("Audio", True, CREAM).convert_alpha()
        self._audio_label_shadow = self._audio_label.copy()
        self._audio_label_shadow.fill((*INK, 130), special_flags=pygame.BLEND_RGBA_MULT)
        self._credits_label = self.font_note.render(
            "CMU Game Dev Club  •  cozy farming defense", True, CREAM
        ).convert_alpha()
        pad = 10
        w, h = self._credits_label.get_width() + pad * 2, self._credits_label.get_height() + pad
        self._credits_plate = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(self._credits_plate, (50, 38, 28, 116), self._credits_plate.get_rect(), border_radius=12)
        pygame.draw.rect(self._credits_plate, (255, 238, 190, 92), self._credits_plate.get_rect(), 1, border_radius=12)
        self._credits_label_pos = (pad, pad // 2)

    def _build_props(self):
        prop_h = SCREEN_H // 3
        # The three originals stay; a few crops are scattered as set dressing.
        # Each entry: (surface, center_x, sway amplitude px, sway phase).
        self._scarecrow_img = self._load_prop("scarecrow_icon.png", int(prop_h * 0.9))
        self._squirrel_img = self._make_squirrel_surf(126, 63)
        apple_img = self._load_prop("apple_phase4.png", int(prop_h * 1.4))
        carrot_img = self._load_prop("carrot_phase3.png", prop_h)

        scatter = [
            ("pumpkin_phase4.png", 205, 104, 1.6, 0.0),
            ("sunflower_phase3.png", 395, 150, 4.0, 1.1),
            ("tomato_phase4.png", 770, 122, 3.4, 2.2),
            ("mushroom_phase2.png", 1140, 96, 2.0, 4.0),
        ]

        self._props = []
        self._props.append((self._scarecrow_img, 100, 1.2, 0.4))
        self._props.append((apple_img, 300, 2.4, 1.7))
        self._props.append((carrot_img, 1010, 2.0, 2.6))
        for name, cx, h, amp, phase in scatter:
            img = self._load_prop(name, h)
            if img is not None:
                self._props.append((img, cx, amp, phase))
        self._prop_shadows = {}
        for img, _cx, _amp, _phase in self._props:
            if img is None:
                continue
            sw = int(img.get_width() * 0.7)
            sh = max(6, int(img.get_width() * 0.16))
            self._prop_shadows[img] = pygame.transform.smoothscale(self._shadow, (sw, sh))
        # Squirrel drawn separately so it keeps its low, grounded placement.
        self._squirrel_x = 900

    def _build_title(self):
        if " - " in TITLE:
            main_text, sub_text = TITLE.split(" - ", 1)
        else:
            main_text, sub_text = TITLE, ""

        self._title_main = self._compose_text(main_text, self.font_title, CREAM, INK, 3)
        self._title_sub = self._compose_text(sub_text, self.font_sub, AMBER, INK, 2) if sub_text else None
        self._title_mask = self.font_title.render(main_text, True, (255, 255, 255)).convert_alpha()
        self._title_outline = 3

        # A soft dark silhouette of the title, reused as a drop shadow.
        shadow = self._title_mask.copy()
        shadow.fill((0, 0, 0, 130), special_flags=pygame.BLEND_RGBA_MULT)
        self._title_shadow = shadow

        mw, mh = self._title_main.get_size()
        self._title_main_cy = int(SCREEN_H * 0.17)
        sub_h = self._title_sub.get_height() if self._title_sub else 0
        self._title_sub_cy = self._title_main_cy + mh // 2 + sub_h // 2 - 2

        # A soft sheen stripe that sweeps across the title.
        stripe_w = max(48, mw // 6)
        stripe = pygame.Surface((stripe_w, mh), pygame.SRCALPHA)
        for x in range(stripe_w):
            f = 1.0 - abs(x - stripe_w / 2) / (stripe_w / 2)
            a = int(130 * (f ** 2))
            if a > 0:
                pygame.draw.line(stripe, (255, 255, 255, a), (x, 0), (x, mh))
        self._sheen_stripe = stripe
        self._sheen_w = stripe_w
        self._sheen_frames = []
        for i in range(24):
            sheen = pygame.Surface(self._title_mask.get_size(), pygame.SRCALPHA)
            sx = int((i / 24.0) * (mw + self._sheen_w)) - self._sheen_w
            sheen.blit(self._sheen_stripe, (sx, 0))
            sheen.blit(self._title_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self._sheen_frames.append(sheen)
        self._title_leaf = self._make_title_leaf()
        self._title_cloud = pygame.transform.smoothscale(self._make_cloud_surf(), (86, 43)).convert_alpha()

    @staticmethod
    def _compose_text(text, font, fill, outline, ow):
        body = font.render(text, True, fill)
        w, h = body.get_size()
        surf = pygame.Surface((w + ow * 2, h + ow * 2), pygame.SRCALPHA)
        ol = font.render(text, True, outline)
        for dx in range(-ow, ow + 1):
            for dy in range(-ow, ow + 1):
                if dx * dx + dy * dy <= ow * ow:
                    surf.blit(ol, (ow + dx, ow + dy))
        # A faint top highlight, then the fill, for a soft bevel.
        surf.blit(font.render(text, True, _lerp_col(fill, (255, 255, 255), 0.5)), (ow, ow - 1))
        surf.blit(body, (ow, ow))
        return surf

    # ── the per-frame draw (callable headlessly) ────────────────────────────
    def _draw_frame(self, dt):
        dt = min(0.05, max(0.0, dt))
        self._t += dt

        self.screen.blit(self._bg, (0, 0))
        self._draw_sun()
        self._draw_clouds(dt)
        self._draw_birds()
        self._draw_particles(dt)
        self._draw_living_field()
        self._draw_ground_props()
        self._draw_title()
        self._update_hover_sound()
        for i, (rect, label, state) in enumerate(self.buttons):
            self._draw_button(i, rect, label, state, dt)
        self._draw_music_btn()
        self._draw_affordances()
        self.screen.blit(self._vignette, (0, 0))
        self._draw_intro_fade(dt)

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
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
                    self._mouse_down = True
                    self._press_idx = -1
                    for i, (rect, _label, _state) in enumerate(self.buttons):
                        if rect.collidepoint(event.pos):
                            self._press_idx = i
                            break

                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self._mouse_down = False
                    if self._press_idx >= 0:
                        rect, _label, state = self.buttons[self._press_idx]
                        if rect.collidepoint(event.pos):
                            self._safe_play(self._click_sound)
                            return self._finish_selection(state)
                    self._press_idx = -1

            self._draw_frame(dt)
            pygame.display.flip()

    def _update_hover_sound(self):
        mouse = pygame.mouse.get_pos()
        hovered_idx = -1
        for i, (rect, _label, _state) in enumerate(self.buttons):
            if rect.collidepoint(mouse):
                hovered_idx = i
                break
        if hovered_idx >= 0 and hovered_idx != self._hover_idx:
            self._safe_play(self._hover_sound)
        self._hover_idx = hovered_idx

    def _draw_affordances(self):
        label_rect = self._audio_label.get_rect(midright=(self._music_btn_center[0] - 34, self._music_btn_center[1]))
        self.screen.blit(self._audio_label_shadow, label_rect.move(1, 1))
        self.screen.blit(self._audio_label, label_rect)

        plate_rect = self._credits_plate.get_rect(bottomleft=(18, SCREEN_H - 14))
        self.screen.blit(self._credits_plate, plate_rect)
        self.screen.blit(self._credits_label, (plate_rect.x + self._credits_label_pos[0],
                                               plate_rect.y + self._credits_label_pos[1]))

    def _draw_intro_fade(self, dt):
        self._intro_t = min(1.0, self._intro_t + dt / 0.55)
        fade = int(255 * (1.0 - self._intro_t) ** 2)
        if fade <= 0:
            return
        self._fade_overlay.fill((255, 236, 186, fade))
        self.screen.blit(self._fade_overlay, (0, 0))

    def _finish_selection(self, state):
        for i in range(12):
            dt = self.clock.tick(FPS) / 1000.0
            self._draw_frame(dt)
            alpha = int(190 * ((i + 1) / 12.0) ** 2)
            self._fade_overlay.fill((34, 24, 18, alpha))
            self.screen.blit(self._fade_overlay, (0, 0))
            pygame.display.flip()
        pygame.mixer.music.stop()
        return state

    # ── scene pieces ────────────────────────────────────────────────────────
    def _draw_sun(self):
        cx, cy = self._sun_cx, self._sun_cy

        glow_i = int((0.5 + 0.5 * math.sin(self._t * 1.6)) * (len(self._sun_glow_frames) - 1))
        glow = self._sun_glow_frames[glow_i]
        self.screen.blit(glow, glow.get_rect(center=(cx, cy)))

        rays = self._sun_ray_frames[int(self._t * 2.5) % len(self._sun_ray_frames)]
        self.screen.blit(rays, rays.get_rect(center=(cx, cy)))

        if self._sun_img is not None:
            self.screen.blit(self._sun_img, self._sun_img.get_rect(center=(cx, cy)))
        else:
            pygame.draw.circle(self.screen, (255, 220, 80), (cx, cy), self._sun_r)
            pygame.draw.circle(self.screen, (255, 245, 160),
                               (cx - 16, cy - 16), self._sun_r // 5)

    def _draw_clouds(self, dt):
        for c in self._clouds:
            c["offset"] = (c["offset"] + c["speed"] * dt) % c["span"]
            x = int(c["offset"]) - c["w"]
            self.screen.blit(c["img"], (x, c["y"]))
            if x > 0:
                self.screen.blit(c["img"], (x - c["span"], c["y"]))
            elif x + c["w"] < SCREEN_W:
                self.screen.blit(c["img"], (x + c["span"], c["y"]))

    def _draw_particles(self, dt):
        for p in self._particles:
            p["y"] -= p["vy"] * dt
            if p["y"] < -8:
                p["y"] = self._field_top + 8
                p["x"] = (p["x"] + 137.0) % SCREEN_W
            x = int(p["x"] + math.sin(self._t * p["freq"] + p["phase"]) * p["amp"])
            y = int(p["y"])
            tw = 0.45 + 0.55 * (0.5 - 0.5 * math.cos(self._t * p["tw_freq"] + p["tw_phase"]))
            level = max(0, min(5, int(tw * 5)))
            dot = self._particle_sprites[(p["size"], p["tint"], level)]
            d = dot.get_width()
            self.screen.blit(dot, (x - d // 2, y - d // 2))

    def _draw_birds(self):
        for b in self._birds:
            x = int((b["x"] + self._t * b["speed"]) % (SCREEN_W + 80) - 40)
            y = int(b["y"] + math.sin(self._t * 0.8 + b["phase"]) * 5)
            wing = int(5 + 2 * math.sin(self._t * 5.0 + b["phase"]))
            s = b["scale"]
            col = (82, 86, 78)
            pygame.draw.line(self.screen, col, (x, y), (x - int(12 * s), y + wing), 2)
            pygame.draw.line(self.screen, col, (x, y), (x + int(12 * s), y + wing), 2)

    def _draw_living_field(self):
        for c in self._field_crops:
            sway = math.sin(self._t * 1.8 + c["phase"])
            if c["small"]:
                frames = self._sprout_frames
                idx = 0 if sway < -0.33 else 2 if sway > 0.33 else 1
            else:
                frames = self._crop_frames
                idx = max(0, min(len(frames) - 1, int((sway + 1.0) * 0.5 * (len(frames) - 1))))
            img = frames[idx]
            self.screen.blit(img, img.get_rect(midbottom=(c["x"], c["y"])))

        bx = int(SCREEN_W * 0.30 + math.sin(self._t * 0.9) * 72 + math.sin(self._t * 2.7) * 12)
        by = int(SCREEN_H * 0.48 + math.sin(self._t * 1.7 + 1.2) * 26)
        self.screen.blit(self._bee_img, self._bee_img.get_rect(center=(bx, by)))

    def _draw_ground_props(self):
        bottom_y = SCREEN_H - SCREEN_H // 8
        for img, cx, amp, phase in self._props:
            if img is None:
                continue
            sway = math.sin(self._t * 1.1 + phase) * amp
            rect = img.get_rect()
            rect.centerx = int(cx + sway)
            rect.bottom = bottom_y
            shadow = self._prop_shadows.get(img)
            self.screen.blit(shadow, shadow.get_rect(center=(int(cx), bottom_y - 4)))
            self.screen.blit(img, rect)

        if self._squirrel_img is not None:
            rect = self._squirrel_img.get_rect()
            rect.centerx = self._squirrel_x
            rect.bottom = bottom_y
            self.screen.blit(self._squirrel_img, rect)

    def _draw_title(self):
        bob = math.sin(self._t * 1.4) * 4.0
        ow = self._title_outline
        main_rect = self._title_main.get_rect(center=(SCREEN_W // 2, int(self._title_main_cy + bob)))

        cloud_rect = self._title_cloud.get_rect(center=(main_rect.left + 26, main_rect.top + 10))
        self.screen.blit(self._title_cloud, cloud_rect)
        leaf_rect = self._title_leaf.get_rect(center=(main_rect.right - 18, main_rect.bottom - 8))
        self.screen.blit(self._title_leaf, leaf_rect)

        # Drop shadow first, then the title, then the cached sheen sweep.
        self.screen.blit(self._title_shadow, (main_rect.x + ow, main_rect.y + ow + 6))
        self.screen.blit(self._title_main, main_rect)

        sheen = self._sheen_frames[int(self._t * 10.0) % len(self._sheen_frames)]
        self.screen.blit(sheen, (main_rect.x + ow, main_rect.y + ow))

        if self._title_sub is not None:
            sub_rect = self._title_sub.get_rect(center=(SCREEN_W // 2, int(self._title_sub_cy + bob)))
            self.screen.blit(self._title_sub, sub_rect)

    def _draw_button(self, idx, rect, label, state, dt):
        mouse = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse)
        pressed = hovered and self._mouse_down and self._press_idx == idx

        # Ease the hover and scale toward their targets so motion feels soft.
        target_hover = 1.0 if hovered else 0.0
        self._btn_hover[idx] += (target_hover - self._btn_hover[idx]) * min(1.0, dt * 14.0)
        h = self._btn_hover[idx]

        target_scale = 0.97 if pressed else (1.045 if hovered else 1.0)
        self._btn_scale[idx] += (target_scale - self._btn_scale[idx]) * min(1.0, dt * 16.0)
        s = self._btn_scale[idx]

        is_primary = idx == self._primary_idx
        draw_rect = pygame.Rect(0, 0, int(rect.w * s), int(rect.h * s))
        draw_rect.center = rect.center
        radius = 16

        if state == "quit":
            top, bot, border = (150, 120, 116), (118, 92, 90), (208, 192, 188)
            text_col = CREAM
        elif is_primary:
            top, bot, border = (252, 206, 118), (224, 158, 74), (255, 232, 168)
            text_col = INK
        else:
            top, bot, border = (110, 162, 184), (74, 122, 150), (200, 226, 236)
            text_col = CREAM

        if is_primary:
            breath = pulse(self._t, 2.4)
            soft_glow(self.screen, draw_rect, radius, (255, 198, 108), int(52 + 58 * breath))
        elif h > 0.02:
            soft_glow(self.screen, draw_rect, radius, TEAL_GLOW, int(28 + 54 * h), spread=12)

        # Soft drop shadow that lifts on hover and tucks in on press.
        lift = int(6 - 4 * (1.0 if pressed else 0.0)) + int(2 * h)
        soft_shadow(self.screen, draw_rect, radius=radius, lift=lift, alpha=34 if not pressed else 24)

        # Brighten on hover, darken slightly on press.
        bf = 0.12 * h
        top = _lerp_col(top, (255, 255, 255), bf)
        bot = _lerp_col(bot, (255, 255, 255), bf)
        if pressed:
            top = _lerp_col(top, (0, 0, 0), 0.10)
            bot = _lerp_col(bot, (0, 0, 0), 0.10)

        pygame.draw.rect(self.screen, bot, draw_rect, border_radius=radius)
        top_rect = pygame.Rect(draw_rect.x, draw_rect.y, draw_rect.w, int(draw_rect.h * 0.58))
        pygame.draw.rect(self.screen, top, top_rect,
                         border_top_left_radius=radius, border_top_right_radius=radius)
        hi = pygame.Rect(draw_rect.x + 6, draw_rect.y + 4, draw_rect.w - 12, 3)
        pygame.draw.rect(self.screen, _lerp_col(top, (255, 255, 255), 0.45), hi, border_radius=2)
        pygame.draw.rect(self.screen, _lerp_col(border, (255, 255, 255), bf),
                         draw_rect, 3, border_radius=radius)

        label_surf, shadow = self._button_text[(label, text_col)]
        lr = label_surf.get_rect(center=draw_rect.center)
        self.screen.blit(shadow, shadow.get_rect(center=(draw_rect.centerx, draw_rect.centery + 2)))
        self.screen.blit(label_surf, lr)

    def _toggle_music(self):
        if not self._music_available:
            self._music_on = not self._music_on
            return
        self._music_on = not self._music_on
        if self._music_on:
            pygame.mixer.music.unpause()
        else:
            pygame.mixer.music.pause()

    @staticmethod
    def _load_sound(filename, volume):
        path = os.path.join(os.path.dirname(__file__), "passthegame_audio", filename)
        if not os.path.exists(path):
            return None
        try:
            sound = pygame.mixer.Sound(path)
            sound.set_volume(volume)
            return sound
        except Exception:
            return None

    @staticmethod
    def _safe_play(sound):
        if sound is None:
            return
        try:
            sound.play()
        except Exception:
            pass

    def _draw_music_btn(self):
        cx, cy = self._music_btn_center
        r = self._music_btn_radius
        mouse = pygame.mouse.get_pos()
        dx0, dy0 = mouse[0] - cx, mouse[1] - cy
        hovered = dx0 * dx0 + dy0 * dy0 <= r * r

        base = _lerp_col((70, 110, 150), (104, 150, 196), 1.0 if hovered else 0.0)
        pygame.draw.circle(self.screen, base, (cx, cy), r)
        pygame.draw.circle(self.screen, _lerp_col(base, (255, 255, 255), 0.4),
                           (cx, cy - r // 3), r - 4, 0)
        pygame.draw.circle(self.screen, base, (cx, cy - r // 3), r - 4, 0)
        pygame.draw.circle(self.screen, (210, 230, 244), (cx, cy), r, 3)

        # A small procedural speaker, so we never depend on a symbol font.
        ink = (255, 250, 236)
        bx, by = cx - 9, cy
        pygame.draw.rect(self.screen, ink, pygame.Rect(bx, by - 4, 5, 9), border_radius=1)
        pygame.draw.polygon(self.screen, ink,
                            [(bx + 5, by - 4), (bx + 12, by - 10), (bx + 12, by + 10), (bx + 5, by + 5)])
        if self._music_on:
            pygame.draw.arc(self.screen, ink, pygame.Rect(bx + 11, by - 9, 10, 18), -1.0, 1.0, 2)
            pygame.draw.arc(self.screen, ink, pygame.Rect(bx + 11, by - 13, 16, 26), -0.9, 0.9, 2)
        else:
            pygame.draw.line(self.screen, (228, 96, 86),
                             (cx - r + 8, cy - r + 8), (cx + r - 8, cy + r - 8), 3)

    # ── small procedural assets / loaders ───────────────────────────────────
    @staticmethod
    def _make_shadow(w, h):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        steps = 10
        for i in range(steps, 0, -1):
            f = i / steps
            a = int(70 * (1.0 - f))
            pygame.draw.ellipse(surf, (24, 18, 12, a),
                                (cx - int(cx * f), cy - int(cy * f), int(w * f), int(h * f)))
        return surf

    @staticmethod
    def _make_cloud_surf():
        surf = pygame.Surface((160, 80), pygame.SRCALPHA)
        white = (255, 255, 255, 235)
        pygame.draw.ellipse(surf, white, pygame.Rect(10, 30, 140, 45))
        pygame.draw.ellipse(surf, white, pygame.Rect(10, 10, 60, 55))
        pygame.draw.ellipse(surf, white, pygame.Rect(50, 0, 70, 60))
        pygame.draw.ellipse(surf, white, pygame.Rect(90, 15, 55, 50))
        return surf

    @staticmethod
    def _make_crop_clump(w, h, lean, small=False):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        base = (w // 2, h - 3)
        stem = (70, 132, 62)
        leaf = (104, 176, 86) if not small else (124, 190, 96)
        pygame.draw.line(surf, stem, base, (w // 2 + lean, 7), 3 if not small else 2)
        for i, side in enumerate((-1, 1, -1, 1)):
            y = h - 12 - i * (7 if not small else 5)
            length = 12 if not small else 8
            end = (w // 2 + lean + side * length, y - 5)
            pygame.draw.line(surf, leaf, (w // 2 + lean, y), end, 3 if not small else 2)
            pygame.draw.circle(surf, _lerp_col(leaf, (255, 255, 255), 0.12), end, 3 if not small else 2)
        pygame.draw.ellipse(surf, (44, 28, 18, 72), (w // 2 - 10, h - 6, 20, 6))
        return surf

    @staticmethod
    def _make_bee_surf(w, h):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (255, 244, 235, 120), pygame.Rect(5, 0, 12, 10))
        pygame.draw.ellipse(surf, (255, 244, 235, 120), pygame.Rect(16, 1, 12, 10))
        pygame.draw.ellipse(surf, (238, 184, 54), pygame.Rect(7, 7, 19, 11))
        pygame.draw.line(surf, (48, 34, 24), (13, 8), (12, 17), 2)
        pygame.draw.line(surf, (48, 34, 24), (19, 8), (18, 17), 2)
        pygame.draw.circle(surf, (42, 30, 22), (26, 12), 4)
        pygame.draw.circle(surf, (255, 255, 255), (28, 10), 1)
        return surf

    @staticmethod
    def _make_title_leaf():
        surf = pygame.Surface((92, 58), pygame.SRCALPHA)
        stem = (66, 122, 58)
        pygame.draw.arc(surf, stem, pygame.Rect(6, 16, 80, 36), 3.45, 6.05, 4)
        for x, y, flip in ((24, 30, -1), (42, 24, 1), (58, 25, -1), (70, 20, 1)):
            pts = [(x, y), (x + flip * 18, y - 11), (x + flip * 12, y + 9)]
            pygame.draw.polygon(surf, LEAF_GREEN, pts)
            pygame.draw.line(surf, _lerp_col(LEAF_GREEN, (255, 255, 255), 0.22),
                             (x, y), (x + flip * 13, y - 4), 1)
        return surf

    @staticmethod
    def _make_squirrel_surf(w, h):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        fur = (165, 115, 70, 235)
        fur_dark = (125, 85, 55, 220)
        belly = (215, 175, 125, 220)
        outline = (35, 30, 25, 210)
        foot = (90, 60, 40, 220)

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
        path = os.path.join(PROPS_DIR, filename)
        if not os.path.exists(path):
            return None
        raw = pygame.image.load(path).convert_alpha()
        w, h = raw.get_size()
        return pygame.transform.smoothscale(raw, (int(w * height / h), height))
