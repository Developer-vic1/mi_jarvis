"""
macros/gestor_macros.py — Gestor de Macros de Jarvis.

Permite registrar y coordinar la ejecución de macros compuestas de desarrollo.
"""

import logging
import time
from typing import Callable

logger = logging.getLogger("jarvis.macros.gestor")

# Registro global de macros: intencion -> función ejecutora
_REGISTRO_MACROS: dict[str, Callable[[], tuple[bool, str]]] = {}


def registrar_macro(intencion: str, funcion: Callable[[], tuple[bool, str]]) -> None:
    """
    Registra una macro asociada a una intención NLP.

    Args:
        intencion: Nombre de la intención (ej. ABRIR_INTEGRADOR).
        funcion: Función que ejecuta la macro y retorna (éxito: bool, mensaje: str).
    """
    _REGISTRO_MACROS[intencion] = funcion
    logger.info("Macro registrada correctamente: %s", intencion)


def es_macro(intencion: str) -> bool:
    """Retorna True si la intención corresponde a una macro registrada."""
    return intencion in _REGISTRO_MACROS


def ejecutar_macro(intencion: str) -> tuple[bool, str]:
    """
    Ejecuta la macro solicitada midiendo tiempos y registrando logs.

    Args:
        intencion: Intención identificada por el NLP.

    Returns:
        Tupla (éxito: bool, mensaje: str).
    """
    if intencion not in _REGISTRO_MACROS:
        msg = f"No existe una macro registrada para la intención: '{intencion}'"
        logger.error(msg)
        return False, msg

    logger.info("Iniciando ejecución de macro: %s", intencion)
    inicio = time.time()
    try:
        exito, resultado = _REGISTRO_MACROS[intencion]()
        duracion = time.time() - inicio
        logger.info(
            "Macro '%s' finalizada en %.2f segundos. Éxito: %s",
            intencion, duracion, exito
        )
        return exito, resultado
    except Exception as e:
        duracion = time.time() - inicio
        msg_err = f"Error no controlado en la macro '{intencion}' tras {duracion:.2f}s: {e}"
        logger.error(msg_err, exc_info=True)
        return False, msg_err


def cargar_macros() -> None:
    """Carga e inicializa todos los módulos de macros disponibles."""
    try:
        from macros.abrir_integrador import registrar as reg_integrador
        reg_integrador()
    except Exception as e:
        logger.error("Error al cargar macro abrir_integrador: %s", e)

    try:
        from macros.entorno_flutter import registrar as reg_flutter
        reg_flutter()
    except Exception as e:
        logger.error("Error al cargar macro entorno_flutter: %s", e)

    try:
        from macros.entorno_python import registrar as reg_python
        reg_python()
    except Exception as e:
        logger.error("Error al cargar macro entorno_python: %s", e)

    try:
        from macros.entorno_laravel import registrar as reg_laravel
        reg_laravel()
    except Exception as e:
        logger.error("Error al cargar macro entorno_laravel: %s", e)

    logger.info("Todas las macros han sido cargadas. Total registradas: %d", len(_REGISTRO_MACROS))
