"""
plugins/ayuda.py — Plugin de ayuda interactiva de Jarvis.

Responde preguntas como:
- "¿qué puedes hacer?"
- "¿qué comandos conoces?"
- "ayuda"

Lista todos los plugins registrados agrupados por categoría.
"""

import logging

import plugins

logger = logging.getLogger("jarvis.ayuda")


class PluginAyuda(plugins.BasePlugin):
    """Plugin de ayuda que lista las capacidades de Jarvis."""

    def __init__(self) -> None:
        super().__init__(
            nombre="ayuda",
            intenciones=["AYUDA"],
            descripcion="Muestra qué puede hacer Jarvis y sus comandos disponibles.",
            categoria="Sistema",
        )

    def manejar(self, intencion: str, entidades: dict, contexto: dict) -> str:
        categorias = plugins.listar_por_categoria()

        if not categorias:
            return (
                "Soy Jarvis, tu asistente personal. "
                "Puedo abrir aplicaciones, buscar en internet, "
                "controlar el sistema y mucho más. "
                "Aún estoy cargando mis módulos."
            )

        partes = ["Estas son mis capacidades principales:"]

        for categoria, plugin_list in sorted(categorias.items()):
            if categoria == "Sistema" and "ayuda" in [p.nombre for p in plugin_list]:
                # Omitir el propio plugin de ayuda del listado
                plugin_list = [p for p in plugin_list if p.nombre != "ayuda"]
                if not plugin_list:
                    continue

            descs = [p.descripcion for p in plugin_list if p.descripcion]
            if descs:
                partes.append(f"En {categoria}: {'. '.join(descs)}")

        partes.append(
            "Para usar cualquier función, simplemente dímelo de forma natural. "
            "Por ejemplo: 'abre Chrome', 'busca Laravel', 'cuánto es raíz de 144', "
            "'qué hora es', 'sube el volumen'."
        )

        return " ".join(partes)


plugins.registrar(PluginAyuda())
