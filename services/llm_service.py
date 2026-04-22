import os
from groq import Groq


def _get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    return os.getenv(key, default)


def generate(prompt: str, system: str = "") -> str:
    api_key = _get_secret("GROQ_API_KEY")
    model = _get_secret("GROQ_MODEL", "llama3-8b-8192")

    if not api_key:
        return (
            "GROQ_API_KEY is not configured. "
            "Get a free key at console.groq.com and add it to your secrets."
        )

    client = Groq(api_key=api_key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=512,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[LLM error: {e}]"
