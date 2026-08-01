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