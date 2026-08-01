import httpx
import json


API_URL = "http://127.0.0.1:1337/v1/chat/completions"
MODEL = "Qwen3.5-4B-UD-Q4_K_XL.gguf"


def main():
    response = httpx.post(
        API_URL,
        json={
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an RPG action interpreter. "
                        "Return ONLY valid JSON. "
                        "Do not explain your reasoning."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        'Return JSON for the action: "Go outside." '
                        'Use this exact structure: '
                        '{"narration":"...","actions":[{"type":"move","destination":"outside"}]}'
                    ),
                },
            ],
            "temperature": 0.2,
            "max_tokens": 4096,

            # Ask the backend/model not to spend tokens on reasoning.
            "reasoning_effort": "none",
        },
        timeout=180,
    )

    response.raise_for_status()

    data = response.json()

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()