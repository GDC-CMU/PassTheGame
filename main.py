import pygame
from settings import SCREEN_W, SCREEN_H
from main_menu import MainMenu
from tutorial import Tutorial
from game import Game

def main():
    pygame.init()
    # Create the screen once here and pass it around
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.SCALED | pygame.FULLSCREEN)

    state = "menu"

    while state != "quit":
        if state == "menu":
            menu = MainMenu(screen)
            state = menu.run()

        elif state == "tutorial":
            tutorial = Tutorial(screen)
            state = tutorial.run()

        elif state == "start":
            game = Game()
            game.screen = screen
            game.run()
            state = "menu"

    pygame.quit()

if __name__ == "__main__":
    main()
