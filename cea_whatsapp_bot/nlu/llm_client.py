from typing import List, Optional
import os

class LLMClient:
    """Provider-agnostic LLM client. Defaults to OpenAI if key is present."""
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = os.getenv("OPENAI_API_KEY")

        # Lazy import to avoid dependency errors if not used
        self._openai = None
        if self.api_key:
            from openai import OpenAI
            self._openai = OpenAI(api_key=self.api_key)

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        if self._openai:
            msgs = []
            if system:
                msgs.append({ "role": "system", "content": system })
            msgs.append({ "role": "user", "content": prompt })
            resp = self._openai.chat.completions.create(model=self.model, messages=msgs, temperature=0.2)
            return resp.choices[0].message.content.strip()
        # Fallback stub
        return "Soy un asistente IA. Aún no tengo clave configurada; responde usando el menú o configura OPENAI_API_KEY."
