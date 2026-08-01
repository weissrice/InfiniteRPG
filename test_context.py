from engine.world import create_new_game
from engine.context import build_game_context


game = create_new_game()

context = build_game_context(game)

print(context)