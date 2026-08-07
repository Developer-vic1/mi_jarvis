"""
macros/entorno_python.py — Macro modular para entornos de desarrollo Python.
"""

import logging
from nucleo.voz import hablar

logger = logging.getLogger("jarvis.macros.python")


def ejecutar_entorno_python() -> tuple[bool, str]:
    """Ejecuta la macro para preparar el entorno Python."""
    logger.info("Ejecutando macro MACRO_PYTHON")
    hablar("Preparando entorno de desarrollo Python.")
    return True, "Entorno Python iniciado."


def registrar() -> None:
    """Registra la macro en el gestor."""
    from macros.gestor_macros import registrar_macro
    registrar_macro("MACRO_PYTHON", ejecutar_entorno_python)
