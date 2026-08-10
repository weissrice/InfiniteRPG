import httpx
from typing import Optional


class AIClient:
    """Client for communicating with the local AI API."""

    API_BASE = "http://127.0.0.1:1337"

    def __init__(
        self,
        model: str = "",
        timeout: float = 180.0,
    ):
        self.model = model
        self.client = httpx.Client(timeout=timeout)

    def _get_model(self) -> str:
        """Return the explicitly selected model or the server's loaded model."""

        if self.model:
            return self.model

        response = self.client.get(
            f"{self.API_BASE}/models"
        )

        response.raise_for_status()

        data = response.json()

        models = data.get("data", [])

        if not models:
            raise RuntimeError(
                "The AI server returned no loaded models."
            )

        return models[0]["id"]

    def ask(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> str:
        """Send a request to the local AI server."""

        messages = []

        if system:
            messages.append(
                {
                    "role": "system",
                    "content": system,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        request_data = {
            "model": self._get_model(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            request_data["response_format"] = {
                "type": "json_object"
            }

        response = self.client.post(
            f"{self.API_BASE}/chat/completions",
            json=request_data,
        )

        response.raise_for_status()

        data = response.json()

        choice = data["choices"][0]
        message = choice["message"]

        content = message.get("content", "")

        if not content:
            reasoning = message.get(
                "reasoning_content",
                "",
            )

            raise RuntimeError(
                "The AI returned no final response. "
                f"Finish reason: {choice.get('finish_reason')}. "
                f"Reasoning tokens present: {bool(reasoning)}"
            )

        return content

    def close(self):
        """Close the HTTP connection."""

        self.client.close()
