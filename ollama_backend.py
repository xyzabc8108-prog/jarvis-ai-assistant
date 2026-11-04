"""Local, loopback-only Ollama chat adapter for JARVIS."""
import httpx
from fastapi import HTTPException

OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"

async def ollama_chat(messages: list[dict[str, str]], model: str) -> str:
    # Deliberately fixed to localhost: never forward owner chats to arbitrary hosts.
    try:
        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            result = await client.post(
                OLLAMA_CHAT_URL,
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"num_ctx": 2048, "num_predict": 400},
                    "keep_alive": "5m",
                },
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=503, detail={
            "code": "ollama_timeout",
            "message": "Local AI timed out. Close memory-heavy apps or try llama3.2:1b."
        })
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail={
            "code": "ollama_offline",
            "message": "Ollama is not running on this PC. Start Ollama and try again."
        })

    if result.status_code == 404:
        raise HTTPException(status_code=503, detail={
            "code": "ollama_model_missing",
            "message": f"Local model is missing. Run: ollama pull {model}"
        })
    if result.status_code >= 400:
        raise HTTPException(status_code=503, detail={
            "code": "ollama_error",
            "message": "The local AI could not process the request. Check the Ollama application."
        })
    try:
        payload = result.json()
        answer = payload["message"]["content"]
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("empty model output")
        return answer.strip()
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail={
            "code": "ollama_response_invalid",
            "message": "Ollama returned an unexpected response."
        })
