"""
macros/entorno_laravel.py — Macro modular para entornos de desarrollo Laravel genéricos.
"""

import logging
from nucleo.voz import hablar

logger = logging.getLogger("jarvis.macros.laravel")


def ejecutar_entorno_laravel() -> tuple[bool, str]:
    """Ejecuta la macro para preparar el entorno Laravel genérico."""
    logger.info("Ejecutando macro MACRO_LARAVEL")
    hablar("Preparando entorno de desarrollo Laravel.")
    return True, "Entorno Laravel iniciado."


def registrar() -> None:
    """Registra la macro en el gestor."""
    from macros.gestor_macros import registrar_macro
    registrar_macro("MACRO_LARAVEL", ejecutar_entorno_laravel)
