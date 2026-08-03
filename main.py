from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings

from engine.game import GameEngine
from engine.renderer import render_game


def create_session():
    """Create a keyboard-aware command session."""

    bindings = KeyBindings()

    @bindings.add("escape")
    def _(event):
        event.app.exit(result="__ESC__")

    return PromptSession(key_bindings=bindings)


def show_inventory(game):
    """Display the inventory screen."""

    session = create_session()

    while True:
        print()
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║                         INVENTORY                                ║")
        print("╠══════════════════════════════════════════════════════════════════╣")
        print()

        inventory = game.player.inventory

        if inventory:
            for item in inventory:
                print(f"  ◆ {item}")
        else:
            print("  Your inventory is empty.")

        print()
        print("╠══════════════════════════════════════════════════════════════════╣")
        print("║                     Press ESC to close                          ║")
        print("╚══════════════════════════════════════════════════════════════════╝")

        result = session.prompt("\n")

        if result == "__ESC__":
            return


def show_quests(game):
    """Display the quests screen."""

    session = create_session()

    while True:
        print()
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║                           QUESTS                                  ║")
        print("╠══════════════════════════════════════════════════════════════════╣")
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

        print("╠══════════════════════════════════════════════════════════════════╣")
        print("║                     Press ESC to close                          ║")
        print("╚══════════════════════════════════════════════════════════════════╝")

        result = session.prompt("\n")

        if result == "__ESC__":
            return


def show_status(game):
    """Display the player status screen."""

    session = create_session()

    while True:
        print()
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║                          STATUS                                  ║")
        print("╠══════════════════════════════════════════════════════════════════╣")
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
        print("╠══════════════════════════════════════════════════════════════════╣")
        print("║                     Press ESC to close                          ║")
        print("╚══════════════════════════════════════════════════════════════════╝")

        result = session.prompt("\n")

        if result == "__ESC__":
            return


def show_map(game):
    """Display the map screen."""

    render_game(game)

    session = create_session()

    while True:
        result = session.prompt(
            "\nPress ESC to return to the game: "
        )

        if result == "__ESC__":
            return


def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║                                                                  ║")
    print("║                      ✦ INFINITE RPG ✦                            ║")
    print("║                                                                  ║")
    print("║                       [1] New Game                               ║")
    print("║                       [2] Load Game                              ║")
    print("║                       [3] Quit                                   ║")
    print("║                                                                  ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
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

        session = PromptSession()

        while True:
            render_game(game.game)

            try:
                player_input = session.prompt("> ")
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

            if command == "/map":
                show_map(game.game)
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
                print("  /map        Open map")
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
                    print(f"⚠ {action['message']}")

    finally:
        game.close()


if __name__ == "__main__":
    main()