"""
plugins/web.py — Plugin de búsqueda y navegación web de Jarvis.

Capacidades:
- Abrir sitios conocidos directamente (YouTube, Gmail, GitHub, etc.)
- Detectar URLs dictadas por el usuario y abrirlas
- Realizar búsquedas en Google
- Distinguir entre búsquedas y URLs directas
"""

import logging
import re
import subprocess
from urllib.parse import quote_plus

import plugins
from config import NAVEGADOR_CMD, SITIOS_CONOCIDOS
from rapidfuzz import fuzz, process as rfprocess  # type: ignore[import]

logger = logging.getLogger("jarvis.web")

# Patrón para detectar URLs dictadas directamente
URL_PATRON = re.compile(
    r"^(https?://)?"
    r"([a-z0-9\-]+\.)+[a-z]{2,}"
    r"(/[^\s]*)?$",
    re.IGNORECASE,
)


def _abrir_url(url: str) -> bool:
    """
    Abre una URL en el navegador predeterminado.

    Args:
        url: URL completa a abrir.

    Returns:
        True si se lanzó correctamente.
    """
    if not url.startswith("http"):
        url = "https://" + url
    try:
        subprocess.Popen([NAVEGADOR_CMD, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("URL abierta: %s", url)
        return True
    except Exception as e:
        logger.error("Error abriendo URL '%s': %s", url, e)
        return False


def _buscar_sitio_conocido(texto: str) -> tuple[str | None, str | None]:
    """
    Busca si el texto coincide con algún sitio conocido (fuzzy).

    Args:
        texto: Texto del usuario ya normalizado.

    Returns:
        Tupla (nombre_sitio, url) o (None, None) si no hay coincidencia.
    """
    nombres = list(SITIOS_CONOCIDOS.keys())

    # Búsqueda exacta primero
    for nombre in nombres:
        if nombre in texto:
            return nombre, SITIOS_CONOCIDOS[nombre]

    # Búsqueda fuzzy
    match = rfprocess.extractOne(
        texto, nombres, scorer=fuzz.partial_ratio, score_cutoff=70
    )
    if match:
        return match[0], SITIOS_CONOCIDOS[match[0]]

    return None, None


class PluginWeb(plugins.BasePlugin):
    """Plugin de búsqueda y navegación web."""

    def __init__(self) -> None:
        super().__init__(
            nombre="web",
            intenciones=["BUSCAR_WEB", "ABRIR_WEB"],
            descripcion=(
                "Navega a sitios web, abre páginas conocidas o realiza búsquedas. "
                "Ej: 'busca Python', 'abre YouTube', 've a github.com'."
            ),
            categoria="Web",
        )

    def manejar(self, intencion: str, entidades: dict, contexto: dict) -> str:
        if intencion == "ABRIR_WEB":
            sitio = entidades.get("sitio", "").strip()
            if not sitio:
                return "¿A qué sitio web deseas ir?"

            # ¿Es una URL directa?
            if URL_PATRON.match(sitio):
                if _abrir_url(sitio):
                    return f"Abriendo {sitio}."
                return f"No pude abrir {sitio}."

            # ¿Es un sitio conocido?
            nombre, url = _buscar_sitio_conocido(sitio)
            if url:
                if _abrir_url(url):
                    return f"Abriendo {nombre.title()}."
                return f"No pude abrir {nombre}."

            # Fallback: buscar en Google
            return self._buscar_google(sitio)

        elif intencion == "BUSCAR_WEB":
            query = entidades.get("query", "").strip()
            if not query:
                return "¿Qué deseas buscar?"
            return self._buscar_google(query)

        return "No sé cómo procesar esa solicitud web."

    def _buscar_google(self, query: str) -> str:
        """Realiza una búsqueda en Google."""
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        if _abrir_url(url):
            return f"Buscando '{query}' en Google."
        return "No pude abrir el navegador para la búsqueda."


plugins.registrar(PluginWeb())
