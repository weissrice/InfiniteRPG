import os

from .state import GameState


VISUAL_SYMBOLS = {
    "house": "🏠",
    "interior": "🚪",
    "forest": "🌲",
    "cave": "🕳️",
    "village": "🏘️",
    "city": "🏙️",
    "dungeon": "⚔️",
    "mountain": "⛰️",
    "water": "🌊",
    "road": "🛣️",
    "ruins": "🏚️",
    "castle": "🏰",
    "temple": "⛩️",
    "camp": "⛺",
    "area": "●",
}


DIRECTIONS = (
    "north",
    "east",
    "south",
    "west",
    "up",
    "down",
)


def clear_screen():
    """Clear the terminal screen."""

    os.system("cls" if os.name == "nt" else "clear")


def get_location_symbol(location) -> str:
    """Return the visual symbol for a location."""

    if location.symbol and location.symbol != "?":
        return location.symbol

    return VISUAL_SYMBOLS.get(
        location.visual_type,
        "●",
    )


def render_game(game: GameState):
    """Render the current game state."""

    clear_screen()

    player = game.player
    location = game.current_location()

    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║                     ✦ INFINITE RPG ✦                            ║")
    print(
        f"║              Day {game.world.day} • "
        f"{game.world.time} • {game.world.weather.condition:<12}             ║"
    )
    print("╠══════════════════════════════════════════════════════════════════╣")

    render_map(game)

    print("╠══════════════════════════════════════════════════════════════════╣")

    if location:
        print(f" LOCATION: {location.name}")
        print()
        print(f" {location.description}")

    if game.last_narration:
        print()
        print("╠══════════════════════════════════════════════════════════════════╣")
        print(" LAST EVENT")
        print()
        print(f" {game.last_narration}")

    print()
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(" PLAYER")
    print(
        f" {player.name}    "
        f"HP: {player.hp}/{player.max_hp}"
    )

    print()

    if player.inventory:
        inventory = " • ".join(player.inventory)
        print(f" Inventory: {inventory}")
    else:
        print(" Inventory: Empty")

    print("╠══════════════════════════════════════════════════════════════════╣")
    print(" Commands: /save  /load  /map  /inventory  /help  /quit")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()


def render_map(game: GameState):
    """Render the current location and its known connections."""

    current_id = game.player.location
    locations = game.world.locations

    print("                         WORLD MAP")
    print()

    current = locations.get(current_id)

    if current is None:
        print(f"                         Current: {current_id}")
        print()
        return

    current_symbol = get_location_symbol(current)

    print(
        f"                         {current_symbol} "
        f"{current.name}"
    )
    print("                              ●")
    print("                         YOU ARE HERE")

    connected_directions = set()

    if current.exits:
        print()
        print("                         CONNECTED LOCATIONS")

        for direction, destination_id in current.exits.items():
            destination = locations.get(destination_id)

            if destination:
                connected_directions.add(direction.lower())

                symbol = get_location_symbol(destination)

                print(
                    f"                         → {direction}: "
                    f"{symbol} {destination.name}"
                )

    unexplored = [
        direction
        for direction in DIRECTIONS
        if direction not in connected_directions
    ]

    if unexplored:
        print()
        print("                         UNEXPLORED DIRECTIONS")

        for direction in unexplored:
            print(
                f"                         ? {direction}"
            )

    print()