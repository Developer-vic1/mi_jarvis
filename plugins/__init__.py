"""
plugins/__init__.py — Sistema de registro automático de plugins de Jarvis.

Cada plugin es un módulo en este directorio que:
1. Define una clase que hereda de BasePlugin.
2. Se auto-registra al importarse.

Para agregar una nueva habilidad a Jarvis, simplemente crea un archivo
en este directorio. No es necesario modificar cerebro.py ni main.py.
"""

import importlib
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("jarvis.plugins")

# ─────────────────────────────────────────────────────────────────────────────
# BASE PLUGIN
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BasePlugin(ABC):
    """
    Clase base que deben heredar todos los plugins de Jarvis.

    Atributos:
        nombre: Identificador único del plugin.
        intenciones: Lista de intenciones que este plugin maneja.
        descripcion: Descripción breve para el comando de ayuda.
    """
    nombre: str
    intenciones: list[str]
    descripcion: str = ""
    categoria: str = "General"

    @abstractmethod
    def manejar(
        self,
        intencion: str,
        entidades: dict,
        contexto: dict,
    ) -> str:
        """
        Procesa una intención y devuelve una respuesta textual.

        Args:
            intencion: Intención detectada por NLP (e.g. 'ABRIR_APP').
            entidades: Diccionario de entidades extraídas.
            contexto: Diccionario de contexto de la sesión actual.

        Returns:
            Texto de respuesta para hablar/mostrar al usuario.
        """
        ...

    def puede_manejar(self, intencion: str) -> bool:
        """Devuelve True si este plugin maneja la intención dada."""
        return intencion in self.intenciones


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRO DE PLUGINS
# ─────────────────────────────────────────────────────────────────────────────

# Diccionario: intención → plugin
_REGISTRO: dict[str, BasePlugin] = {}
# Lista de todos los plugins (para ayuda y listado)
_PLUGINS: list[BasePlugin] = []


def registrar(plugin: BasePlugin) -> None:
    """
    Registra un plugin en el sistema.

    Asocia cada intención declarada por el plugin a su instancia.

    Args:
        plugin: Instancia de BasePlugin a registrar.
    """
    for intencion in plugin.intenciones:
        if intencion in _REGISTRO:
            logger.warning(
                "Intención '%s' ya registrada por '%s'. Será reemplazada por '%s'.",
                intencion, _REGISTRO[intencion].nombre, plugin.nombre,
            )
        _REGISTRO[intencion] = plugin
        logger.debug("Plugin '%s' registró intención '%s'.", plugin.nombre, intencion)

    if plugin not in _PLUGINS:
        _PLUGINS.append(plugin)
    logger.info("Plugin registrado: '%s' (%d intenciones).", plugin.nombre, len(plugin.intenciones))


def obtener_plugin(intencion: str) -> Optional[BasePlugin]:
    """
    Busca el plugin que maneja la intención dada.

    Args:
        intencion: Nombre de la intención.

    Returns:
        Plugin correspondiente o None si no hay registro.
    """
    return _REGISTRO.get(intencion)


def listar_plugins() -> list[BasePlugin]:
    """Devuelve la lista de todos los plugins registrados."""
    return list(_PLUGINS)


def listar_por_categoria() -> dict[str, list[BasePlugin]]:
    """Agrupa los plugins por categoría para el comando de ayuda."""
    categorias: dict[str, list[BasePlugin]] = {}
    for plugin in _PLUGINS:
        cat = plugin.categoria
        categorias.setdefault(cat, []).append(plugin)
    return categorias


def cargar_todos() -> int:
    """
    Importa automáticamente todos los módulos en el directorio plugins/.

    Cada módulo que defina plugins (clases con @registrar) los registrará
    automáticamente al ser importado.

    Returns:
        Número de plugins registrados exitosamente.
    """
    plugins_dir = os.path.dirname(os.path.abspath(__file__))
    count_antes = len(_PLUGINS)

    archivos = [
        f[:-3]
        for f in os.listdir(plugins_dir)
        if f.endswith(".py")
        and f != "__init__.py"
        and not f.startswith("_")
    ]

    for nombre_modulo in sorted(archivos):
        try:
            importlib.import_module(f"plugins.{nombre_modulo}")
            logger.debug("Módulo de plugin cargado: %s", nombre_modulo)
        except Exception as e:
            logger.error("Error cargando plugin '%s': %s", nombre_modulo, e)

    count_cargados = len(_PLUGINS) - count_antes
    logger.info("Plugins cargados: %d nuevos (%d total).", count_cargados, len(_PLUGINS))
    return count_cargados
