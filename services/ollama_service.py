import os
import httpx
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")


class OllamaService:
    def __init__(self):
        self.base_url = OLLAMA_BASE_URL
        self.model = OLLAMA_MODEL

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, system: str = "") -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system
        try:
            resp = httpx.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=60.0,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            return f"[Ollama error: {e}]"
