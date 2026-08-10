"""Infinite RPG - Main game loop and UI.

UI V2: Uses the split-screen renderer for the main gameplay view.
Overlay screens (inventory, quests, etc.) retain the classic boxed layout.
"""

import sys

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings

    _HAS_PROMPT_TOOLKIT = True
except ImportError:
    _HAS_PROMPT_TOOLKIT = False

from engine.game import GameEngine
from engine.renderer import render_game, clear_screen
from engine.weather import get_condition_description
from engine.events import format_events_for_display


def create_session():
    """Create a keyboard-aware command session."""
    if not _HAS_PROMPT_TOOLKIT:
        return None

    bindings = KeyBindings()

    @bindings.add("escape")
    def _(event):
        event.app.exit(result="__ESC__")

    return PromptSession(key_bindings=bindings)


def _input_prompt(session, prompt_str="> "):
    """Get input, using prompt_toolkit if available, else standard input."""
    if session is not None:
        return session.prompt(prompt_str)
    else:
        return input(prompt_str)


def _overlay_header(title: str) -> None:
    """Print a boxed overlay header."""
    print()
    print("\u2554\u2550" + "\u2550" * 62 + "\u2557")
    # Center the title
    padding = 62 - len(title) - 2
    left_pad = padding // 2
    right_pad = padding - left_pad
    print(
        f"\u2551{' ' * left_pad}{title}{' ' * right_pad}\u2551"
    )
    print("\u2560" + "\u2550" * 62 + "\u2563")


def _overlay_footer() -> None:
    """Print a boxed overlay footer."""
    print("\u2560" + "\u2550" * 62 + "\u2563")
    print(
        "\u2551"
        + " " * 17
        + "Press ESC to close"
        + " " * 17
        + "\u2551"
    )
    print("\u255a" + "\u2550" * 62 + "\u255d")


def show_inventory(game):
    """Display the inventory screen."""
    session = create_session()

    while True:
        _overlay_header("INVENTORY")
        print()

        inventory = game.player.inventory

        if inventory:
            for item in inventory:
                print(f"  \u25c6 {item}")
        else:
            print("  Your inventory is empty.")

        print()
        _overlay_footer()

        result = _input_prompt(session, "\n")

        if result == "__ESC__":
            return


def show_quests(game):
    """Display the quests screen."""
    session = create_session()

    while True:
        _overlay_header("QUESTS")
        print()

        quests = game.quests

        if not quests:
            print("  No quests.")
        else:
            active = [q for q in quests.values() if q.state == "active"]
            offered = [q for q in quests.values() if q.state == "offered"]
            completed = [q for q in quests.values() if q.state == "completed"]
            failed = [q for q in quests.values() if q.state == "failed"]
            abandoned = [q for q in quests.values() if q.state == "abandoned"]

            if active:
                print("  ACTIVE:")
                for q in active:
                    print(f"    [{q.id}] {q.title}")
                    total = len(q.objectives)
                    done = sum(1 for o in q.objectives if o.completed)
                    print(f"      Progress: {done}/{total} objectives")
                    for o in q.objectives:
                        mark = "x" if o.completed else " "
                        print(
                            f"        [{mark}] {o.description}"
                            f" ({o.current}/{o.required})"
                        )
                print()

            if offered:
                print("  OFFERED:")
                for q in offered:
                    print(f"    [{q.id}] {q.title}")
                    print(f"      {q.description}")
                print()

            if completed:
                print("  COMPLETED:")
                for q in completed:
                    print(f"    [{q.id}] {q.title}")
                print()

            if failed:
                print("  FAILED:")
                for q in failed:
                    print(f"    [{q.id}] {q.title}")
                print()

            if abandoned:
                print("  ABANDONED:")
                for q in abandoned:
                    print(f"    [{q.id}] {q.title}")
                print()

        _overlay_footer()

        result = _input_prompt(session, "\n")

        if result == "__ESC__":
            return


def show_status(game):
    """Display the player status screen."""
    session = create_session()

    while True:
        _overlay_header("STATUS")
        print()

        player = game.player
        xp_for_next = player.level * 100

        print(f"  Name:            {player.name}")
        print(f"  Level:           {player.level}")
        print(f"  XP:              {player.xp}/{xp_for_next}")
        print(f"  Stat Points:     {player.stat_points}")
        print()
        print(f"  HP:              {player.hp}/{player.max_hp}")
        print()
        print(f"  Strength:        {player.strength}")
        print(f"  Vitality:        {player.vitality}")
        print(f"  Agility:         {player.agility}")
        print(f"  Intelligence:    {player.intelligence}")
        print()

        bare_damage = max(1, 5 + player.strength - 10)
        weapon_damage = max(1, 15 + player.strength - 10)
        print(f"  Bare Hands Dmg:  {bare_damage}")
        print(f"  Weapon Dmg:      {weapon_damage}")

        print()
        _overlay_footer()

        result = _input_prompt(session, "\n")

        if result == "__ESC__":
            return


def show_crafting(game):
    """Display the crafting screen."""
    from engine.actions import RECIPES, ITEM_PRICES

    session = create_session()

    while True:
        _overlay_header("CRAFTING")
        print()

        player = game.player
        print(f"  Money: {player.money} gold")
        print()

        if not RECIPES:
            print("  No recipes available.")
        else:
            print("  Available Recipes:")
            for recipe_id, recipe in RECIPES.items():
                print(f"    [{recipe_id}] {recipe.name}")
                ingredient_parts = [
                    f"{item} x{qty}"
                    for item, qty in recipe.ingredients.items()
                ]
                print(f"      Ingredients: {', '.join(ingredient_parts)}")
                print(f"      Output: {recipe.output} x{recipe.output_quantity}")

                can_craft = True
                for ingredient, required in recipe.ingredients.items():
                    if player.inventory.count(ingredient) < required:
                        can_craft = False
                        break

                status = "READY" if can_craft else "Missing ingredients"
                print(f"      Status: {status}")
                print()

        _overlay_footer()

        result = _input_prompt(session, "\n")

        if result == "__ESC__":
            return


def show_trading(game):
    """Display the trading screen."""
    from engine.actions import ITEM_PRICES

    session = create_session()

    while True:
        _overlay_header("TRADING")
        print()

        player = game.player
        location = game.current_location()

        print(f"  Your Money: {player.money} gold")
        print()

        if not location or not location.npcs:
            print("  No merchants nearby.")
        else:
            merchants = [
                game.world.npcs[npc_id]
                for npc_id in location.npcs
                if npc_id in game.world.npcs
                and game.world.npcs[npc_id].hp > 0
                and game.world.npcs[npc_id].inventory
            ]

            if not merchants:
                print("  No merchants nearby.")
            else:
                for npc in merchants:
                    print(f"  {npc.name} ({npc.id})")
                    print(f"    Money: {npc.money} gold")
                    print("    Inventory:")

                    item_counts = {}
                    for item in npc.inventory:
                        item_counts[item] = item_counts.get(item, 0) + 1

                    for item, count in item_counts.items():
                        price = ITEM_PRICES.get(item, 0)
                        print(f"      - {item} x{count} (buy: {price}g)")

                    print()

        _overlay_footer()

        result = _input_prompt(session, "\n")

        if result == "__ESC__":
            return


def show_map(game):
    """Display the map screen using the top-down 2D world map."""
    from engine.world_map import render_full_map

    session = create_session()

    while True:
        _overlay_header("MAP")
        print()

        map_str = render_full_map(game)
        print(map_str)

        _overlay_footer()

        result = _input_prompt(session, "\n")

        if result == "__ESC__":
            return


def show_weather(game):
    """Display the weather screen."""
    session = create_session()

    while True:
        _overlay_header("WEATHER")
        print()

        weather = game.world.weather
        desc = get_condition_description(weather.condition)

        print(f"  Condition:    {weather.condition.title()}")
        print(f"  Description:  {desc}")
        print(f"  Temperature:  {weather.temperature}\u00b0C")
        print(f"  Time:         {game.world.time}")
        print(f"  Day:          {game.world.day}")

        print()
        _overlay_footer()

        result = _input_prompt(session, "\n")

        if result == "__ESC__":
            return


def show_events(game):
    """Display the world events screen."""
    session = create_session()

    while True:
        _overlay_header("RECENT WORLD EVENTS")
        print()

        display = format_events_for_display(game.events)
        print(display)

        print()
        _overlay_footer()

        result = _input_prompt(session, "\n")

        if result == "__ESC__":
            return


def main():
    print()
    print("\u2554\u2550" + "\u2550" * 62 + "\u2557")
    print("\u2551" + " " * 62 + "\u2551")
    print(
        "\u2551"
        + " " * 15
        + "\u2726 INFINITE RPG \u2726"
        + " " * 15
        + "\u2551"
    )
    print("\u2551" + " " * 62 + "\u2551")
    print(
        "\u2551"
        + " " * 18
        + "[1] New Game"
        + " " * 18
        + "\u2551"
    )
    print(
        "\u2551"
        + " " * 18
        + "[2] Load Game"
        + " " * 17
        + "\u2551"
    )
    print(
        "\u2551"
        + " " * 18
        + "[3] Quit"
        + " " * 21
        + "\u2551"
    )
    print("\u2551" + " " * 62 + "\u2551")
    print("\u255a" + "\u2550" * 62 + "\u255d")
    print()

    choice = input("> ").strip()

    if choice == "3":
        print("Goodbye.")
        return

    if choice not in ("1", "2"):
        print("Invalid choice.")
        return

    game = GameEngine()

    try:
        if choice == "2":
            try:
                game.load()
            except FileNotFoundError:
                print()
                print("No save file found.")
                return
            except Exception as error:
                print()
                print(f"Load failed: {error}")
                return

        session = create_session()

        while True:
            output = render_game(game.game)
            clear_screen()
            sys.stdout.write(output)
            sys.stdout.flush()

            try:
                player_input = _input_prompt(session, "> ")
            except (EOFError, KeyboardInterrupt):
                break

            player_input = player_input.strip()

            if not player_input:
                continue

            command = player_input.lower()

            if command == "/quit":
                print()
                print("Leaving the world...")
                break

            if command == "/inventory":
                show_inventory(game.game)
                continue

            if command == "/quests":
                show_quests(game.game)
                continue

            if command == "/status":
                show_status(game.game)
                continue

            if command == "/craft":
                show_crafting(game.game)
                continue

            if command == "/trade":
                show_trading(game.game)
                continue

            if command == "/map":
                show_map(game.game)
                continue

            if command == "/weather":
                show_weather(game.game)
                continue

            if command == "/events":
                show_events(game.game)
                continue

            if command == "/save":
                try:
                    game.save()
                    print()
                    print("Game saved.")
                except Exception as error:
                    print()
                    print(f"Save failed: {error}")

                continue

            if command == "/load":
                try:
                    game.load()
                    print()
                    print("Game loaded.")
                except FileNotFoundError:
                    print()
                    print("No save file exists yet.")
                except Exception as error:
                    print()
                    print(f"Load failed: {error}")

                continue

            if command == "/help":
                print()
                print("Commands:")
                print("  /inventory  Open inventory")
                print("  /quests     View quests")
                print("  /status     View player stats")
                print("  /craft      View crafting recipes")
                print("  /trade      View nearby merchants")
                print("  /map        Open map")
                print("  /weather    View weather")
                print("  /events     View world events")
                print("  /save       Save game")
                print("  /load       Load game")
                print("  /quit       Exit game")
                print()
                print("You can also type anything you want your")
                print("character to do.")
                continue

            result = game.process_input(player_input)

            for action in result["actions"]:
                if not action["success"]:
                    print()
                    print(f"\u26a0 {action['message']}")

    finally:
        game.close()


if __name__ == "__main__":
    main()
