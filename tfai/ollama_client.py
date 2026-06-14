"""Client minimal pour l'API Ollama (http://localhost:11434)."""
from __future__ import annotations

import os

import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def chat(model: str, messages: list[dict], system: str | None = None) -> str:
    """Envoie une conversation à Ollama et retourne le texte de la réponse.

    `messages` est une liste de dicts {"role": "user"|"assistant", "content": str}.
    """
    full_messages = list(messages)
    if system:
        full_messages = [{"role": "system", "content": system}] + full_messages

    payload = {
        "model": model,
        "messages": full_messages,
        "stream": False,
    }

    resp = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=600)
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"]


def list_models() -> list[str]:
    """Retourne la liste des modèles disponibles localement dans Ollama."""
    resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
    resp.raise_for_status()
    return [m["name"] for m in resp.json().get("models", [])]
