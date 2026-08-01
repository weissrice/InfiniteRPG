from engine.game import GameEngine


def main():
    game = GameEngine()

    try:
        print("=== INFINITE RPG TEST ===")
        print()

        print("Starting location:")
        print(game.game.current_location().name)

        print()
        print("Player: Go outside.")
        print()

        result = game.process_input(
            "Go outside."
        )

        print("NARRATION:")
        print(result["narration"])

        print()
        print("ACTIONS:")
        for action in result["actions"]:
            print(action)

        print()
        print("INVENTORY:")
        print(game.game.player.inventory)

        print()
        print("CURRENT LOCATION:")
        print(game.game.current_location().name)

    finally:
        game.close()


if __name__ == "__main__":
    main()