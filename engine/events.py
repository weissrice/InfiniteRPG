import random
from typing import List, Optional, Tuple

from .state import GameState, WorldEvent


EVENT_INTERVAL = 360  # 6 game hours in minutes
MAX_WORLD_EVENTS = 50
EVENT_CONTEXT_COUNT = 10

# Event type weights for deterministic selection.
EVENT_WEIGHTS = {
    "npc_encounter": 30,
    "npc_dispute": 20,
    "merchant_restock": 25,
    "weather_incident": 25,
}

WEATHER_INCIDENT_CONDITIONS = ("rain", "storm", "fog")

MERCHANT_RESTOCKS = {
    "merchant": {
        "items": ["Herb", "Wood", "Cloth", "Empty Bottle", "Torch"],
        "money": 50,
    },
}


def _event_period(total_minutes: int) -> int:
    """Return the event period index for the given total minutes."""
    return total_minutes // EVENT_INTERVAL


def _make_event_id(seed: int, period: int, index: int) -> str:
    """Create a deterministic event id."""
    rng = random.Random(seed ^ (period * 2654435761) ^ (index * 7919))
    return f"evt_{period}_{rng.randint(10000, 99999)}"


def _roll_event(seed: int, period: int) -> Optional[str]:
    """Deterministically decide whether an event occurs and which type.

    Returns the event type string or None if no event occurs.
    """
    rng = random.Random(seed ^ (period * 3743217617))

    # 50% chance of no event
    if rng.randint(0, 99) < 50:
        return None

    # Weighted selection of event type
    roll = rng.randint(0, 99)
    cumulative = 0
    for etype, weight in EVENT_WEIGHTS.items():
        cumulative += weight
        if roll < cumulative:
            return etype

    return "npc_encounter"


def _find_co_located_npc_pairs(
    game: GameState,
) -> List[Tuple[str, str, str]]:
    """Find all pairs of living NPCs at the same location.

    Returns list of (npc_a_id, npc_b_id, location_id).
    """
    pairs = []
    for loc_id, loc in game.world.locations.items():
        living_npcs = [
            npc_id for npc_id in loc.npcs
            if npc_id in game.world.npcs
            and game.world.npcs[npc_id].hp > 0
        ]
        for i in range(len(living_npcs)):
            for j in range(i + 1, len(living_npcs)):
                pairs.append((living_npcs[i], living_npcs[j], loc_id))
    return pairs


def _find_merchants(game: GameState) -> List[str]:
    """Find all living merchant NPCs with configured restock data."""
    merchants = []
    for npc_id, npc in game.world.npcs.items():
        if (
            npc.hp > 0
            and npc_id in MERCHANT_RESTOCKS
        ):
            merchants.append(npc_id)
    return merchants


def _npc_encounter(
    game: GameState,
    seed: int,
    period: int,
) -> Optional[WorldEvent]:
    """Generate an npc_encounter event if eligible NPCs exist."""
    pairs = _find_co_located_npc_pairs(game)
    if not pairs:
        return None

    rng = random.Random(seed ^ (period * 1193183571))
    pair = pairs[rng.randint(0, len(pairs) - 1)]

    npc_a = game.world.npcs[pair[0]]
    npc_b = game.world.npcs[pair[1]]
    loc = game.world.locations[pair[2]]

    # Record memories
    memory_a = f"{npc_a.name} met with {npc_b.name} at {loc.name}."
    memory_b = f"{npc_b.name} met with {npc_a.name} at {loc.name}."

    if memory_a not in npc_a.memory:
        npc_a.memory.append(memory_a)
    if memory_b not in npc_b.memory:
        npc_b.memory.append(memory_b)

    # Small positive relationship adjustment
    current_a = npc_a.relationships.get(npc_b.name, 0)
    npc_a.relationships[npc_b.name] = min(100, current_a + 1)
    current_b = npc_b.relationships.get(npc_a.name, 0)
    npc_b.relationships[npc_a.name] = min(100, current_b + 1)

    event_id = _make_event_id(seed, period, 0)

    return WorldEvent(
        id=event_id,
        type="npc_encounter",
        title=f"{npc_a.name} meets {npc_b.name}",
        description=f"{npc_a.name} and {npc_b.name} meet at {loc.name}.",
        location=loc.name,
        actors=[npc_a.name, npc_b.name],
        day=game.world.day,
        time=game.world.time,
    )


def _npc_dispute(
    game: GameState,
    seed: int,
    period: int,
) -> Optional[WorldEvent]:
    """Generate an npc_dispute event if eligible NPCs exist."""
    pairs = _find_co_located_npc_pairs(game)
    if not pairs:
        return None

    rng = random.Random(seed ^ (period * 2849632741))
    pair = pairs[rng.randint(0, len(pairs) - 1)]

    npc_a = game.world.npcs[pair[0]]
    npc_b = game.world.npcs[pair[1]]
    loc = game.world.locations[pair[2]]

    # Record memories
    memory_a = f"{npc_a.name} argued with {npc_b.name} at {loc.name}."
    memory_b = f"{npc_b.name} argued with {npc_a.name} at {loc.name}."

    if memory_a not in npc_a.memory:
        npc_a.memory.append(memory_a)
    if memory_b not in npc_b.memory:
        npc_b.memory.append(memory_b)

    # Small negative relationship adjustment
    current_a = npc_a.relationships.get(npc_b.name, 0)
    npc_a.relationships[npc_b.name] = max(-100, current_a - 3)
    current_b = npc_b.relationships.get(npc_a.name, 0)
    npc_b.relationships[npc_a.name] = max(-100, current_b - 3)

    event_id = _make_event_id(seed, period, 1)

    return WorldEvent(
        id=event_id,
        type="npc_dispute",
        title=f"{npc_a.name} argues with {npc_b.name}",
        description=f"{npc_a.name} and {npc_b.name} have a heated argument at {loc.name}.",
        location=loc.name,
        actors=[npc_a.name, npc_b.name],
        day=game.world.day,
        time=game.world.time,
    )


def _merchant_restock(
    game: GameState,
    seed: int,
    period: int,
) -> Optional[WorldEvent]:
    """Generate a merchant_restock event if eligible merchants exist."""
    merchants = _find_merchants(game)
    if not merchants:
        return None

    rng = random.Random(seed ^ (period * 3284912837))
    merchant_id = merchants[rng.randint(0, len(merchants) - 1)]
    npc = game.world.npcs[merchant_id]
    restock = MERCHANT_RESTOCKS[merchant_id]

    # Restore items: add one of each configured item if not already present
    items_added = []
    for item in restock["items"]:
        if item not in npc.inventory:
            npc.inventory.append(item)
            items_added.append(item)

    # Restore money
    money_added = 0
    if npc.money < restock["money"]:
        money_added = restock["money"] - npc.money
        npc.money = restock["money"]

    if not items_added and money_added == 0:
        return None

    event_id = _make_event_id(seed, period, 2)

    desc_parts = []
    if items_added:
        desc_parts.append(f"{npc.name} restocked {', '.join(items_added)}.")
    if money_added > 0:
        desc_parts.append(f"{npc.name} received {money_added} gold.")

    return WorldEvent(
        id=event_id,
        type="merchant_restock",
        title=f"{npc.name} restocks",
        description=" ".join(desc_parts),
        location=game.world.locations[npc.location].name
        if npc.location in game.world.locations
        else npc.location,
        actors=[npc.name],
        day=game.world.day,
        time=game.world.time,
    )


def _weather_incident(
    game: GameState,
    seed: int,
    period: int,
) -> Optional[WorldEvent]:
    """Generate a weather_incident event if weather supports it."""
    condition = game.world.weather.condition
    if condition not in WEATHER_INCIDENT_CONDITIONS:
        return None

    # Pick a random location for the incident
    loc_ids = list(game.world.locations.keys())
    if not loc_ids:
        return None

    rng = random.Random(seed ^ (period * 4129384721))
    loc_id = loc_ids[rng.randint(0, len(loc_ids) - 1)]
    loc = game.world.locations[loc_id]

    messages = {
        "rain": f"Rain causes minor flooding near {loc.name}.",
        "storm": f"A storm blows debris through {loc.name}.",
        "fog": f"Dense fog reduces visibility around {loc.name}.",
    }

    description = messages.get(
        condition,
        f"Weather affects {loc.name}.",
    )

    event_id = _make_event_id(seed, period, 3)

    return WorldEvent(
        id=event_id,
        type="weather_incident",
        title=f"Weather incident at {loc.name}",
        description=description,
        location=loc.name,
        actors=[],
        day=game.world.day,
        time=game.world.time,
    )


EVENT_GENERATORS = {
    "npc_encounter": _npc_encounter,
    "npc_dispute": _npc_dispute,
    "merchant_restock": _merchant_restock,
    "weather_incident": _weather_incident,
}


def process_event_period(game: GameState) -> Optional[WorldEvent]:
    """Process a single event period. Returns the event or None.

    This is the authoritative function called during time advancement.
    It checks the current period against last_event_period to avoid
    processing the same period twice.
    """
    total = game.world.day * 24 * 60 + _total_minutes(game.world.time)
    period = _event_period(total)

    if period <= game.last_event_period:
        return None

    game.last_event_period = period

    event_type = _roll_event(game.world.seed, period)
    if event_type is None:
        return None

    generator = EVENT_GENERATORS.get(event_type)
    if generator is None:
        return None

    event = generator(game, game.world.seed, period)
    if event is None:
        return None

    # Bound the event history
    game.events.append(event)
    if len(game.events) > MAX_WORLD_EVENTS:
        game.events = game.events[-MAX_WORLD_EVENTS:]

    return event


def process_event_range(
    game: GameState,
    old_total: int,
    new_total: int,
) -> List[WorldEvent]:
    """Process all event periods crossed between old_total and new_total.

    Each period is processed exactly once.
    """
    events = []
    old_period = _event_period(old_total)
    new_period = _event_period(new_total)

    for period in range(old_period + 1, new_period + 1):
        # Check if this period was already processed
        if period <= game.last_event_period:
            continue

        game.last_event_period = period

        event_type = _roll_event(game.world.seed, period)
        if event_type is None:
            continue

        generator = EVENT_GENERATORS.get(event_type)
        if generator is None:
            continue

        event = generator(game, game.world.seed, period)
        if event is None:
            continue

        game.events.append(event)
        events.append(event)

    # Bound history
    if len(game.events) > MAX_WORLD_EVENTS:
        game.events = game.events[-MAX_WORLD_EVENTS:]

    return events


def _total_minutes(time_str: str) -> int:
    """Convert HH:MM string to minutes since midnight."""
    try:
        hours, minutes = time_str.split(":")
        return int(hours) * 60 + int(minutes)
    except (ValueError, TypeError):
        return 0


def format_events_for_display(events: List[WorldEvent]) -> str:
    """Format event history for player display."""
    if not events:
        return "No recent world events."

    lines = []
    for event in reversed(events):
        lines.append(
            f"- Day {event.day} {event.time} — {event.location}"
        )
        lines.append(f"  {event.description}")
    return "\n".join(lines)


def format_events_for_context(events: List[WorldEvent]) -> str:
    """Format recent events for AI context."""
    recent = events[-EVENT_CONTEXT_COUNT:]
    if not recent:
        return "=== RECENT WORLD EVENTS ===\n(none)"

    lines = ["=== RECENT WORLD EVENTS ==="]
    for event in reversed(recent):
        lines.append(
            f"- Day {event.day} {event.time} — "
            f"{event.location} — {event.description}"
        )
    lines.append(
        "(These events are authoritative world history. "
        "The AI may describe or react to them but must not "
        "invent state changes.)"
    )
    return "\n".join(lines)
