from engine.world import create_new_game
from engine.context import build_game_context


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

game = create_new_game()
context = build_game_context(game)

print("=== 1. Context contains core sections ===")
results.append(check(
    "Contains World header",
    "World:" in context,
))
results.append(check(
    "Contains Genre",
    "Genre:" in context,
))
results.append(check(
    "Contains Day",
    "Day:" in context,
))
results.append(check(
    "Contains Time",
    "Time:" in context,
))
results.append(check(
    "Contains Weather",
    "Weather:" in context,
))

print("\n=== 2. Context contains player info ===")
results.append(check(
    "Contains Player section",
    "PLAYER" in context,
))
results.append(check(
    "Contains HP",
    "HP:" in context,
))
results.append(check(
    "Contains Location",
    "Location:" in context,
))
results.append(check(
    "Contains Inventory",
    "Inventory:" in context,
))

print("\n=== 3. Context contains NPC info ===")
results.append(check(
    "Contains Old Man",
    "Old Man" in context,
))
results.append(check(
    "Contains Sarah",
    "Sarah" in context,
))
results.append(check(
    "Contains Personality",
    "Personality:" in context,
))
results.append(check(
    "Contains Knowledge",
    "Knowledge:" in context,
))
results.append(check(
    "Contains Beliefs",
    "Beliefs:" in context,
))
results.append(check(
    "Contains Goals",
    "Goals:" in context,
))
results.append(check(
    "Contains Relationships",
    "Relationships:" in context,
))
results.append(check(
    "Contains Schedule",
    "Schedule:" in context,
))

print("\n=== 4. Context contains location info ===")
results.append(check(
    "Contains Old Wooden House",
    "Old Wooden House" in context,
))
results.append(check(
    "Contains Exits",
    "Exits:" in context,
))
results.append(check(
    "Contains Items",
    "Items:" in context,
))

print("\n=== 5. Context contains interactables ===")
results.append(check(
    "Contains upstairs door description",
    "upstairs door" in context,
))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
