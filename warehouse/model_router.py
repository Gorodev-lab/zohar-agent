"""
warehouse/model_router.py
Selección dinámica de modelos según el flujo de trabajo.
Gemini siempre es primario; modelos locales son fallback.
"""

from dataclasses import dataclass, field
from typing import Optional
import os

@dataclass
class ModelConfig:
    name: str
    endpoint: str           # "gemini" | URL HTTP local
    max_tokens: int
    temperature: float
    priority: int           # 1 = máxima prioridad
    extra: dict = field(default_factory=dict)


class ModelRouter:
    """Selecciona el modelo óptimo según el flujo de trabajo.

    Uso:
        model = ModelRouter.get_model("extraction")
        # En caso de error con el primario:
        fallback = ModelRouter.get_fallback("extraction")
    """

    WORKFLOWS: dict[str, dict] = {
        # Extracción estructurada de datos de PDFs de Gaceta Ecológica
        "extraction": {
            "primary": ModelConfig(
                name="gemini-2.0-flash",
                endpoint="gemini",
                max_tokens=2000,
                temperature=0.1,
                priority=1,
            ),
            "fallback": ModelConfig(
                name="DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf",
                endpoint="http://127.0.0.1:8001/v1/chat/completions",
                max_tokens=500,
                temperature=0.1,
                priority=2,
            ),
        },
        # Verificación con fuentes web (grounding)
        "grounding": {
            "primary": ModelConfig(
                name="gemini-2.0-flash",
                endpoint="gemini",
                max_tokens=2000,
                temperature=0.0,
                priority=1,
                extra={"grounding": True},
            ),
        },
        # OCR de imágenes dentro de PDFs
        "ocr": {
            "primary": ModelConfig(
                name="gemini-2.0-flash",
                endpoint="gemini",
                max_tokens=1500,
                temperature=0.0,
                priority=1,
            ),
            "fallback": ModelConfig(
                name="qwen-ocr",
                endpoint="http://127.0.0.1:8002/v1/chat/completions",
                max_tokens=500,
                temperature=0.1,
                priority=2,
            ),
        },
        # Auditoría y validación cruzada de registros
        "audit": {
            "primary": ModelConfig(
                name="gemini-2.0-flash",
                endpoint="gemini",
                max_tokens=3000,
                temperature=0.2,
                priority=1,
            ),
        },
        # Resumen rápido (tokens cortos)
        "summary": {
            "primary": ModelConfig(
                name="gemini-2.0-flash",
                endpoint="gemini",
                max_tokens=512,
                temperature=0.3,
                priority=1,
            ),
        },
    }

    @classmethod
    def get_model(cls, workflow: str, prefer_local: bool = False) -> ModelConfig:
        """Devuelve el modelo más adecuado para el flujo dado.

        Args:
            workflow: Nombre del flujo ("extraction", "grounding", "ocr", "audit", "summary")
            prefer_local: Si True, retorna el fallback local en vez del primario cloud
        """
        config = cls.WORKFLOWS.get(workflow, cls.WORKFLOWS["extraction"])
        if prefer_local and "fallback" in config:
            return config["fallback"]
        return config["primary"]

    @classmethod
    def get_fallback(cls, workflow: str) -> Optional[ModelConfig]:
        """Devuelve el modelo de fallback (local) para el flujo dado, o None si no hay."""
        config = cls.WORKFLOWS.get(workflow, {})
        return config.get("fallback")

    @classmethod
    def list_workflows(cls) -> list[str]:
        """Lista todos los flujos de trabajo disponibles."""
        return list(cls.WORKFLOWS.keys())

    @classmethod
    def get_active_model_name(cls, workflow: str = "extraction", prefer_local: bool = False) -> str:
        """Devuelve solo el nombre del modelo activo (útil para logging y dashboard)."""
        return cls.get_model(workflow, prefer_local).name


# ── Conveniencia: instancia singleton opcional ──────────────────────────────
router = ModelRouter()


if __name__ == "__main__":
    # Diagnóstico rápido
    for wf in ModelRouter.list_workflows():
        primary = ModelRouter.get_model(wf)
        fallback = ModelRouter.get_fallback(wf)
        fb_name = fallback.name if fallback else "—"
        print(f"[{wf:12s}] primary={primary.name:<30s} fallback={fb_name}")
