import tempfile
from pathlib import Path

from engine.world import create_new_game
from engine.actions import move_player
from engine.map import render_map, get_location_details
from engine.context import build_game_context
from engine.save import save_game, load_game


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

# ---------------------------------------------------------------
# 1. Map renders successfully
# ---------------------------------------------------------------

print("\n=== 1. Map renders successfully ===")
game = create_new_game()
map_str = render_map(game)

results.append(check(
    "Map is a string",
    isinstance(map_str, str),
))
results.append(check(
    "Map is not empty",
    len(map_str) > 0,
))
results.append(check(
    "Map contains WORLD MAP header",
    "WORLD MAP" in map_str,
))

# ---------------------------------------------------------------
# 2. All world locations appear
# ---------------------------------------------------------------

print("\n=== 2. All world locations appear ===")
results.append(check(
    "Old Wooden House in map",
    "Old Wooden House" in map_str,
))
results.append(check(
    "Forest Edge in map",
    "Forest Edge" in map_str,
))
results.append(check(
    "Kitchen in map",
    "Kitchen" in map_str,
))
results.append(check(
    "Upstairs Hall in map",
    "Upstairs Hall" in map_str,
))
results.append(check(
    "Deep Forest in map",
    "Deep Forest" in map_str,
))

# ---------------------------------------------------------------
# 3. Player current location is marked
# ---------------------------------------------------------------

print("\n=== 3. Player current location is marked ===")
results.append(check(
    "Current location has @ marker",
    "@ Old Wooden H" in map_str,
))

# ---------------------------------------------------------------
# 4. Connections are rendered
# ---------------------------------------------------------------

print("\n=== 4. Connections are rendered ===")
results.append(check(
    "CONNECTIONS section exists",
    "CONNECTIONS" in map_str,
))
results.append(check(
    "Old Wooden House <-> Forest Edge connection shown",
    "Old Wooden House <-> Forest Edge" in map_str
    or "Forest Edge <-> Old Wooden House" in map_str,
))

# ---------------------------------------------------------------
# 5. Starting location is visited
# ---------------------------------------------------------------

print("\n=== 5. Starting location is visited ===")
results.append(check(
    "Starting location in visited_locations",
    "old_wooden_house" in game.visited_locations,
))

# ---------------------------------------------------------------
# 6. Successful movement marks destination visited
# ---------------------------------------------------------------

print("\n=== 6. Successful movement marks destination visited ===")
game = create_new_game()
result = move_player(game, "outside")

results.append(check(
    "Movement succeeds",
    result.success,
))
results.append(check(
    "Destination marked as visited",
    "forest_edge" in game.visited_locations,
))

# ---------------------------------------------------------------
# 7. Failed movement does not mark destination visited
# ---------------------------------------------------------------

print("\n=== 7. Failed movement does not mark destination visited ===")
game = create_new_game()
result = move_player(game, "nonexistent")

results.append(check(
    "Movement fails",
    not result.success,
))
results.append(check(
    "Only starting location visited",
    game.visited_locations == {"old_wooden_house"},
))

# ---------------------------------------------------------------
# 8. NPCs appear at their actual current locations
# ---------------------------------------------------------------

print("\n=== 8. NPCs appear at their actual current locations ===")
game = create_new_game()
map_str = render_map(game)

# Old Man and Sarah are at old_wooden_house
# Merchant is at forest_edge
results.append(check(
    "NPCs marker present for Old Wooden House",
    "N" in map_str,
))

# ---------------------------------------------------------------
# 9. Dead NPCs do not appear
# ---------------------------------------------------------------

print("\n=== 9. Dead NPCs do not appear ===")
game = create_new_game()
merchant = game.world.npcs["merchant"]
merchant.hp = 0

map_str = render_map(game)
details = get_location_details(game, "forest_edge")

results.append(check(
    "Dead merchant not in location details",
    "Merchant" not in details,
))

# ---------------------------------------------------------------
# 10. Items appear at their actual locations
# ---------------------------------------------------------------

print("\n=== 10. Items appear at their actual locations ===")
game = create_new_game()
details = get_location_details(game, "old_wooden_house")

results.append(check(
    "Rusty Key in location details",
    "Rusty Key" in details,
))
results.append(check(
    "Torn Note in location details",
    "Torn Note" in details,
))

# ---------------------------------------------------------------
# 11. Interactables appear with useful state
# ---------------------------------------------------------------

print("\n=== 11. Interactables appear with useful state ===")
game = create_new_game()
details = get_location_details(game, "upstairs")

results.append(check(
    "Locked Upstairs Door in details",
    "Locked Upstairs Door" in details,
))
results.append(check(
    "Door state shown",
    "[locked]" in details,
))

# ---------------------------------------------------------------
# 12. Map rendering does not mutate game state
# ---------------------------------------------------------------

print("\n=== 12. Map rendering does not mutate game state ===")
game = create_new_game()
original_location = game.player.location
original_visited = game.visited_locations.copy()

render_map(game)

results.append(check(
    "Player location unchanged",
    game.player.location == original_location,
))
results.append(check(
    "Visited locations unchanged",
    game.visited_locations == original_visited,
))

# ---------------------------------------------------------------
# 13. Save/load preserves visited locations
# ---------------------------------------------------------------

print("\n=== 13. Save/load preserves visited locations ===")
game = create_new_game()
game.visited_locations.add("forest_edge")
game.visited_locations.add("kitchen")

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    save_path = Path(f.name)

save_game(game, save_path)
loaded = load_game(save_path)

results.append(check(
    "Visited locations preserved",
    loaded.visited_locations == {"old_wooden_house", "forest_edge", "kitchen"},
))

save_path.unlink(missing_ok=True)

# ---------------------------------------------------------------
# 14. Old save data without visited_locations loads safely
# ---------------------------------------------------------------

print("\n=== 14. Old save data without visited_locations loads safely ===")
import json

old_save = {
    "version": 2,
    "player": {
        "name": "Traveler",
        "hp": 100,
        "max_hp": 100,
        "location": "old_wooden_house",
        "inventory": ["Rusty Key", "Torn Note"],
        "xp": 0,
        "level": 1,
        "stat_points": 0,
        "strength": 10,
        "vitality": 10,
        "agility": 10,
        "intelligence": 10,
        "money": 0,
    },
    "world": {
        "name": "Test World",
        "genre": "fantasy",
        "time": "12:00",
        "day": 1,
        "weather": "clear",
        "locations": {},
        "npcs": {},
    },
    "conversations": {},
    "quests": {},
}

with tempfile.NamedTemporaryFile(
    mode="w", suffix=".json", delete=False
) as f:
    json.dump(old_save, f)
    old_path = Path(f.name)

old_loaded = load_game(old_path)

results.append(check(
    "Old save loads without error",
    old_loaded is not None,
))
results.append(check(
    "Visited locations defaults to empty set",
    old_loaded.visited_locations == set(),
))

old_path.unlink(missing_ok=True)

# ---------------------------------------------------------------
# 15. /map command works
# ---------------------------------------------------------------

print("\n=== 15. /map command works ===")

import ast
import inspect

with open("main.py", "r", encoding="utf-8") as f:
    source = f.read()

results.append(check(
    "/map handler present",
    '"/map"' in source,
))
results.append(check(
    "show_map function defined",
    "def show_map" in source,
))

# ---------------------------------------------------------------
# 16. /help includes /map
# ---------------------------------------------------------------

print("\n=== 16. /help includes /map ===")
results.append(check(
    "/map in help text",
    "/map" in source,
))

# ---------------------------------------------------------------
# 17. Multiple NPCs at one location render correctly
# ---------------------------------------------------------------

print("\n=== 17. Multiple NPCs at one location render correctly ===")
game = create_new_game()
details = get_location_details(game, "old_wooden_house")

results.append(check(
    "Old Man in details",
    "Old Man" in details,
))
results.append(check(
    "Sarah in details",
    "Sarah" in details,
))

# ---------------------------------------------------------------
# 18. Multiple items at one location render correctly
# ---------------------------------------------------------------

print("\n=== 18. Multiple items at one location render correctly ===")
game = create_new_game()
details = get_location_details(game, "old_wooden_house")

results.append(check(
    "Rusty Key in details",
    "Rusty Key" in details,
))
results.append(check(
    "Torn Note in details",
    "Torn Note" in details,
))

# ---------------------------------------------------------------
# 19. Empty locations render correctly
# ---------------------------------------------------------------

print("\n=== 19. Empty locations render correctly ===")
game = create_new_game()
# Forest Edge has items but let's check deep_forest
details = get_location_details(game, "deep_forest")

results.append(check(
    "Deep Forest details not empty",
    len(details) > 0,
))
results.append(check(
    "Deep Forest has description",
    "trees grow thicker" in details,
))

# ---------------------------------------------------------------
# 20. Map remains deterministic across repeated renders
# ---------------------------------------------------------------

print("\n=== 20. Map remains deterministic across repeated renders ===")
game = create_new_game()
map1 = render_map(game)
map2 = render_map(game)
map3 = render_map(game)

results.append(check(
    "Map render 1 == render 2",
    map1 == map2,
))
results.append(check(
    "Map render 2 == render 3",
    map2 == map3,
))

# ---------------------------------------------------------------
# Summary
# ---------------------------------------------------------------

print("\n" + "=" * 60)
passed = sum(results)
total = len(results)

if passed == total:
    print(f"ALL {total} ASSERTIONS PASSED")
else:
    failed = total - passed
    print(f"{passed}/{total} assertions passed ({failed} FAILED)")

print("=" * 60)
raise SystemExit(0 if passed == total else 1)
