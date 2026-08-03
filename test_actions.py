from engine.world import create_new_game
from engine.actions import (
    move_player,
    take_item,
    drop_item,
    wait,
)


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

game = create_new_game()

print("=== 1. Initial state ===")
results.append(check(
    "Starts in old_wooden_house",
    game.player.location == "old_wooden_house",
))
results.append(check(
    "Starts with Rusty Key and Torn Note",
    game.player.inventory == ["Rusty Key", "Torn Note"],
))
results.append(check(
    "Day starts at 1",
    game.world.day == 1,
))
results.append(check(
    "Time starts at 12:00",
    game.world.time == "12:00",
))

print("\n=== 2. Take item ===")
result = take_item(game, "Rusty Key")
results.append(check(
    "Take succeeds (Rusty Key is in location items)",
    result.success is True,
))
results.append(check(
    "Rusty Key duplicated in inventory (pre-existing world state)",
    game.player.inventory.count("Rusty Key") == 2,
))

print("\n=== 3. Move outside ===")
result = move_player(game, "outside")
results.append(check(
    "Move succeeds",
    result.success is True,
))
results.append(check(
    "Now at forest_edge",
    game.player.location == "forest_edge",
))

print("\n=== 4. Wait advances time ===")
result = wait(game, 30)
results.append(check(
    "Wait succeeds",
    result.success is True,
))
results.append(check(
    "Time advanced by 30 minutes",
    game.world.time == "12:30",
))
results.append(check(
    "Day still 1 after 30 min",
    game.world.day == 1,
))

print("\n=== 5. Wait across midnight ===")
result = wait(game, 720)
results.append(check(
    "Wait 720 min succeeds",
    result.success is True,
))
results.append(check(
    "Day advanced to 2",
    game.world.day == 2,
))

print("\n=== 6. Drop item ===")
result = drop_item(game, "Rusty Key")
results.append(check(
    "Drop succeeds",
    result.success is True,
))
results.append(check(
    "One Rusty Key removed from inventory",
    game.player.inventory.count("Rusty Key") == 1,
))
results.append(check(
    "Torn Note still in inventory",
    "Torn Note" in game.player.inventory,
))

print("\n=== 7. Drop non-existent item fails ===")
result = drop_item(game, "Nonexistent Item")
results.append(check(
    "Drop non-existent fails",
    result.success is False,
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
