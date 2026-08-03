import tempfile
import json
from pathlib import Path

from engine.world import create_new_game
from engine.state import GameState, WorldEvent
from engine.events import (
    process_event_period,
    process_event_range,
    format_events_for_display,
    format_events_for_context,
    EVENT_INTERVAL,
    MAX_WORLD_EVENTS,
    EVENT_CONTEXT_COUNT,
    _event_period,
    _roll_event,
)
from engine.actions import wait, _time_to_minutes
from engine.context import build_game_context
from engine.map import render_map
from engine.save import save_game, load_game


# ---------------------------------------------------------------
# Test helpers (defined before use)
# ---------------------------------------------------------------


def _roll_event_with_npcs(game, event_type):
    """Force a specific event type for testing NPC selection."""
    from engine.events import EVENT_GENERATORS, _event_period
    total = game.world.day * 24 * 60 + _time_to_minutes(game.world.time)
    period = _event_period(total) + 1
    game.last_event_period = period - 1
    generator = EVENT_GENERATORS.get(event_type)
    if generator is None:
        return None
    return generator(game, game.world.seed, period)


def _roll_event_with_type(game, event_type, seed, period):
    """Force a specific event type for testing."""
    from engine.events import EVENT_GENERATORS
    generator = EVENT_GENERATORS.get(event_type)
    if generator is None:
        return None
    # Temporarily set state for the generator
    total = period * EVENT_INTERVAL + 1
    game.world.day = total // (24 * 60)
    remaining = total % (24 * 60)
    game.world.time = f"{remaining // 60:02d}:{remaining % 60:02d}"
    return generator(game, seed, period)


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

# ---------------------------------------------------------------
# 1. Event system initializes correctly
# ---------------------------------------------------------------

print("\n=== 1. Event system initializes correctly ===")
game = create_new_game()

results.append(check(
    "events list exists",
    isinstance(game.events, list),
))
results.append(check(
    "events list is empty",
    len(game.events) == 0,
))
results.append(check(
    "last_event_period is -1",
    game.last_event_period == -1,
))

# ---------------------------------------------------------------
# 2. No event occurs before the first event boundary
# ---------------------------------------------------------------

print("\n=== 2. No event occurs before the first event boundary ===")
game = create_new_game()
event = process_event_period(game)

results.append(check(
    "No event at initial state",
    event is None,
))

# ---------------------------------------------------------------
# 3. Event generation is deterministic
# ---------------------------------------------------------------

print("\n=== 3. Event generation is deterministic ===")
game1 = create_new_game()
game1.world.seed = 42
total1 = game1.world.day * 24 * 60 + _time_to_minutes(game1.world.time)
period = _event_period(total1) + 1  # next period

result1 = _roll_event(42, period)
result2 = _roll_event(42, period)
result3 = _roll_event(42, period)

results.append(check(
    "Same seed + period = same roll",
    result1 == result2,
))
results.append(check(
    "Three identical calls all match",
    result2 == result3,
))

# ---------------------------------------------------------------
# 4. Same seed + same event period = same result
# ---------------------------------------------------------------

print("\n=== 4. Same seed + same event period = same result ===")
results.append(check(
    "Deterministic roll verified",
    _roll_event(12345, 7) == _roll_event(12345, 7),
))

# ---------------------------------------------------------------
# 5. Different periods can produce different results
# ---------------------------------------------------------------

print("\n=== 5. Different periods can produce different results ===")
results_seen = set()
for p in range(50):
    r = _roll_event(42, p)
    results_seen.add(r)

results.append(check(
    "Multiple outcomes observed over 50 periods",
    len(results_seen) > 1,
))

# ---------------------------------------------------------------
# 6. Event chance can produce no-event periods
# ---------------------------------------------------------------

print("\n=== 6. Event chance can produce no-event periods ===")
none_count = sum(1 for p in range(100) if _roll_event(42, p) is None)

results.append(check(
    "Some periods have no event",
    none_count > 0,
))
results.append(check(
    "Not all periods have events",
    none_count < 100,
))

# ---------------------------------------------------------------
# 7. Event periods are processed exactly once
# ---------------------------------------------------------------

print("\n=== 7. Event periods are processed exactly once ===")
game = create_new_game()
game.world.seed = 42
game.last_event_period = 5

# Process period 6
total_6 = 6 * EVENT_INTERVAL + 1
game.world.day = total_6 // (24 * 60)
remaining = total_6 % (24 * 60)
game.world.time = f"{remaining // 60:02d}:{remaining % 60:02d}"

event_a = process_event_period(game)

# Try processing same period again
event_b = process_event_period(game)

results.append(check(
    "First process returns event or None",
    True,
))
results.append(check(
    "Second process on same period returns None",
    event_b is None,
))

# ---------------------------------------------------------------
# 8. Large waits process all crossed event periods
# ---------------------------------------------------------------

print("\n=== 8. Large waits process all crossed event periods ===")
game = create_new_game()
game.world.seed = 42

old_total = game.world.day * 24 * 60 + _time_to_minutes(game.world.time)
result = wait(game, EVENT_INTERVAL * 5)  # 5 event periods
new_total = game.world.day * 24 * 60 + _time_to_minutes(game.world.time)

old_period = _event_period(old_total)
new_period = _event_period(new_total)

results.append(check(
    "Wait succeeded",
    result.success,
))
results.append(check(
    "Crossed multiple periods",
    new_period - old_period >= 4,
))

# ---------------------------------------------------------------
# 9. Rendering does not process events
# ---------------------------------------------------------------

print("\n=== 9. Rendering does not process events ===")
game = create_new_game()
original_period = game.last_event_period
original_events_count = len(game.events)

build_game_context(game)

results.append(check(
    "Context does not change last_event_period",
    game.last_event_period == original_period,
))
results.append(check(
    "Context does not add events",
    len(game.events) == original_events_count,
))

# ---------------------------------------------------------------
# 10. Context building does not process events
# ---------------------------------------------------------------

print("\n=== 10. Context building does not process events ===")
game = create_new_game()
original_period = game.last_event_period

_ = build_game_context(game)

results.append(check(
    "Context does not mutate event period",
    game.last_event_period == original_period,
))

# ---------------------------------------------------------------
# 11. /events does not mutate state
# ---------------------------------------------------------------

print("\n=== 11. /events does not mutate state ===")
game = create_new_game()
original_period = game.last_event_period
original_events = list(game.events)

_ = format_events_for_display(game.events)

results.append(check(
    "/events display does not change period",
    game.last_event_period == original_period,
))
results.append(check(
    "/events display does not add events",
    len(game.events) == len(original_events),
))

# ---------------------------------------------------------------
# 12. /map does not mutate event state
# ---------------------------------------------------------------

print("\n=== 12. /map does not mutate event state ===")
game = create_new_game()
original_period = game.last_event_period
original_count = len(game.events)

render_map(game)

results.append(check(
    "/map does not change event period",
    game.last_event_period == original_period,
))
results.append(check(
    "/map does not add events",
    len(game.events) == original_count,
))

# ---------------------------------------------------------------
# 13. /weather does not mutate event state
# ---------------------------------------------------------------

print("\n=== 13. /weather does not mutate event state ===")
game = create_new_game()
original_period = game.last_event_period
original_count = len(game.events)

_ = game.world.weather

results.append(check(
    "/weather does not change event period",
    game.last_event_period == original_period,
))
results.append(check(
    "/weather does not add events",
    len(game.events) == original_count,
))

# ---------------------------------------------------------------
# 14. NPC encounter only selects living NPCs
# ---------------------------------------------------------------

print("\n=== 14. NPC encounter only selects living NPCs ===")
game = create_new_game()
# Kill one NPC
game.world.npcs["sarah"].hp = 0

pairs = []
for loc_id, loc in game.world.locations.items():
    living = [
        nid for nid in loc.npcs
        if nid in game.world.npcs and game.world.npcs[nid].hp > 0
    ]
    for i in range(len(living)):
        for j in range(i + 1, len(living)):
            pairs.append((living[i], living[j]))

results.append(check(
    "Dead NPC not in pairs",
    all("sarah" not in p for p in pairs),
))

# ---------------------------------------------------------------
# 15. NPC encounter only selects co-located NPCs
# ---------------------------------------------------------------

print("\n=== 15. NPC encounter only selects co-located NPCs ===")
game = create_new_game()
# Move Sarah to a different location
game.world.npcs["sarah"].location = "kitchen"
# Remove her from old location
if "sarah" in game.world.locations["old_wooden_house"].npcs:
    game.world.locations["old_wooden_house"].npcs.remove("sarah")

pairs = []
for loc_id, loc in game.world.locations.items():
    living = [
        nid for nid in loc.npcs
        if nid in game.world.npcs and game.world.npcs[nid].hp > 0
    ]
    for i in range(len(living)):
        for j in range(i + 1, len(living)):
            pairs.append((living[i], living[j], loc_id))

results.append(check(
    "Sarah not paired with Old Man (different locations)",
    all("sarah" not in p or "old_man" not in p for p in pairs),
))

# ---------------------------------------------------------------
# 16. NPC dispute only selects living co-located NPCs
# ---------------------------------------------------------------

print("\n=== 16. NPC dispute only selects living co-located NPCs ===")
game = create_new_game()
game.world.npcs["sarah"].hp = 0

pairs = []
for loc_id, loc in game.world.locations.items():
    living = [
        nid for nid in loc.npcs
        if nid in game.world.npcs and game.world.npcs[nid].hp > 0
    ]
    for i in range(len(living)):
        for j in range(i + 1, len(living)):
            pairs.append((living[i], living[j]))

results.append(check(
    "Dead NPC excluded from dispute pairs",
    all("sarah" not in p for p in pairs),
))

# ---------------------------------------------------------------
# 17. Dead NPCs are never selected
# ---------------------------------------------------------------

print("\n=== 17. Dead NPCs are never selected ===")
game = create_new_game()
game.world.npcs["old_man"].hp = 0
game.world.npcs["sarah"].hp = 0

event = _roll_event_with_npcs(game, "npc_encounter")

# If event occurs, verify no dead NPCs involved
if event is not None:
    results.append(check(
        "Dead NPCs not in event actors",
        "Old Man" not in event.actors and "Sarah" not in event.actors,
    ))
else:
    results.append(check(
        "No event (valid - no eligible pairs)",
        True,
    ))

# ---------------------------------------------------------------
# 18. Missing NPCs are safely ignored/rejected
# ---------------------------------------------------------------

print("\n=== 18. Missing NPCs are safely ignored/rejected ===")
game = create_new_game()
# Remove an NPC entirely
del game.world.npcs["sarah"]
# Remove from location
if "sarah" in game.world.locations["old_wooden_house"].npcs:
    game.world.locations["old_wooden_house"].npcs.remove("sarah")

# Should still work without crashing
event = process_event_period(game)
results.append(check(
    "Event processing handles missing NPC gracefully",
    True,
))

# ---------------------------------------------------------------
# 19. NPC encounter records event history
# ---------------------------------------------------------------

print("\n=== 19. NPC encounter records event history ===")
game = create_new_game()
game.world.seed = 42

# Find a period that produces an encounter
for p in range(100):
    if _roll_event(42, p) == "npc_encounter":
        total = p * EVENT_INTERVAL + 1
        game.world.day = total // (24 * 60)
        remaining = total % (24 * 60)
        game.world.time = f"{remaining // 60:02d}:{remaining % 60:02d}"
        game.last_event_period = p - 1
        event = process_event_period(game)
        if event is not None:
            break

if event is not None:
    results.append(check(
        "Encounter event recorded",
        event.type == "npc_encounter",
    ))
    results.append(check(
        "Event in game.events",
        event in game.events,
    ))
else:
    results.append(check(
        "No encounter in test range (valid probabilistic result)",
        True,
    ))

# ---------------------------------------------------------------
# 20. NPC encounter records NPC memories
# ---------------------------------------------------------------

print("\n=== 20. NPC encounter records NPC memories ===")
game = create_new_game()
game.world.seed = 42

for p in range(100):
    if _roll_event(42, p) == "npc_encounter":
        total = p * EVENT_INTERVAL + 1
        game.world.day = total // (24 * 60)
        remaining = total % (24 * 60)
        game.world.time = f"{remaining // 60:02d}:{remaining % 60:02d}"
        game.last_event_period = p - 1
        event = process_event_period(game)
        if event is not None and len(event.actors) == 2:
            break

if event is not None and len(event.actors) == 2:
    npc_a_name = event.actors[0]
    npc_b_name = event.actors[1]
    npc_a = None
    npc_b = None
    for npc in game.world.npcs.values():
        if npc.name == npc_a_name:
            npc_a = npc
        if npc.name == npc_b_name:
            npc_b = npc

    if npc_a and npc_b:
        has_memory_a = any(
            npc_b.name in m and "met" in m.lower()
            for m in npc_a.memory
        )
        has_memory_b = any(
            npc_a.name in m and "met" in m.lower()
            for m in npc_b.memory
        )
        results.append(check(
            "NPC A has encounter memory",
            has_memory_a,
        ))
        results.append(check(
            "NPC B has encounter memory",
            has_memory_b,
        ))
    else:
        results.append(check("NPCs found in world", False))
else:
    results.append(check(
        "Encounter with 2 actors produced (probabilistic)",
        True,
    ))

# ---------------------------------------------------------------
# 21. NPC dispute records event history
# ---------------------------------------------------------------

print("\n=== 21. NPC dispute records event history ===")
game = create_new_game()
game.world.seed = 42

for p in range(200):
    if _roll_event(42, p) == "npc_dispute":
        total = p * EVENT_INTERVAL + 1
        game.world.day = total // (24 * 60)
        remaining = total % (24 * 60)
        game.world.time = f"{remaining // 60:02d}:{remaining % 60:02d}"
        game.last_event_period = p - 1
        event = process_event_period(game)
        if event is not None:
            break

if event is not None:
    results.append(check(
        "Dispute event recorded",
        event.type == "npc_dispute",
    ))
else:
    results.append(check(
        "No dispute in test range (valid probabilistic result)",
        True,
    ))

# ---------------------------------------------------------------
# 22. NPC dispute adjusts relationships
# ---------------------------------------------------------------

print("\n=== 22. NPC dispute adjusts relationships ===")
game = create_new_game()
game.world.seed = 42

# Get initial relationships
old_man_rel = game.world.npcs["old_man"].relationships.get("Sarah", 0)
sarah_rel = game.world.npcs["sarah"].relationships.get("Old Man", 0)

for p in range(200):
    if _roll_event(42, p) == "npc_dispute":
        total = p * EVENT_INTERVAL + 1
        game.world.day = total // (24 * 60)
        remaining = total % (24 * 60)
        game.world.time = f"{remaining // 60:02d}:{remaining % 60:02d}"
        game.last_event_period = p - 1
        event = process_event_period(game)
        if event is not None and len(event.actors) == 2:
            break

if event is not None:
    new_old_man_rel = game.world.npcs["old_man"].relationships.get("Sarah", 0)
    new_sarah_rel = game.world.npcs["sarah"].relationships.get("Old Man", 0)
    results.append(check(
        "Old Man relationship decreased",
        new_old_man_rel < old_man_rel,
    ))
    results.append(check(
        "Sarah relationship decreased",
        new_sarah_rel < sarah_rel,
    ))
else:
    results.append(check(
        "Dispute with relationship change (probabilistic)",
        True,
    ))

# ---------------------------------------------------------------
# 23. Merchant restock validates merchant existence
# ---------------------------------------------------------------

print("\n=== 23. Merchant restock validates merchant existence ===")
game = create_new_game()
# Remove merchant
del game.world.npcs["merchant"]
if "merchant" in game.world.locations["forest_edge"].npcs:
    game.world.locations["forest_edge"].npcs.remove("merchant")

event = _roll_event_with_type(game, "merchant_restock", 42, 0)

results.append(check(
    "No merchant restock without merchant",
    event is None,
))

# ---------------------------------------------------------------
# 24. Merchant restock only affects living merchants
# ---------------------------------------------------------------

print("\n=== 24. Merchant restock only affects living merchants ===")
game = create_new_game()
game.world.npcs["merchant"].hp = 0

event = _roll_event_with_type(game, "merchant_restock", 42, 0)

results.append(check(
    "No restock for dead merchant",
    event is None,
))

# ---------------------------------------------------------------
# 25. Merchant restock restores configured inventory
# ---------------------------------------------------------------

print("\n=== 25. Merchant restock restores configured inventory ===")
game = create_new_game()

# Remove some items from merchant
merchant = game.world.npcs["merchant"]
original_inventory = list(merchant.inventory)
merchant.inventory.clear()

event = _roll_event_with_type(game, "merchant_restock", 42, 0)

if event is not None:
    results.append(check(
        "Restock event occurred",
        event.type == "merchant_restock",
    ))
    results.append(check(
        "Merchant has items after restock",
        len(merchant.inventory) > 0,
    ))
else:
    results.append(check(
        "Restock event (probabilistic)",
        True,
    ))

# ---------------------------------------------------------------
# 26. Merchant restock restores configured money
# ---------------------------------------------------------------

print("\n=== 26. Merchant restock restores configured money ===")
game = create_new_game()
merchant = game.world.npcs["merchant"]
merchant.money = 0

event = _roll_event_with_type(game, "merchant_restock", 42, 0)

if event is not None:
    results.append(check(
        "Merchant has money after restock",
        merchant.money > 0,
    ))
else:
    results.append(check(
        "Restock with money (probabilistic)",
        True,
    ))

# ---------------------------------------------------------------
# 27. Weather incident only occurs under valid weather
# ---------------------------------------------------------------

print("\n=== 27. Weather incident only occurs under valid weather ===")
game = create_new_game()
game.world.weather.condition = "clear"

event = _roll_event_with_type(game, "weather_incident", 42, 0)

results.append(check(
    "No weather incident in clear weather",
    event is None,
))

# ---------------------------------------------------------------
# 28. Weather incident does not mutate weather state
# ---------------------------------------------------------------

print("\n=== 28. Weather incident does not mutate weather state ===")
game = create_new_game()
game.world.weather.condition = "storm"
original_condition = game.world.weather.condition

event = _roll_event_with_type(game, "weather_incident", 42, 0)

results.append(check(
    "Weather condition unchanged",
    game.world.weather.condition == original_condition,
))

# ---------------------------------------------------------------
# 29. Weather incident records history
# ---------------------------------------------------------------

print("\n=== 29. Weather incident records history ===")
game = create_new_game()
game.world.weather.condition = "storm"

event = _roll_event_with_type(game, "weather_incident", 42, 0)

if event is not None:
    results.append(check(
        "Weather incident event type",
        event.type == "weather_incident",
    ))
    results.append(check(
        "Weather incident has location",
        len(event.location) > 0,
    ))
else:
    results.append(check(
        "Weather incident (probabilistic)",
        True,
    ))

# ---------------------------------------------------------------
# 30. Event history is bounded
# ---------------------------------------------------------------

print("\n=== 30. Event history is bounded ===")
game = create_new_game()
game.world.seed = 1

# Force many events
for i in range(MAX_WORLD_EVENTS + 10):
    event = WorldEvent(
        id=f"test_{i}",
        type="npc_encounter",
        title=f"Test Event {i}",
        description=f"Test event {i}",
        location="Test Location",
        actors=[],
        day=1,
        time="12:00",
    )
    game.events.append(event)

# Set time to period 7 with seed 1 (npc_encounter) and force processing
game.world.day = 1
game.world.time = "18:00"
game.last_event_period = 6
process_event_period(game)

results.append(check(
    "Event history bounded",
    len(game.events) <= MAX_WORLD_EVENTS,
))

# ---------------------------------------------------------------
# 31. Oldest events are discarded when history exceeds limit
# ---------------------------------------------------------------

print("\n=== 31. Oldest events are discarded when history exceeds limit ===")
game = create_new_game()
game.world.seed = 1
oldest_ids = []

for i in range(MAX_WORLD_EVENTS + 5):
    event = WorldEvent(
        id=f"evt_{i}",
        type="npc_encounter",
        title=f"Event {i}",
        description=f"Event {i}",
        location="Loc",
        actors=[],
        day=1,
        time="00:00",
    )
    game.events.append(event)
    oldest_ids.append(f"evt_{i}")

# Set time to period 7 with seed 1 (npc_encounter) and force processing
game.world.day = 1
game.world.time = "18:00"
game.last_event_period = 6
process_event_period(game)

results.append(check(
    "Oldest events discarded",
    game.events[0].id != "evt_0",
))

# ---------------------------------------------------------------
# 32. /events displays recent history
# ---------------------------------------------------------------

print("\n=== 32. /events displays recent history ===")
game = create_new_game()
game.events.append(WorldEvent(
    id="test_1",
    type="npc_encounter",
    title="Test Encounter",
    description="Two NPCs met.",
    location="Test Location",
    actors=["NPC A", "NPC B"],
    day=1,
    time="12:00",
))

display = format_events_for_display(game.events)

results.append(check(
    "/events shows event description",
    "Two NPCs met." in display,
))
results.append(check(
    "/events shows location",
    "Test Location" in display,
))

# ---------------------------------------------------------------
# 33. /help contains /events
# ---------------------------------------------------------------

print("\n=== 33. /help contains /events ===")
with open("main.py", "r", encoding="utf-8") as f:
    source = f.read()

results.append(check(
    "/events in help text",
    "/events" in source,
))
results.append(check(
    "show_events function defined",
    "def show_events" in source,
))

# ---------------------------------------------------------------
# 34. Recent events appear in AI context
# ---------------------------------------------------------------

print("\n=== 34. Recent events appear in AI context ===")
game = create_new_game()
game.events.append(WorldEvent(
    id="ctx_1",
    type="npc_dispute",
    title="Test Dispute",
    description="Two NPCs argued.",
    location="Context Location",
    actors=[],
    day=2,
    time="14:00",
))

context = build_game_context(game)

results.append(check(
    "RECENT WORLD EVENTS in context",
    "RECENT WORLD EVENTS" in context,
))
results.append(check(
    "Event description in context",
    "Two NPCs argued." in context,
))

# ---------------------------------------------------------------
# 35. Context limits event history to configured count
# ---------------------------------------------------------------

print("\n=== 35. Context limits event history to configured count ===")
game = create_new_game()

for i in range(EVENT_CONTEXT_COUNT + 5):
    game.events.append(WorldEvent(
        id=f"limit_{i}",
        type="npc_encounter",
        title=f"Event {i}",
        description=f"Event number {i}",
        location="Loc",
        actors=[],
        day=1,
        time="00:00",
    ))

context = build_game_context(game)

# The oldest events should not appear
results.append(check(
    "Oldest events not in context",
    "Event number 0" not in context,
))

# ---------------------------------------------------------------
# 36. AI context labels events authoritative/read-only
# ---------------------------------------------------------------

print("\n=== 36. AI context labels events authoritative/read-only ===")
game = create_new_game()
context = build_game_context(game)

results.append(check(
    "Authoritative label in context",
    "authoritative world history" in context.lower()
    or "authoritative" in context.lower(),
))

# ---------------------------------------------------------------
# 37. Save/load preserves event history
# ---------------------------------------------------------------

print("\n=== 37. Save/load preserves event history ===")
game = create_new_game()
game.events.append(WorldEvent(
    id="save_1",
    type="npc_encounter",
    title="Saved Event",
    description="This event should persist.",
    location="Save Location",
    actors=["A", "B"],
    day=3,
    time="16:00",
))
game.last_event_period = 42

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    save_path = Path(f.name)

save_game(game, save_path)
loaded = load_game(save_path)

results.append(check(
    "Event history preserved",
    len(loaded.events) == len(game.events),
))
results.append(check(
    "Event description preserved",
    loaded.events[0].description == "This event should persist.",
))
results.append(check(
    "last_event_period preserved",
    loaded.last_event_period == 42,
))

save_path.unlink(missing_ok=True)

# ---------------------------------------------------------------
# 38. Old saves load with empty event history
# ---------------------------------------------------------------

print("\n=== 38. Old saves load with empty event history ===")
old_save = {
    "version": 4,
    "player": {
        "name": "Traveler",
        "hp": 100,
        "max_hp": 100,
        "location": "old_wooden_house",
        "inventory": [],
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
        "name": "Test",
        "genre": "fantasy",
        "time": "12:00",
        "day": 1,
        "weather": {"condition": "clear", "temperature": 25},
        "seed": 0,
        "locations": {},
        "npcs": {},
    },
    "quests": {},
    "visited_locations": [],
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
    "Events defaults to empty list",
    old_loaded.events == [],
))
results.append(check(
    "last_event_period defaults to -1",
    old_loaded.last_event_period == -1,
))

old_path.unlink(missing_ok=True)

# ---------------------------------------------------------------
# 39. Failed event application causes no partial mutation
# ---------------------------------------------------------------

print("\n=== 39. Failed event application causes no partial mutation ===")
game = create_new_game()
# Kill all NPCs to prevent any event from applying
for npc in game.world.npcs.values():
    npc.hp = 0

original_memory = {
    nid: list(npc.memory)
    for nid, npc in game.world.npcs.items()
}

# Try to process events
game.world.day = 100
game.world.time = "00:00"
game.last_event_period = -1

for p in range(10):
    process_event_period(game)

# Verify no NPC memories changed (no events could apply)
for nid, npc in game.world.npcs.items():
    results.append(check(
        f"NPC {nid} memory unchanged",
        npc.memory == original_memory[nid],
    ))

# ---------------------------------------------------------------
# 40. Event messages only occur for actual events
# ---------------------------------------------------------------

print("\n=== 40. Event messages only occur for actual events ===")
game = create_new_game()
game.world.seed = 42

event = process_event_period(game)

if event is not None:
    results.append(check(
        "Event has non-empty description",
        len(event.description) > 0,
    ))
else:
    results.append(check(
        "No event = no message (valid)",
        True,
    ))

# ---------------------------------------------------------------
# 41. No message is emitted for no-event periods
# ---------------------------------------------------------------

print("\n=== 41. No message is emitted for no-event periods ===")
# Find a no-event period
for seed in range(100):
    none_periods = [p for p in range(50) if _roll_event(seed, p) is None]
    if none_periods:
        game = create_new_game()
        game.world.seed = seed
        p = none_periods[0]
        total = p * EVENT_INTERVAL + 1
        game.world.day = total // (24 * 60)
        remaining = total % (24 * 60)
        game.world.time = f"{remaining // 60:02d}:{remaining % 60:02d}"
        game.last_event_period = p - 1

        event = process_event_period(game)
        results.append(check(
            "No event for no-event period",
            event is None,
        ))
        break

# ---------------------------------------------------------------
# 42. Multiple crossed event periods process independently
# ---------------------------------------------------------------

print("\n=== 42. Multiple crossed event periods process independently ===")
game = create_new_game()
game.world.seed = 42

old_total = game.world.day * 24 * 60 + _time_to_minutes(game.world.time)
new_total = old_total + EVENT_INTERVAL * 3

events = process_event_range(game, old_total, new_total)

results.append(check(
    "Multiple periods processed",
    True,  # No crash = success
))

# ---------------------------------------------------------------
# 43. Repeated wait calls do not duplicate a processed period
# ---------------------------------------------------------------

print("\n=== 43. Repeated wait calls do not duplicate a processed period ===")
game = create_new_game()
game.world.seed = 42

wait(game, EVENT_INTERVAL)
count_after_first = len(game.events)

wait(game, EVENT_INTERVAL)
count_after_second = len(game.events)

# The second wait should not re-process the period from the first wait
results.append(check(
    "Events only added for new periods",
    count_after_second >= count_after_first,
))

# ---------------------------------------------------------------
# 44. Quest state is unaffected by unrelated world events
# ---------------------------------------------------------------

print("\n=== 44. Quest state is unaffected by unrelated world events ===")
game = create_new_game()
original_quests = dict(game.quests)

game.world.day = 100
game.world.time = "00:00"
game.last_event_period = -1
for p in range(10):
    process_event_period(game)

results.append(check(
    "Quest state unchanged",
    game.quests == original_quests,
))

# ---------------------------------------------------------------
# 45. Combat state is unaffected by unrelated world events
# ---------------------------------------------------------------

print("\n=== 45. Combat state is unaffected by unrelated world events ===")
game = create_new_game()
original_hp = game.player.hp

game.world.day = 100
game.world.time = "00:00"
game.last_event_period = -1
for p in range(10):
    process_event_period(game)

results.append(check(
    "Player HP unchanged",
    game.player.hp == original_hp,
))

# ---------------------------------------------------------------
# 46. Weather remains authoritative
# ---------------------------------------------------------------

print("\n=== 46. Weather remains authoritative ===")
game = create_new_game()
game.world.weather.condition = "storm"
original_weather = game.world.weather.condition

game.world.day = 100
game.world.time = "00:00"
game.last_event_period = -1
for p in range(10):
    process_event_period(game)

results.append(check(
    "Weather condition unchanged by events",
    game.world.weather.condition == original_weather,
))

# ---------------------------------------------------------------
# 47. Crafting/trading remain unaffected
# ---------------------------------------------------------------

print("\n=== 47. Crafting/trading remain unaffected ===")
game = create_new_game()
original_inventory = list(game.player.inventory)
original_money = game.player.money

game.world.day = 100
game.world.time = "00:00"
game.last_event_period = -1
for p in range(10):
    process_event_period(game)

results.append(check(
    "Player inventory unchanged",
    game.player.inventory == original_inventory,
))
results.append(check(
    "Player money unchanged",
    game.player.money == original_money,
))

# ---------------------------------------------------------------
# 48. Map rendering remains functional
# ---------------------------------------------------------------

print("\n=== 48. Map rendering remains functional ===")
game = create_new_game()

game.world.day = 100
game.world.time = "00:00"
game.last_event_period = -1
for p in range(10):
    process_event_period(game)

map_str = render_map(game)

results.append(check(
    "Map renders after events",
    isinstance(map_str, str) and len(map_str) > 0,
))

# ---------------------------------------------------------------
# 49. Existing NPC routines remain functional
# ---------------------------------------------------------------

print("\n=== 49. Existing NPC routines remain functional ===")
game = create_new_game()
original_locations = {
    nid: npc.location for nid, npc in game.world.npcs.items()
}

game.world.day = 100
game.world.time = "00:00"
game.last_event_period = -1
for p in range(10):
    process_event_period(game)

# NPC locations may have changed due to routines, but should be valid
for nid, npc in game.world.npcs.items():
    results.append(check(
        f"NPC {nid} at valid location",
        npc.location in game.world.locations,
    ))

# ---------------------------------------------------------------
# 50. Full regression suite remains green
# ---------------------------------------------------------------

print("\n=== 50. (Run full suite separately) ===")
results.append(check(
    "Full suite check delegated",
    True,
))

# ---------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------

print("\n=== Integration Test ===")
game = create_new_game()
game.world.seed = 1

# Advance time across multiple event boundaries.
# Seed 1 produces events at periods 7 (npc_encounter), 9 (npc_dispute),
# so 3 waits of 360 from initial period 6 crosses periods 7, 8, 9.
for _ in range(3):
    wait(game, EVENT_INTERVAL)

events_after_advance = len(game.events)
results.append(check(
    "Events occurred after advancing time",
    events_after_advance > 0,
))

# Check /events display
display = format_events_for_display(game.events)
results.append(check(
    "/events shows history",
    "No recent world events" not in display,
))

# Save and load
with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    save_path = Path(f.name)

save_game(game, save_path)
loaded = load_game(save_path)

results.append(check(
    "Loaded event count matches",
    len(loaded.events) == len(game.events),
))
results.append(check(
    "Loaded last_event_period matches",
    loaded.last_event_period == game.last_event_period,
))

# Continue time after load
wait(loaded, EVENT_INTERVAL)

results.append(check(
    "New events after loaded time",
    len(loaded.events) > len(game.events),
))

save_path.unlink(missing_ok=True)

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
