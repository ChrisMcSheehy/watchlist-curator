import os
import pathlib

import requests
import yaml

CONFIG = pathlib.Path(__file__).resolve().parent.parent / "config" / "models.yaml"
URL = "https://openrouter.ai/api/v1/chat/completions"


def model_for(role):
    return yaml.safe_load(CONFIG.read_text())[role]


def complete(role, prompt, system=None, timeout=1800):
    """One OpenRouter chat completion. role is a key in models.yaml."""
    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    r = requests.post(
        URL,
        timeout=timeout,
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        json={"model": model_for(role), "messages": messages},
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
