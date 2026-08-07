"""
macros/entorno_flutter.py — Macro modular para entornos de desarrollo Flutter.
"""

import logging
from nucleo.voz import hablar

logger = logging.getLogger("jarvis.macros.flutter")


def ejecutar_entorno_flutter() -> tuple[bool, str]:
    """Ejecuta la macro para preparar el entorno Flutter."""
    logger.info("Ejecutando macro MACRO_FLUTTER")
    hablar("Preparando entorno de desarrollo Flutter.")
    return True, "Entorno Flutter iniciado."


def registrar() -> None:
    """Registra la macro en el gestor."""
    from macros.gestor_macros import registrar_macro
    registrar_macro("MACRO_FLUTTER", ejecutar_entorno_flutter)
