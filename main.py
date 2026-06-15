import os
import pygame
from settings import SCREEN_W, SCREEN_H, GAME_FULLSCREEN
from main_menu import MainMenu
from tutorial import Tutorial
from game import Game

# Nearest-neighbour scaling so fullscreen stays crisp instead of blurring the
# 1200x600 frame when the monitor is not an exact multiple. Must be set before
# the display (renderer) is created.
os.environ.setdefault("SDL_HINT_RENDER_SCALE_QUALITY", "0")


def main():
    pygame.init()
    # Create the screen once here and pass it around. Windowed SCALED keeps text
    # crisp (integer scaling); fullscreen is opt-in via settings.GAME_FULLSCREEN.
    flags = pygame.SCALED | (pygame.FULLSCREEN if GAME_FULLSCREEN else 0)
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)

    state = "menu"

    while state != "quit":
        if state == "menu":
            menu = MainMenu(screen)
            state = menu.run()

        elif state == "tutorial":
            tutorial = Tutorial(screen)
            state = tutorial.run()

        elif state in ("new_game", "continue"):
            game = Game(new_game=(state == "new_game"))
            game.screen = screen
            game.run()
            state = "menu"

    pygame.quit()

if __name__ == "__main__":
    main()
