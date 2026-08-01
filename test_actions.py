from engine.world import create_new_game
from engine.actions import (
    move_player,
    take_item,
    drop_item,
    wait,
)


game = create_new_game()

print("START")
print("Location:", game.current_location().name)
print("Inventory:", game.player.inventory)

print("\nTAKE RUSTY KEY")
result = take_item(game, "Rusty Key")
print(result.success)
print(result.message)

print("\nINVENTORY")
print(game.player.inventory)

print("\nMOVE OUTSIDE")
result = move_player(game, "outside")
print(result.success)
print(result.message)

print("\nLOCATION")
print(game.current_location().name)

print("\nWAIT")
result = wait(game, 30)
print(result.success)
print(result.message)

print("Day:", game.world.day)
print("Time:", game.world.time)

print("\nDROP RUSTY KEY")
result = drop_item(game, "Rusty Key")
print(result.success)
print(result.message)

print("\nINVENTORY")
print(game.player.inventory)