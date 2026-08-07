"""
plugins/definiciones.py — Plugin de definiciones del diccionario.

Usa la API pública de dictionaryapi.dev para obtener definiciones en español.
Fallback a wiktionary si la primera API falla.
"""

import logging
from typing import Optional

import requests  # type: ignore[import]

import plugins

logger = logging.getLogger("jarvis.definiciones")

API_URL = "https://api.dictionaryapi.dev/api/v2/entries/es/{palabra}"
API_WIKTIONARY = "https://es.wiktionary.org/api/rest_v1/page/definition/{palabra}"
TIMEOUT_API = 6  # segundos


def _buscar_dictionaryapi(palabra: str) -> Optional[str]:
    """
    Consulta dictionaryapi.dev para obtener la definición en español.

    Args:
        palabra: Palabra a definir.

    Returns:
        Definición encontrada o None.
    """
    try:
        resp = requests.get(
            API_URL.format(palabra=palabra.lower()),
            timeout=TIMEOUT_API,
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        if isinstance(data, list) and data:
            meanings = data[0].get("meanings", [])
            for meaning in meanings:
                defs = meaning.get("definitions", [])
                if defs:
                    definicion = defs[0].get("definition", "")
                    ejemplo = defs[0].get("example", "")
                    resultado = definicion
                    if ejemplo:
                        resultado += f" Ejemplo: '{ejemplo}'."
                    return resultado
    except requests.RequestException as e:
        logger.warning("Error en dictionaryapi: %s", e)
    except Exception as e:
        logger.error("Error inesperado en definiciones: %s", e)
    return None


def _buscar_wiktionary(palabra: str) -> Optional[str]:
    """
    Consulta la API de Wiktionary en español como fallback.

    Args:
        palabra: Palabra a definir.

    Returns:
        Definición encontrada o None.
    """
    try:
        resp = requests.get(
            API_WIKTIONARY.format(palabra=palabra.lower()),
            timeout=TIMEOUT_API,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        for parte_oracion, definiciones in data.items():
            if isinstance(definiciones, list) and definiciones:
                primera = definiciones[0]
                if isinstance(primera, dict):
                    definicion = primera.get("definition", "")
                    if definicion:
                        # Limpiar HTML básico
                        import re
                        definicion = re.sub(r"<[^>]+>", "", definicion).strip()
                        return definicion
    except requests.RequestException as e:
        logger.warning("Error en Wiktionary: %s", e)
    except Exception as e:
        logger.error("Error inesperado en Wiktionary: %s", e)
    return None


class PluginDefiniciones(plugins.BasePlugin):
    """Plugin de definiciones usando APIs de diccionario libres."""

    def __init__(self) -> None:
        super().__init__(
            nombre="definiciones",
            intenciones=["DEFINIR"],
            descripcion=(
                "Define palabras usando diccionarios en línea. "
                "Ej: '¿qué significa algoritmo?', 'define resiliencia'."
            ),
            categoria="Información",
        )

    def manejar(self, intencion: str, entidades: dict, contexto: dict) -> str:
        palabra = entidades.get("palabra", "").strip()

        if not palabra:
            return "¿Qué palabra deseas que defina?"

        # Limpiar artículos y partículas comunes
        import re
        palabra = re.sub(r"^(la\s+|el\s+|los\s+|las\s+|un\s+|una\s+)", "", palabra).strip()

        logger.info("Buscando definición de: '%s'", palabra)

        # Intentar primera API
        definicion = _buscar_dictionaryapi(palabra)

        # Fallback a Wiktionary
        if not definicion:
            definicion = _buscar_wiktionary(palabra)

        if definicion:
            return f"{palabra.capitalize()}: {definicion}"
        else:
            return (
                f"No encontré una definición para '{palabra}'. "
                f"Puede que sea un término muy especializado o un nombre propio."
            )


plugins.registrar(PluginDefiniciones())
