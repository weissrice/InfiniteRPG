"""Launch the Pygame UI for InfiniteRPG."""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.pygame.app import run_game

if __name__ == "__main__":
    run_game()
