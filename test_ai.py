from engine.ai import AIClient


def main():
    ai = AIClient()

    try:
        response = ai.ask(
            prompt="Describe a mysterious forest in exactly two sentences.",
            system=(
                "You are the narrative AI for a living-world RPG. "
                "Be concise and immersive."
            ),
            max_tokens=4096,
            temperature=0.7,
        )

        print("\n" + response)

    finally:
        ai.close()


if __name__ == "__main__":
    main()