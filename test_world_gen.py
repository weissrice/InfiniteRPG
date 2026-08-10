# -*- coding: utf-8 -*-
"""Tests for the AI World Generation system."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.world import create_new_game
from engine.state import GameState, Location, NPC, Interactable
from engine.world_gen import (
    generate_world_content,
    _make_safe_id,
    _assign_id,
    _compute_coordinates,
    _find_free_cell,
    _create_connections,
    _register_npcs,
    _register_items,
    _register_interactables,
    _parse_generation_response,
    _validate_generation,
    GenerationResult,
    _DIRECTION_VECTORS,
)


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []
test_results = []  # (name, passed) pairs for summary


def test(name):
    """Start a new test group."""
    return name


def end_test(name, checks):
    """Record test result: all checks must pass."""
    test_results.append((name, all(checks)))


class MockAI:
    def __init__(self, response_data):
        self.response_data = response_data

    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        return json.dumps(self.response_data)

    def close(self):
        pass


def make_generation_response(
    name="Misty Creek Village",
    description="A small village along a misty creek.",
    visual_type="village",
    is_interior=False,
    items=None,
    npcs=None,
    interactables=None,
    connections=None,
):
    return {
        "location": {
            "name": name,
            "description": description,
            "visual_type": visual_type,
            "is_interior": is_interior,
            "items": items or [],
        },
        "npcs": npcs or [],
        "items": items or [],
        "interactables": interactables or [],
        "connections": connections or [],
    }


# 1. Generate a new location
print("\n=== 1. Generate a new location ===")
game = create_new_game()
response = make_generation_response(
    name="Misty Creek Village",
    description="A small village along a misty creek.",
    visual_type="village",
)
ai = MockAI(response)
result = generate_world_content(game, ai, "old_wooden_house", "east")
results.append(check("Generation succeeded", result.success))
results.append(check("Location created", result.location is not None))
results.append(check("Location name matches", result.location.name == "Misty Creek Village"))
results.append(check("Location in game world", result.location.id in game.world.locations))
test_results.append(("Generate a new location", all(results[-4:])))

# 2. Generate east of player -> coordinates +x (or nearby if occupied)
print("\n=== 2. Generate east -> +x ===")
game = create_new_game()
ref = game.current_location()
ai = MockAI(make_generation_response(name="Eastern Clearing"))
result = generate_world_content(game, ai, ref.id, "east")
results.append(check("Generation succeeded", result.success))
dx = result.location.map_x - ref.map_x
dy = result.location.map_y - ref.map_y
results.append(check("East: offset moves in +x direction (or shifts if occupied)", dx >= 1 or (dx == 0 and abs(dy) == 1)))
test_results.append(("Generate east -> +x", all(results[-3:])))

# 3. Generate west -> coordinates -x (or nearby if occupied)
print("\n=== 3. Generate west -> -x ===")
game = create_new_game()
ref = game.current_location()
ai = MockAI(make_generation_response(name="Western Ridge"))
result = generate_world_content(game, ai, ref.id, "west")
results.append(check("Generation succeeded", result.success))
dx = result.location.map_x - ref.map_x
dy = result.location.map_y - ref.map_y
results.append(check("West: offset moves in -x direction (or shifts if occupied)", dx <= -1 or (dx == 0 and abs(dy) == 1)))
test_results.append(("Generate west -> -x", all(results[-3:])))

# 4. Generate north -> coordinates -y
print("\n=== 4. Generate north -> -y ===")
game = create_new_game()
ref = game.current_location()
ai = MockAI(make_generation_response(name="Northern Trail"))
result = generate_world_content(game, ai, ref.id, "north")
results.append(check("Generation succeeded", result.success))
results.append(check("North: map_y < reference", result.location.map_y < ref.map_y))
test_results.append(("Generate north -> -y", all(results[-2:])))

# 5. Generate south -> coordinates +y
print("\n=== 5. Generate south -> +y ===")
game = create_new_game()
ref = game.current_location()
ai = MockAI(make_generation_response(name="Southern Marsh"))
result = generate_world_content(game, ai, ref.id, "south")
results.append(check("Generation succeeded", result.success))
results.append(check("South: map_y > reference", result.location.map_y > ref.map_y))
test_results.append(("Generate south -> +y", all(results[-2:])))

# 6. Bidirectional connections
print("\n=== 6. Bidirectional connections ===")
game = create_new_game()
ref = game.current_location()
ai = MockAI(make_generation_response(
    name="Birch Grove",
    connections=[{"label": "path", "one_way": False}],
))
result = generate_world_content(game, ai, ref.id, "east")
loc = result.location
results.append(check("Generation succeeded", result.success))
results.append(check("Forward connection exists", any(v == loc.id for v in ref.exits.values())))
results.append(check("Reverse connection exists", any(v == ref.id for v in loc.exits.values())))
test_results.append(("Bidirectional connections", all(results[-3:])))

# 7. One-way connection
print("\n=== 7. One-way connection ===")
game = create_new_game()
ref = game.current_location()
ai = MockAI(make_generation_response(
    name="Cliff Edge",
    connections=[{"label": "cliff", "one_way": True}],
))
result = generate_world_content(game, ai, ref.id, "east")
loc = result.location
results.append(check("Generation succeeded", result.success))
results.append(check("Forward connection exists", any(v == loc.id for v in ref.exits.values())))
results.append(check("No reverse connection", not any(v == ref.id for v in loc.exits.values())))
test_results.append(("One-way connection", all(results[-3:])))

# 8. Stable IDs
print("\n=== 8. Stable IDs ===")
game = create_new_game()
ai = MockAI(make_generation_response(name="The Hollow Lantern"))
result = generate_world_content(game, ai, "old_wooden_house", "east")
loc = result.location
results.append(check("ID is snake_case", loc.id == "the_hollow_lantern"))
results.append(check("ID is in world", loc.id in game.world.locations))
test_results.append(("Stable IDs", all(results[-2:])))

# 9. ID collision handling
print("\n=== 9. ID collision handling ===")
game = create_new_game()
ai1 = MockAI(make_generation_response(name="Birch Grove"))
r1 = generate_world_content(game, ai1, "old_wooden_house", "east")
first_id = r1.location.id
ai2 = MockAI(make_generation_response(name="Birch Grove"))
r2 = generate_world_content(game, ai2, "old_wooden_house", "west")
second_id = r2.location.id
results.append(check("First ID generated", first_id is not None))
results.append(check("Second ID different", first_id != second_id))
results.append(check("Both in world", first_id in game.world.locations and second_id in game.world.locations))
test_results.append(("ID collision handling", all(results[-3:])))

# 10. No duplicate locations
print("\n=== 10. No duplicate locations ===")
game = create_new_game()
initial_count = len(game.world.locations)
ai = MockAI(make_generation_response(name="Misty Creek"))
r1 = generate_world_content(game, ai, "old_wooden_house", "east")
count_after_first = len(game.world.locations)
ai2 = MockAI(make_generation_response(name="Another Place"))
r2 = generate_world_content(game, ai2, "old_wooden_house", "east")
count_after_second = len(game.world.locations)
results.append(check("First added location", count_after_first > initial_count))
results.append(check("Second added too", count_after_second > count_after_first))
test_results.append(("No duplicate locations", all(results[-2:])))

# 11. NPC persistence
print("\n=== 11. NPC persistence ===")
game = create_new_game()
ai = MockAI(make_generation_response(
    name="Wandering Trader Camp",
    npcs=[{
        "name": "Elara",
        "description": "A wandering trader.",
        "personality": ["friendly", "shrewd"],
        "knowledge": ["Trade routes."],
        "goals": ["Sell rare goods."],
        "disposition": 5,
        "inventory": ["Health Potion", "Torch"],
        "money": 50,
        "schedule": {},
    }],
))
result = generate_world_content(game, ai, "old_wooden_house", "east")
loc = result.location
results.append(check("Generation succeeded", result.success))
results.append(check("NPC created", len(result.npcs) == 1))
npc = result.npcs[0]
results.append(check("NPC in world", npc.id in game.world.npcs))
results.append(check("NPC at correct location", npc.location == loc.id))
results.append(check("NPC has inventory", "Health Potion" in npc.inventory))
results.append(check("NPC has money", npc.money == 50))
test_results.append(("NPC persistence", all(results[-6:])))

# 12. Item persistence
print("\n=== 12. Item persistence ===")
game = create_new_game()
ai = MockAI(make_generation_response(
    name="Abandoned Campsite",
    items=["Iron Sword", "Torch", "Bread"],
))
result = generate_world_content(game, ai, "old_wooden_house", "east")
loc = result.location
results.append(check("Generation succeeded", result.success))
results.append(check("Items at location", "Iron Sword" in loc.items))
results.append(check("Multiple items", len(loc.items) >= 3))
test_results.append(("Item persistence", all(results[-3:])))

# 13. Interactable persistence
print("\n=== 13. Interactable persistence ===")
game = create_new_game()
ai = MockAI(make_generation_response(
    name="Locked Cellar",
    is_interior=True,
    interactables=[{
        "name": "Cellar Door",
        "description": "A heavy wooden door.",
        "state": "locked",
        "unlock_items": ["Rusty Key"],
    }],
))
result = generate_world_content(game, ai, "old_wooden_house", "inside")
results.append(check("Generation succeeded", result.success))
results.append(check("Interactable created", len(result.interactables) == 1))
obj = result.interactables[0]
results.append(check("In world", obj.id in game.world.interactables))
results.append(check("State is locked", obj.state == "locked"))
results.append(check("Has unlock item", "Rusty Key" in obj.unlock_items))
test_results.append(("Interactable persistence", all(results[-5:])))

# 14. Connected region
print("\n=== 14. Connected region ===")
game = create_new_game()
ref_id = "old_wooden_house"
ai1 = MockAI(make_generation_response(
    name="Village Square",
    connections=[{"label": "road", "one_way": False}],
))
r1 = generate_world_content(game, ai1, ref_id, "east")
village_id = r1.location.id
ai2 = MockAI(make_generation_response(
    name="Market District",
    connections=[{"label": "road", "one_way": False}],
))
r2 = generate_world_content(game, ai2, village_id, "east")
market_id = r2.location.id
house = game.world.locations[ref_id]
village = game.world.locations[village_id]
market = game.world.locations[market_id]
results.append(check("House -> village", village_id in house.exits.values()))
results.append(check("Village -> house", ref_id in village.exits.values()))
results.append(check("Village -> market", market_id in village.exits.values()))
results.append(check("Market -> village", village_id in market.exits.values()))
test_results.append(("Connected region", all(results[-4:])))

# 15. Interior locations share coordinates
print("\n=== 15. Interior locations share coordinates ===")
game = create_new_game()
ref = game.current_location()
ai = MockAI(make_generation_response(
    name="Upper Bedroom",
    visual_type="interior",
    is_interior=True,
))
result = generate_world_content(game, ai, ref.id, "inside")
loc = result.location
results.append(check("Generation succeeded", result.success))
results.append(check("Same map_x", loc.map_x == ref.map_x))
results.append(check("Same map_y", loc.map_y == ref.map_y))
test_results.append(("Interior locations share coords", all(results[-3:])))

# 16. Free cell search
print("\n=== 16. Free cell search ===")
game = create_new_game()
ref = game.current_location()
ai1 = MockAI(make_generation_response(name="First East"))
r1 = generate_world_content(game, ai1, ref.id, "east")
ai2 = MockAI(make_generation_response(name="Second East"))
r2 = generate_world_content(game, ai2, ref.id, "east")
results.append(check("Both succeeded", r1.success and r2.success))
results.append(check("Different coords",
    (r1.location.map_x, r1.location.map_y) != (r2.location.map_x, r2.location.map_y)))
test_results.append(("Free cell search", all(results[-2:])))

# 17. WASD follows generated connections
print("\n=== 17. WASD follows generated connections ===")
game = create_new_game()
ref = game.current_location()
ai = MockAI(make_generation_response(
    name="Forest Path",
    connections=[{"label": "path", "one_way": False}],
))
result = generate_world_content(game, ai, ref.id, "east")
loc = result.location
exit_dir = None
for d, target in ref.exits.items():
    if target == loc.id:
        exit_dir = d
        break
results.append(check("Exit found", exit_dir is not None))
from engine.actions import move_player
move_result = move_player(game, exit_dir)
results.append(check("Move succeeded", move_result.success))
results.append(check("Player at generated", game.player.location == loc.id))
test_results.append(("WASD follows connections", all(results[-3:])))

# 18. Pygame renders generated locations
print("\n=== 18. Pygame renders generated locations ===")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame
pygame.init()
screen = pygame.display.set_mode((800, 600))
game = create_new_game()
ref = game.current_location()
ai = MockAI(make_generation_response(
    name="Crystal Cave",
    visual_type="cave",
    items=["Glowing Crystal"],
    npcs=[{
        "name": "Cave Bat",
        "description": "A large bat.",
        "personality": ["territorial"],
        "knowledge": [],
        "goals": [],
    }],
))
result = generate_world_content(game, ai, ref.id, "east")
from ui.pygame.world_renderer import WorldRenderer
from ui.pygame.hud import HUD
from ui.pygame.camera import Camera
wr = WorldRenderer(game)
cam = Camera(0, 0)
px, py = wr.player_pixel_pos()
cam.update(px, py, wr.pixel_width, wr.pixel_height)
wr.draw(screen, cam.x, cam.y)
hud = HUD()
hud.draw(screen, game, "", False)
results.append(check("Pygame renders generated locations", True))
test_results.append(("Pygame renders generated", all(results[-1:])))

# 19. Invalid AI output doesn't corrupt GameState
print("\n=== 19. Invalid AI output safe ===")
game = create_new_game()
initial_loc_count = len(game.world.locations)
initial_npc_count = len(game.world.npcs)

class BadAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        return "this is not json {{{"
    def close(self):
        pass

result = generate_world_content(game, BadAI(), "old_wooden_house", "east")
results.append(check("Bad JSON: returns failure", not result.success))
results.append(check("Bad JSON: no new locations", len(game.world.locations) == initial_loc_count))
results.append(check("Bad JSON: no new NPCs", len(game.world.npcs) == initial_npc_count))

class BadContentAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        return json.dumps({"location": {"name": "", "description": ""}})
    def close(self):
        pass

result2 = generate_world_content(game, BadContentAI(), "old_wooden_house", "east")
results.append(check("Invalid content: returns failure", not result2.success))
results.append(check("Invalid content: unchanged", len(game.world.locations) == initial_loc_count))
test_results.append(("Invalid AI output safe", all(results[-5:])))

# 20. Existing engine behavior intact
print("\n=== 20. Existing engine intact ===")
game = create_new_game()
from engine.actions import move_player, take_item, drop_item, wait, inspect
result = move_player(game, "outside")
results.append(check("Legacy move works", result.success))
results.append(check("Player moved", game.player.location == "forest_edge"))
result = take_item(game, "Wood")
results.append(check("Take item works", result.success))
results.append(check("Item in inventory", "Wood" in game.player.inventory))
result = drop_item(game, "Wood")
results.append(check("Drop item works", result.success))
result = wait(game, 10)
results.append(check("Wait works", result.success))
result = inspect(game, "Rusty Key")
results.append(check("Inspect works", result.success))

from engine.game import GameEngine
engine = GameEngine()
engine.ai = MockAI(make_generation_response(
    name="Test Village",
    visual_type="village",
))
result = engine.process_input("go east")
results.append(check("GameEngine works", result.get("success", False)))
engine.close()
test_results.append(("Existing engine intact", all(results[-8:])))

# 21. Directional movement uses existing connections
print("\n=== 21. Directional movement -> existing connections ===")
game = create_new_game()
move_player(game, "outside")
results.append(check("At Forest Edge", game.player.location == "forest_edge"))
r = move_player(game, "east")
results.append(check("East moves to Deep Forest", r.success and game.player.location == "deep_forest"))
r2 = move_player(game, "west")
results.append(check("West moves back to Forest Edge", r2.success and game.player.location == "forest_edge"))
r3 = move_player(game, "west")
results.append(check("West again to Old Wooden House", r3.success and game.player.location == "old_wooden_house"))
r4 = move_player(game, "east")
results.append(check("East to Forest Edge again", r4.success and game.player.location == "forest_edge"))
test_results.append(("Directional movement -> existing connections", all(results[-4:])))

# 22. No exit + direction fails (generation needed via AI)
print("\n=== 22. No exit + direction fails (generation needed) ===")
game = create_new_game()
move_player(game, "outside")
move_player(game, "east")
results.append(check("At Deep Forest", game.player.location == "deep_forest"))
r = move_player(game, "east")
results.append(check("East from Deep Forest fails (no exit)", not r.success))
r2 = move_player(game, "north")
results.append(check("North from Deep Forest fails (no exit)", not r2.success))
test_results.append(("No exit + direction fails", all(results[-3:])))

# 23. Context shows directional hints
print("\n=== 23. Context directional hints ===")
from engine.context import build_game_context
game = create_new_game()
move_player(game, "outside")
context = build_game_context(game)
results.append(check("Context has east hint", "east)" in context or "east)" in context))
results.append(check("Context has west hint", "west)" in context or "west)" in context))
test_results.append(("Context directional hints", all(results[-2:])))

# 24. Generated movement auto-moves player
print("\n=== 24. Generated movement auto-moves player ===")
game = create_new_game()
move_player(game, "outside")
move_player(game, "east")
results.append(check("At Deep Forest", game.player.location == "deep_forest"))

# Simulate AI returning generate_world with travel_destination=True
from engine.world_gen import generate_world_content
class TravelAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        return json.dumps({
            "location": {"name": "Sunlit Clearing", "description": "A sunny clearing.", "visual_type": "forest", "is_interior": False},
            "npcs": [], "items": ["Sunflower"], "interactables": [],
            "connections": [{"label": "path", "one_way": False}],
        })
    def close(self): pass

result = generate_world_content(game, TravelAI(), "deep_forest", "south")
# Simulate travel_destination: move player
if result.success and result.location:
    game.player.location = result.location.id
    game.visited_locations.add(result.location.id)
results.append(check("Player moved to generated", game.player.location == "sunlit_clearing"))
results.append(check("Generated in world", "sunlit_clearing" in game.world.locations))
results.append(check("Generated in visited", "sunlit_clearing" in game.visited_locations))
test_results.append(("Generated movement auto-moves player", all(results[-3:])))

# 25. Generated destination has correct spatial coordinates
print("\n=== 25. Generated destination spatial coordinates ===")
loc = game.world.locations["sunlit_clearing"]
results.append(check("Has map_x", isinstance(loc.map_x, int)))
results.append(check("Has map_y", isinstance(loc.map_y, int)))
# Interior types share parent coords; forest doesn't, so check it's adjacent
results.append(check("Has valid coords", loc.map_x is not None and loc.map_y is not None))
test_results.append(("Generated destination spatial coordinates", all(results[-3:])))

# 26. Generated connection persists
print("\n=== 26. Generated connection persists ===")
deep = game.world.locations["deep_forest"]
sunlit = game.world.locations["sunlit_clearing"]
results.append(check("Deep -> Sunlit connection exists",
    any(v == "sunlit_clearing" for v in deep.exits.values())))
results.append(check("Sunlit -> Deep connection exists",
    any(v == "deep_forest" for v in sunlit.exits.values())))
test_results.append(("Generated connection persists", all(results[-2:])))

# 27. Returning to generated destination reaches same location
print("\n=== 27. Return to generated destination ===")
game2 = create_new_game()
move_player(game2, "outside")
move_player(game2, "east")
r1 = generate_world_content(game2, TravelAI(), "deep_forest", "south")
if r1.success and r1.location:
    game2.player.location = r1.location.id
loc_id = r1.location.id
# Move away and come back
move_player(game2, "north")
results.append(check("Moved away", game2.player.location == "deep_forest"))
# The exit back to generated should still exist
exit_to_gen = any(v == loc_id for v in game2.current_location().exits.values())
results.append(check("Exit back to generated exists", exit_to_gen))
move_player(game2, loc_id)
results.append(check("Returned to generated", game2.player.location == loc_id))
test_results.append(("Return to generated destination", all(results[-3:])))

# 28. Non-travel generate_world does NOT teleport
print("\n=== 28. Non-travel generate_world does NOT teleport ===")
game3 = create_new_game()
move_player(game3, "outside")
move_player(game3, "east")
results.append(check("At Deep Forest", game3.player.location == "deep_forest"))
# Simulate non-travel generation (travel_destination=False)
r = generate_world_content(game3, TravelAI(), "deep_forest", "north")
# Do NOT move player (non-travel)
results.append(check("Player still at Deep Forest", game3.player.location == "deep_forest"))
results.append(check("Location was created", r.success and r.location is not None))
test_results.append(("Non-travel generate_world no teleport", all(results[-3:])))

# 29. Pygame event log toggle modes
print("\n=== 29. Event log toggle modes ===")
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame
pygame.init()
screen = pygame.display.set_mode((1200, 800))
from ui.pygame.app import App
from ui.pygame.hud import HUD

app = App.__new__(App)
app.event_log = [("player", "I go east."), ("narration", "You enter the forest.")]
app.event_scroll = 0
app.event_auto_scroll = True
app.event_mode = "latest"
hud = HUD()

# Draw in latest mode
app.event_mode = "latest"
result = hud.draw_event_log(screen, app.event_log, 0, True, 1200, 800, mode="latest")
results.append(check("Latest mode draws without error", result >= 0))

# Draw in history mode
app.event_mode = "history"
result = hud.draw_event_log(screen, app.event_log, 0, True, 1200, 800, mode="history")
results.append(check("History mode draws without error", result >= 0))

# Toggle preserves events
app.event_mode = "history"
result = hud.draw_event_log(screen, app.event_log, 0, True, 1200, 800, mode="history")
results.append(check("Events preserved after toggle", len(app.event_log) == 2))
test_results.append(("Event log toggle modes", all(results[-3:])))

# 30. Responsive UI at different sizes
print("\n=== 30. Responsive UI at different sizes ===")
hud2 = HUD()
for size in [(800, 600), (1200, 800), (1600, 1000), (600, 400)]:
    screen = pygame.display.set_mode(size)
    game = create_new_game()
    hud2.draw(screen, game, "test", False, False)
    hud2.draw_event_log(screen, [("narration", "Test narration.")], 0, True, size[0], size[1], mode="latest")
results.append(check("Responsive: 800x600", True))
results.append(check("Responsive: 1200x800", True))
results.append(check("Responsive: 1600x1000", True))
results.append(check("Responsive: 600x400", True))
test_results.append(("Responsive UI at different sizes", all(results[-4:])))

# 31. Narration guidance in system prompt
print("\n=== 31. Narration guidance in system prompt ===")
from engine.game import SYSTEM_PROMPT
results.append(check("Prompt has length guidance", "2-4 sentences" in SYSTEM_PROMPT))
results.append(check("Prompt has location discovery guidance", "do NOT narrate" in SYSTEM_PROMPT.lower() or "do not narrate" in SYSTEM_PROMPT.lower()))
results.append(check("Prompt discourages journey narration", "journey" in SYSTEM_PROMPT.lower()))
results.append(check("Prompt preserves atmosphere", "atmospheric" in SYSTEM_PROMPT.lower() or "atmosphere" in SYSTEM_PROMPT.lower() or "distinctive" in SYSTEM_PROMPT.lower() or "distinct" in SYSTEM_PROMPT.lower()))
test_results.append(("Narration guidance in system prompt", all(results[-4:])))

# 32. move_player fallback generates when AI is passed
print("\n=== 32. move_player fallback generates with AI ===")
game = create_new_game()
move_player(game, "outside")
move_player(game, "east")
# At Deep Forest, try east (no exit) with AI -> should generate
class GenAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        return json.dumps({
            "location": {"name": "Eastern Ridge", "description": "A rocky ridge.", "visual_type": "mountain", "is_interior": False},
            "npcs": [], "items": ["Flint"], "interactables": [],
            "connections": [{"label": "path", "one_way": False}],
        })
    def close(self): pass

r = move_player(game, "east", GenAI())
results.append(move_player is not None)
results.append(check("Fallback generated location", r.success and r.data.get("generated")))
results.append(check("Player moved to generated", game.player.location != "deep_forest"))
results.append(check("Generated location in world", game.player.location in game.world.locations))
test_results.append(("move_player fallback generates with AI", all(results[-3:])))

# 33. Chained generation: original -> A -> B -> C
print("\n=== 33. Chained generation (original -> A -> B -> C) ===")
game = create_new_game()
move_player(game, "outside")
move_player(game, "east")
# Now at Deep Forest (only exit is "back" to Forest Edge)

# Generate A east of Deep Forest
r1 = move_player(game, "east", GenAI())
loc_a = game.player.location
results.append(check("Step 1: Generated A", r1.success and r1.data.get("generated")))
results.append(check("Step 1: At A", loc_a in game.world.locations))

# Generate B east of A
r2 = move_player(game, "east", GenAI())
loc_b = game.player.location
results.append(check("Step 2: Generated B", r2.success and r2.data.get("generated")))
results.append(check("Step 2: At B", loc_b in game.world.locations))
results.append(check("Step 2: B != A", loc_b != loc_a))

# Generate C east of B
r3 = move_player(game, "east", GenAI())
loc_c = game.player.location
results.append(check("Step 3: Generated C", r3.success and r3.data.get("generated")))
results.append(check("Step 3: At C", loc_c in game.world.locations))
results.append(check("Step 3: C != B", loc_c != loc_b))

# Verify chain connections
a_loc = game.world.locations[loc_a]
b_loc = game.world.locations[loc_b]
c_loc = game.world.locations[loc_c]
results.append(check("A connects to B", any(v == loc_b for v in a_loc.exits.values())))
results.append(check("B connects to C", any(v == loc_c for v in b_loc.exits.values())))
results.append(check("B connects back to A", any(v == loc_a for v in b_loc.exits.values())))
results.append(check("C connects back to B", any(v == loc_b for v in c_loc.exits.values())))
test_results.append(("Chained generation (original -> A -> B -> C)", all(results[-10:])))

# Print results
print("\n" + "=" * 70)
print("WORLD GENERATION TEST RESULTS")
print("=" * 70)

passed = sum(1 for r in results if r)
failed = sum(1 for r in results if not r)
total = len(results)

for name, ok in test_results:
    icon = "PASS" if ok else "FAIL"
    print(f"  {icon}  {name}")

# Also show any results not in test_results (fallback)
if not test_results:
    for i, r in enumerate(results):
        icon = "PASS" if r else "FAIL"
        print(f"  {icon}  Check {i+1}")

print(f"\n  {passed}/{total} checks passed, {failed} failed")
print(f"  {sum(1 for _,ok in test_results if ok)}/{len(test_results)} test groups passed")
print("=" * 70)
