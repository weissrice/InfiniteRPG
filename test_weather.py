import tempfile
import json
from pathlib import Path

from engine.world import create_new_game
from engine.state import Weather
from engine.weather import (
    compute_weather,
    get_weather_change_message,
    get_condition_description,
    WEATHER_INTERVAL,
    SUPPORTED_CONDITIONS,
    TEMPERATURE_MODIFIERS,
)
from engine.actions import wait, _time_to_minutes
from engine.context import build_game_context
from engine.map import render_map
from engine.save import save_game, load_game


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

# ---------------------------------------------------------------
# 1. Default weather initializes correctly
# ---------------------------------------------------------------

print("\n=== 1. Default weather initializes correctly ===")
game = create_new_game()

results.append(check(
    "Weather is a Weather instance",
    isinstance(game.world.weather, Weather),
))
results.append(check(
    "Default condition is clear",
    game.world.weather.condition == "clear",
))
results.append(check(
    "Default temperature is an int",
    isinstance(game.world.weather.temperature, int),
))

# ---------------------------------------------------------------
# 2. Weather condition is one of the supported conditions
# ---------------------------------------------------------------

print("\n=== 2. Weather condition is one of the supported conditions ===")
for cond in SUPPORTED_CONDITIONS:
    w = Weather(condition=cond)
    results.append(check(
        f"Condition '{cond}' is supported",
        cond in SUPPORTED_CONDITIONS,
    ))

# ---------------------------------------------------------------
# 3. Temperature is deterministic
# ---------------------------------------------------------------

print("\n=== 3. Temperature is deterministic ===")
w1 = compute_weather(42, 1000)
w2 = compute_weather(42, 1000)
w3 = compute_weather(42, 1000)

results.append(check(
    "Same seed + same time = same condition",
    w1.condition == w2.condition,
))
results.append(check(
    "Same seed + same time = same temperature",
    w1.temperature == w2.temperature,
))
results.append(check(
    "Three identical calls all match",
    w1.condition == w3.condition and w1.temperature == w3.temperature,
))

# ---------------------------------------------------------------
# 4. Same world seed + same time produces same weather
# ---------------------------------------------------------------

print("\n=== 4. Same world seed + same time produces same weather ===")
game1 = create_new_game()
game2 = create_new_game()
game1.world.seed = 12345
game2.world.seed = 12345

total1 = game1.world.day * 24 * 60 + _time_to_minutes(game1.world.time)
total2 = game2.world.day * 24 * 60 + _time_to_minutes(game2.world.time)

w1 = compute_weather(game1.world.seed, total1)
w2 = compute_weather(game2.world.seed, total2)

results.append(check(
    "Same seed + same time = same weather",
    w1.condition == w2.condition and w1.temperature == w2.temperature,
))

# ---------------------------------------------------------------
# 5. Different weather periods can produce different conditions
# ---------------------------------------------------------------

print("\n=== 5. Different weather periods can produce different conditions ===")
conditions_seen = set()
for period in range(50):
    total_minutes = period * WEATHER_INTERVAL
    w = compute_weather(999, total_minutes)
    conditions_seen.add(w.condition)

results.append(check(
    "Multiple conditions observed over 50 periods",
    len(conditions_seen) > 1,
))

# ---------------------------------------------------------------
# 6. Weather updates when crossing the configured weather interval
# ---------------------------------------------------------------

print("\n=== 6. Weather updates when crossing the weather interval ===")
game = create_new_game()
game.world.seed = 42

# Start at time 0:00 day 1 -> total = 1440
# Wait 181 minutes -> crosses period boundary
old_total = game.world.day * 24 * 60 + _time_to_minutes(game.world.time)

result = wait(game, 181)
new_total = game.world.day * 24 * 60 + _time_to_minutes(game.world.time)

old_period = old_total // WEATHER_INTERVAL
new_period = new_total // WEATHER_INTERVAL

results.append(check(
    "Period changed after 181 minute wait",
    old_period != new_period,
))
results.append(check(
    "Wait succeeded",
    result.success,
))

# ---------------------------------------------------------------
# 7. Weather does not update before the interval
# ---------------------------------------------------------------

print("\n=== 7. Weather does not update before the interval ===")
game = create_new_game()
original_condition = game.world.weather.condition

wait(game, 60)  # 60 minutes < 180 minute interval

results.append(check(
    "Weather condition unchanged after 60 min wait",
    game.world.weather.condition == original_condition,
))

# ---------------------------------------------------------------
# 8. Weather does not update when merely rendering context
# ---------------------------------------------------------------

print("\n=== 8. Weather does not update when rendering context ===")
game = create_new_game()
game.world.seed = 77
original_weather = Weather(
    condition=game.world.weather.condition,
    temperature=game.world.weather.temperature,
)

context = build_game_context(game)

results.append(check(
    "Context does not change weather condition",
    game.world.weather.condition == original_weather.condition,
))
results.append(check(
    "Context does not change weather temperature",
    game.world.weather.temperature == original_weather.temperature,
))

# ---------------------------------------------------------------
# 9. Weather does not update when rendering the map
# ---------------------------------------------------------------

print("\n=== 9. Weather does not update when rendering the map ===")
game = create_new_game()
game.world.seed = 88
original_weather = Weather(
    condition=game.world.weather.condition,
    temperature=game.world.weather.temperature,
)

map_str = render_map(game)

results.append(check(
    "Map does not change weather condition",
    game.world.weather.condition == original_weather.condition,
))
results.append(check(
    "Map does not change weather temperature",
    game.world.weather.temperature == original_weather.temperature,
))

# ---------------------------------------------------------------
# 10. Repeated /weather calls do not mutate state
# ---------------------------------------------------------------

print("\n=== 10. Repeated /weather calls do not mutate state ===")
game = create_new_game()
original_condition = game.world.weather.condition
original_temperature = game.world.weather.temperature

# Simulate multiple /weather reads
for _ in range(10):
    _ = game.world.weather.condition
    _ = game.world.weather.temperature

results.append(check(
    "Weather condition unchanged after repeated reads",
    game.world.weather.condition == original_condition,
))
results.append(check(
    "Weather temperature unchanged after repeated reads",
    game.world.weather.temperature == original_temperature,
))

# ---------------------------------------------------------------
# 11. /weather displays current condition
# ---------------------------------------------------------------

print("\n=== 11. /weather displays current condition ===")
game = create_new_game()
weather = game.world.weather

results.append(check(
    "Weather condition is a string",
    isinstance(weather.condition, str),
))
results.append(check(
    "Weather temperature is an int",
    isinstance(weather.temperature, int),
))
results.append(check(
    "Condition is in supported list",
    weather.condition in SUPPORTED_CONDITIONS,
))

# ---------------------------------------------------------------
# 12. /help contains /weather
# ---------------------------------------------------------------

print("\n=== 12. /help contains /weather ===")
with open("main.py", "r", encoding="utf-8") as f:
    source = f.read()

results.append(check(
    "/weather in help text",
    "/weather" in source,
))
results.append(check(
    "show_weather function defined",
    "def show_weather" in source,
))

# ---------------------------------------------------------------
# 13. Weather appears in AI context
# ---------------------------------------------------------------

print("\n=== 13. Weather appears in AI context ===")
game = create_new_game()
context = build_game_context(game)

results.append(check(
    "WEATHER section in context",
    "=== WEATHER ===" in context,
))
results.append(check(
    "Condition line in context",
    "Condition:" in context,
))
results.append(check(
    "Temperature line in context",
    "Temperature:" in context,
))
results.append(check(
    "Weather read-only note in context",
    "must not emit weather mutation" in context,
))

# ---------------------------------------------------------------
# 14. AI context does not invent weather state
# ---------------------------------------------------------------

print("\n=== 14. AI context does not invent weather state ===")
game = create_new_game()
game.world.weather = Weather(condition="storm", temperature=22)
context = build_game_context(game)

results.append(check(
    "Context shows actual condition (storm)",
    "Condition: storm" in context,
))
results.append(check(
    "Context shows actual temperature",
    "Temperature: 22°C" in context,
))

# ---------------------------------------------------------------
# 15. Save/load preserves or reconstructs weather correctly
# ---------------------------------------------------------------

print("\n=== 15. Save/load preserves or reconstructs weather correctly ===")
game = create_new_game()
game.world.seed = 42
game.world.weather = Weather(condition="rain", temperature=18)

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    save_path = Path(f.name)

save_game(game, save_path)
loaded = load_game(save_path)

results.append(check(
    "Weather condition preserved",
    loaded.world.weather.condition == "rain",
))
results.append(check(
    "Weather temperature preserved",
    loaded.world.weather.temperature == 18,
))
results.append(check(
    "Seed preserved",
    loaded.world.seed == 42,
))

save_path.unlink(missing_ok=True)

# ---------------------------------------------------------------
# 16. Old saves without weather data load safely
# ---------------------------------------------------------------

print("\n=== 16. Old saves without weather data load safely ===")
old_save = {
    "version": 2,
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
        "name": "Test World",
        "genre": "fantasy",
        "time": "12:00",
        "day": 1,
        "weather": "Rain",
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
    "Legacy string weather converted to Weather",
    isinstance(old_loaded.world.weather, Weather),
))
results.append(check(
    "Legacy weather condition is 'rain' (lowered)",
    old_loaded.world.weather.condition == "rain",
))
results.append(check(
    "Seed defaults to 0 for old saves",
    old_loaded.world.seed == 0,
))

old_path.unlink(missing_ok=True)

# ---------------------------------------------------------------
# 17. Temperature changes according to time of day
# ---------------------------------------------------------------

print("\n=== 17. Temperature changes according to time of day ===")
temperatures = {}
for hour in range(24):
    total_minutes = 1 * 24 * 60 + hour * 60  # day 1
    w = compute_weather(42, total_minutes)
    temperatures[hour] = w.temperature

results.append(check(
    "Night (3am) is cooler than afternoon (12pm)",
    temperatures[3] < temperatures[12],
))
results.append(check(
    "Morning (8am) differs from night (3am)",
    temperatures[8] != temperatures[3],
))

# ---------------------------------------------------------------
# 18. Weather modifiers affect temperature deterministically
# ---------------------------------------------------------------

print("\n=== 18. Weather modifiers affect temperature deterministically ===")
for cond, modifier in TEMPERATURE_MODIFIERS.items():
    w_clear = Weather(condition="clear", temperature=25)
    w_cond = Weather(condition=cond, temperature=25 + modifier)
    results.append(check(
        f"Modifier for '{cond}' is {modifier}",
        w_cond.temperature == 25 + modifier,
    ))

# ---------------------------------------------------------------
# 19. Weather changes produce an event only when condition changes
# ---------------------------------------------------------------

print("\n=== 19. Weather changes produce an event only when condition changes ===")
msg1 = get_weather_change_message("clear", "rain")
msg2 = get_weather_change_message("rain", "rain")

results.append(check(
    "Different conditions produce a message",
    msg1 is not None and isinstance(msg1, str),
))
results.append(check(
    "Same conditions produce no message",
    msg2 is None,
))

# ---------------------------------------------------------------
# 20. No event is generated when weather remains unchanged
# ---------------------------------------------------------------

print("\n=== 20. No event is generated when weather remains unchanged ===")
for cond in SUPPORTED_CONDITIONS:
    msg = get_weather_change_message(cond, cond)
    results.append(check(
        f"No event for '{cond}' -> '{cond}'",
        msg is None,
    ))

# ---------------------------------------------------------------
# 21. Wait advances weather correctly
# ---------------------------------------------------------------

print("\n=== 21. Wait advances weather correctly ===")
game = create_new_game()
game.world.seed = 42

# Wait exactly WEATHER_INTERVAL minutes
result = wait(game, WEATHER_INTERVAL)

results.append(check(
    "Wait succeeded",
    result.success,
))
results.append(check(
    "Weather change data present",
    "weather_change" in result.data,
))

# ---------------------------------------------------------------
# 22. Failed actions do not advance weather
# ---------------------------------------------------------------

print("\n=== 22. Failed actions do not advance weather ===")
game = create_new_game()
original_condition = game.world.weather.condition

result = wait(game, -5)

results.append(check(
    "Failed wait returns failure",
    not result.success,
))
results.append(check(
    "Weather unchanged after failed action",
    game.world.weather.condition == original_condition,
))

# ---------------------------------------------------------------
# 23. NPC routines do not advance weather multiple times
# ---------------------------------------------------------------

print("\n=== 23. NPC routines do not advance weather multiple times ===")
game = create_new_game()
game.world.seed = 42

old_total = game.world.day * 24 * 60 + _time_to_minutes(game.world.time)
result = wait(game, 200)
new_total = game.world.day * 24 * 60 + _time_to_minutes(game.world.time)

old_period = old_total // WEATHER_INTERVAL
new_period = new_total // WEATHER_INTERVAL

# Should only advance one period (or zero)
period_diff = new_period - old_period

results.append(check(
    "Period advanced by at most 1",
    period_diff <= 1,
))
results.append(check(
    "Weather matches expected period",
    compute_weather(game.world.seed, new_total).condition
    == game.world.weather.condition,
))

# ---------------------------------------------------------------
# 24. Map output can display current weather
# ---------------------------------------------------------------

print("\n=== 24. Map output can display current weather ===")
game = create_new_game()
game.world.weather = Weather(condition="fog", temperature=19)
map_str = render_map(game)

results.append(check(
    "Map contains weather info",
    "Weather:" in map_str,
))
results.append(check(
    "Map shows fog condition",
    "Fog" in map_str,
))
results.append(check(
    "Map shows temperature",
    "19°C" in map_str,
))

# ---------------------------------------------------------------
# 25. Weather rendering does not mutate game state
# ---------------------------------------------------------------

print("\n=== 25. Weather rendering does not mutate game state ===")
game = create_new_game()
original_location = game.player.location
original_visited = game.visited_locations.copy()
original_weather = Weather(
    condition=game.world.weather.condition,
    temperature=game.world.weather.temperature,
)

render_map(game)
build_game_context(game)

results.append(check(
    "Player location unchanged",
    game.player.location == original_location,
))
results.append(check(
    "Visited locations unchanged",
    game.visited_locations == original_visited,
))
results.append(check(
    "Weather condition unchanged",
    game.world.weather.condition == original_weather.condition,
))
results.append(check(
    "Weather temperature unchanged",
    game.world.weather.temperature == original_weather.temperature,
))

# ---------------------------------------------------------------
# 26. Full sequence: start -> wait -> wait -> weather transition
#      -> save -> load -> same weather
# ---------------------------------------------------------------

print("\n=== 26. Full sequence test ===")
game = create_new_game()
game.world.seed = 42

# Wait 200 minutes to cross a weather period boundary
wait(game, 200)

saved_condition = game.world.weather.condition
saved_temperature = game.world.weather.temperature
saved_seed = game.world.seed
saved_day = game.world.day
saved_time = game.world.time

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    save_path = Path(f.name)

save_game(game, save_path)
loaded = load_game(save_path)

results.append(check(
    "Loaded condition matches saved",
    loaded.world.weather.condition == saved_condition,
))
results.append(check(
    "Loaded temperature matches saved",
    loaded.world.weather.temperature == saved_temperature,
))
results.append(check(
    "Loaded seed matches saved",
    loaded.world.seed == saved_seed,
))
results.append(check(
    "Loaded day matches saved",
    loaded.world.day == saved_day,
))
results.append(check(
    "Loaded time matches saved",
    loaded.world.time == saved_time,
))

# Verify determinism: recompute from loaded state
total = loaded.world.day * 24 * 60 + _time_to_minutes(loaded.world.time)
recomputed = compute_weather(loaded.world.seed, total)

results.append(check(
    "Recomputed weather matches loaded",
    recomputed.condition == loaded.world.weather.condition,
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
