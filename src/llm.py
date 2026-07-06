import os
import pathlib

import requests
import yaml

CONFIG = pathlib.Path(__file__).resolve().parent.parent / "config" / "models.yaml"
URL = "https://openrouter.ai/api/v1/chat/completions"


def model_for(role):
    return yaml.safe_load(CONFIG.read_text())[role]


def _citation_urls(data):
    """Perplexity/Sonar return source URLs out-of-band, not inline in content.

    OpenRouter exposes them either as a top-level `citations` list of URL strings
    or as OpenAI-style `annotations` (url_citation) on the message. Return [] if none.
    """
    msg = data["choices"][0]["message"]
    urls = data.get("citations")
    if not urls:
        urls = [a.get("url_citation", {}).get("url")
                for a in (msg.get("annotations") or [])]
    return [u for u in (urls or []) if isinstance(u, str)]


def complete(role, prompt, system=None, timeout=1800, with_citations=False):
    """One OpenRouter chat completion. role is a key in models.yaml.

    with_citations=True appends a numbered Sources list so [n] markers from
    research models resolve to real URLs. Leave False for JSON-returning calls.
    """
    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    r = requests.post(
        URL,
        timeout=timeout,
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        json={"model": model_for(role), "messages": messages},
    )
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    if with_citations:
        urls = _citation_urls(data)
        if urls:
            content += "\n\nSources:\n" + "\n".join(
                f"[{i + 1}] {u}" for i, u in enumerate(urls))
    return content
