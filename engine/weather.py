import random

from .state import Weather


WEATHER_INTERVAL = 180  # 3 game hours in minutes

SUPPORTED_CONDITIONS = ("clear", "cloudy", "rain", "storm", "fog")

# Transition probabilities from each condition.
# Values are percentages that sum to 100.
TRANSITIONS = {
    "clear":  {"clear": 60, "cloudy": 30, "rain": 10},
    "cloudy": {"clear": 30, "cloudy": 40, "rain": 25, "fog": 5},
    "rain":   {"cloudy": 35, "rain": 45, "storm": 15, "clear": 5},
    "storm":  {"rain": 60, "cloudy": 30, "clear": 10},
    "fog":    {"clear": 40, "cloudy": 40, "rain": 20},
}

# Baseline temperature by hour of day.
_HOUR_RANGES = [
    (range(0, 6), 18),
    (range(6, 10), 22),
    (range(10, 16), 28),
    (range(16, 20), 24),
    (range(20, 24), 20),
]

TEMPERATURE_MODIFIERS = {
    "clear": 0,
    "cloudy": -1,
    "rain": -2,
    "storm": -3,
    "fog": -1,
}

# Weather change narration keyed by (old, new).
CHANGE_MESSAGES = {
    ("clear", "cloudy"): "Dark clouds gather overhead.",
    ("clear", "rain"): "Rain begins to fall.",
    ("clear", "storm"): "Thunder rumbles as a storm approaches.",
    ("clear", "fog"): "A thick fog rolls in.",
    ("cloudy", "clear"): "The clouds part and the sky clears.",
    ("cloudy", "rain"): "Rain starts to fall from the dark clouds.",
    ("cloudy", "storm"): "Thunder rumbles as the clouds darken.",
    ("cloudy", "fog"): "A thick fog rolls in from the lowlands.",
    ("rain", "clear"): "The rain stops and the sky clears.",
    ("rain", "cloudy"): "The rain eases to a steady drizzle.",
    ("rain", "storm"): "Thunder rumbles as the rain intensifies.",
    ("rain", "fog"): "The rain fades into a dense fog.",
    ("storm", "clear"): "The storm passes and the sky clears.",
    ("storm", "cloudy"): "The storm weakens to overcast skies.",
    ("storm", "rain"): "The storm eases to steady rain.",
    ("fog", "clear"): "The fog lifts and the sky clears.",
    ("fog", "cloudy"): "The fog thins to overcast clouds.",
    ("fog", "rain"): "The fog turns to light rain.",
}


def _get_temperature_baseline(hour: int) -> int:
    """Return baseline temperature for a given hour of day."""
    for time_range, temp in _HOUR_RANGES:
        if hour in time_range:
            return temp
    return 22


def _weather_period(total_minutes: int) -> int:
    """Return the weather period index for the given total minutes."""
    return total_minutes // WEATHER_INTERVAL


def compute_weather(seed: int, total_minutes: int) -> Weather:
    """Compute weather deterministically from seed and game time.

    Same (seed, total_minutes) always produces the same Weather.
    """
    period = _weather_period(total_minutes)
    rng = random.Random(seed ^ (period * 2654435761))

    # Transition from a neutral base to pick the period's condition.
    roll = rng.randint(0, 99)
    cumulative = 0
    condition = "clear"
    for cond, prob in TRANSITIONS["clear"].items():
        cumulative += prob
        if roll < cumulative:
            condition = cond
            break

    hour = (total_minutes % (24 * 60)) // 60
    baseline = _get_temperature_baseline(hour)
    modifier = TEMPERATURE_MODIFIERS.get(condition, 0)
    temperature = baseline + modifier

    return Weather(condition=condition, temperature=temperature)


def get_weather_change_message(
    old_condition: str,
    new_condition: str,
) -> str | None:
    """Return a narration string when weather changes, or None."""
    if old_condition == new_condition:
        return None
    return CHANGE_MESSAGES.get(
        (old_condition, new_condition),
        "The weather shifts.",
    )


def get_condition_description(condition: str) -> str:
    """Return a short player-facing description of the condition."""
    descriptions = {
        "clear": "Clear skies",
        "cloudy": "Overcast clouds",
        "rain": "Rain falling",
        "storm": "Heavy storm",
        "fog": "Dense fog",
    }
    return descriptions.get(condition, "Unknown weather")
