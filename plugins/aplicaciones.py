"""
plugins/aplicaciones.py — Plugin de apertura de aplicaciones instaladas en Ubuntu.

Genera automáticamente un índice de todas las apps instaladas leyendo los
archivos .desktop del sistema. Usa rapidfuzz para encontrar apps aunque el
usuario diga el nombre con errores o de forma aproximada.

No requiere hardcodear ninguna aplicación manualmente.
"""

import configparser
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz, process as rfprocess  # type: ignore[import]

import plugins
from config import (
    APPS_DESKTOP_DIRS,
    APPS_INDEX_PATH,
    APPS_INDEX_MAX_AGE_HOURS,
    UMBRAL_FUZZY,
)

logger = logging.getLogger("jarvis.apps")


# ─────────────────────────────────────────────────────────────────────────────
# ESTRUCTURAS DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AppEntry:
    """Representa una aplicación instalada en el sistema."""
    nombre: str                          # Nombre oficial (e.g. "Google Chrome")
    exec_cmd: str                        # Comando Exec del .desktop
    aliases: list[str] = field(default_factory=list)  # Aliases de búsqueda
    icono: str = ""
    categorias: str = ""

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "exec_cmd": self.exec_cmd,
            "aliases": self.aliases,
            "icono": self.icono,
            "categorias": self.categorias,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AppEntry":
        return cls(
            nombre=d.get("nombre", ""),
            exec_cmd=d.get("exec_cmd", ""),
            aliases=d.get("aliases", []),
            icono=d.get("icono", ""),
            categorias=d.get("categorias", ""),
        )


# ─────────────────────────────────────────────────────────────────────────────
# ALIASES MANUALES — Para apps con nombres difíciles de inferir del .desktop
# ─────────────────────────────────────────────────────────────────────────────
ALIASES_EXTRA: dict[str, list[str]] = {
    "Google Chrome": ["chrome", "google chrome", "navegador", "chromium"],
    "Opera GX": ["opera", "opera gx", "navegador opera"],
    "Firefox": ["firefox", "navegador firefox", "mozilla"],
    "Docker Desktop": ["docker", "contenedores", "docker desktop"],
    "Tilix": ["tilix", "terminal", "consola", "tilix terminal"],
    "Terminal": ["terminal gnome", "gnome terminal", "consola gnome"],
    "Warp": ["warp", "warp terminal"],
    "Visual Studio Code": ["vscode", "vs code", "visual studio", "code", "editor"],
    "Code": ["vscode", "vs code", "visual studio", "editor de codigo"],
    "PyCharm": ["pycharm", "py charm", "ide python"],
    "Android Studio": ["android studio", "android", "ide android"],
    "pgAdmin 4": ["pgadmin", "postgres admin", "base de datos", "pg admin"],
    "Postman": ["postman", "api tester", "rest client"],
    "Discord": ["discord"],
    "Telegram": ["telegram"],
    "Spotify": ["spotify", "musica"],
    "OBS Studio": ["obs", "obs studio", "grabacion", "streaming"],
    "Steam": ["steam", "juegos"],
    "VirtualBox": ["virtualbox", "virtual box", "maquina virtual"],
    "System Monitor": ["monitor", "system monitor", "monitor del sistema"],
    "GNOME System Monitor": ["monitor", "gnome monitor", "procesos"],
    "Files": ["archivos", "explorador", "nautilus", "files"],
    "Settings": ["configuracion", "ajustes", "settings"],
    "Software": ["software", "tienda", "gnome software"],
    "Calculator": ["calculadora", "calculator"],
    "Text Editor": ["editor de texto", "text editor", "bloc de notas"],
    "Image Viewer": ["visor de imagenes", "galeria", "fotos"],
    "Document Viewer": ["visor de documentos", "evince", "pdf"],
    "Htop": ["htop", "monitor procesos", "top"],
    "Antigravity IDE": ["antigravity", "ide", "antigravity ide"],
    "Antigravity": ["antigravity"],
    "WhatsApp Web": ["whatsapp", "whatsapp web"],
    "Clocks": ["reloj", "alarma", "clocks"],
    "Tweaks": ["tweaks", "ajustes gnome", "personalizacion"],
}


# ─────────────────────────────────────────────────────────────────────────────
# GENERADOR DE ÍNDICE
# ─────────────────────────────────────────────────────────────────────────────

def _limpiar_exec(exec_cmd: str) -> list[str]:
    """
    Limpia el campo Exec del archivo .desktop.

    Elimina placeholders (%U, %F, %i, etc.) y devuelve lista de argumentos.
    """
    # Eliminar placeholders de freedesktop
    exec_cmd = re.sub(r"%[uUfFdDnNickvm]", "", exec_cmd).strip()
    # Dividir en lista respetando comillas
    import shlex
    try:
        return shlex.split(exec_cmd)
    except ValueError:
        return exec_cmd.split()


def _generar_aliases(nombre: str) -> list[str]:
    """
    Genera aliases de búsqueda a partir del nombre oficial de la app.

    Args:
        nombre: Nombre oficial de la aplicación.

    Returns:
        Lista de aliases en minúsculas.
    """
    nombre_lower = nombre.lower()
    aliases = [nombre_lower]

    # Agregar cada palabra del nombre como alias
    palabras = re.split(r"[\s\-_]+", nombre_lower)
    for p in palabras:
        if len(p) > 2:
            aliases.append(p)

    # Agregar alias manuales si existen
    for nombre_manual, alias_lista in ALIASES_EXTRA.items():
        if nombre_manual.lower() == nombre_lower:
            aliases.extend(alias_lista)
            break

    return list(set(aliases))


def construir_indice() -> list[AppEntry]:
    """
    Lee todos los archivos .desktop del sistema y construye el índice de apps.

    Returns:
        Lista de AppEntry con todas las aplicaciones instaladas.
    """
    apps: list[AppEntry] = []
    nombres_vistos: set[str] = set()

    for directorio in APPS_DESKTOP_DIRS:
        if not os.path.exists(directorio):
            continue

        for archivo in sorted(os.listdir(directorio)):
            if not archivo.endswith(".desktop"):
                continue

            ruta = os.path.join(directorio, archivo)
            try:
                config = configparser.ConfigParser(interpolation=None)
                config.read(ruta, encoding="utf-8")

                if not config.has_section("Desktop Entry"):
                    continue
                if config.getboolean("Desktop Entry", "NoDisplay", fallback=False):
                    continue
                if config.getboolean("Desktop Entry", "Hidden", fallback=False):
                    continue

                nombre = config.get("Desktop Entry", "Name", fallback="").strip()
                exec_cmd = config.get("Desktop Entry", "Exec", fallback="").strip()

                if not nombre or not exec_cmd or nombre in nombres_vistos:
                    continue

                nombres_vistos.add(nombre)
                entry = AppEntry(
                    nombre=nombre,
                    exec_cmd=exec_cmd,
                    aliases=_generar_aliases(nombre),
                    icono=config.get("Desktop Entry", "Icon", fallback=""),
                    categorias=config.get("Desktop Entry", "Categories", fallback=""),
                )
                apps.append(entry)

            except Exception as e:
                logger.debug("Error leyendo .desktop '%s': %s", archivo, e)

    logger.info("Índice de apps construido: %d aplicaciones.", len(apps))
    return apps


def guardar_indice(apps: list[AppEntry]) -> None:
    """Persiste el índice de apps en JSON."""
    os.makedirs(os.path.dirname(APPS_INDEX_PATH), exist_ok=True)
    data = {
        "generado_en": time.time(),
        "apps": [a.to_dict() for a in apps],
    }
    with open(APPS_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Índice guardado en %s", APPS_INDEX_PATH)


def cargar_indice() -> list[AppEntry]:
    """
    Carga el índice de apps desde JSON.
    Si no existe o es muy antiguo, lo regenera.

    Returns:
        Lista de AppEntry.
    """
    if os.path.exists(APPS_INDEX_PATH):
        try:
            with open(APPS_INDEX_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            generado_en = data.get("generado_en", 0)
            edad_horas = (time.time() - generado_en) / 3600
            if edad_horas < APPS_INDEX_MAX_AGE_HOURS:
                apps = [AppEntry.from_dict(d) for d in data.get("apps", [])]
                logger.info("Índice cargado: %d apps (%.1fh de antigüedad).", len(apps), edad_horas)
                return apps
        except Exception as e:
            logger.warning("Error cargando índice: %s. Regenerando...", e)

    apps = construir_indice()
    guardar_indice(apps)
    return apps


# ─────────────────────────────────────────────────────────────────────────────
# BÚSQUEDA FUZZY DE APPS
# ─────────────────────────────────────────────────────────────────────────────

class GestorApps:
    """Gestiona el índice de apps y realiza búsquedas fuzzy."""

    def __init__(self) -> None:
        self._apps: list[AppEntry] = []
        self._aliases_planos: list[tuple[str, AppEntry]] = []
        self._cargado = False

    def _cargar(self) -> None:
        if not self._cargado:
            self._apps = cargar_indice()
            self._aliases_planos = [
                (alias, app)
                for app in self._apps
                for alias in app.aliases
            ]
            self._cargado = True

    def buscar(self, nombre: str, umbral: int = UMBRAL_FUZZY) -> Optional[AppEntry]:
        """
        Busca la aplicación más cercana al nombre dado usando fuzzy matching.

        Args:
            nombre: Nombre o alias de la app a buscar.
            umbral: Score mínimo de coincidencia.

        Returns:
            AppEntry si se encontró coincidencia, None si no.
        """
        self._cargar()

        if not nombre.strip():
            return None

        nombre_lower = nombre.lower().strip()
        aliases_lista = [a for a, _ in self._aliases_planos]

        # Búsqueda exacta primero
        for alias, app in self._aliases_planos:
            if alias == nombre_lower:
                logger.info("App encontrada (exacta): '%s' → '%s'", nombre, app.nombre)
                return app

        # Búsqueda fuzzy
        match = rfprocess.extractOne(
            nombre_lower,
            aliases_lista,
            scorer=fuzz.WRatio,
            score_cutoff=umbral,
        )

        if match:
            idx = aliases_lista.index(match[0])
            app = self._aliases_planos[idx][1]
            logger.info(
                "App encontrada (fuzzy): '%s' → '%s' (score=%.0f)",
                nombre, app.nombre, match[1],
            )
            return app

        logger.info("App no encontrada: '%s'", nombre)
        return None

    def listar_nombres(self) -> list[str]:
        """Devuelve nombres oficiales de todas las apps indexadas."""
        self._cargar()
        return [a.nombre for a in self._apps]

    def regenerar(self) -> int:
        """Fuerza regeneración del índice."""
        apps = construir_indice()
        guardar_indice(apps)
        self._apps = apps
        self._aliases_planos = [
            (alias, app) for app in self._apps for alias in app.aliases
        ]
        self._cargado = True
        return len(apps)


_gestor_apps = GestorApps()


def abrir_app(entry: AppEntry) -> bool:
    """
    Abre o enfoca una aplicación consultando primero el estado del sistema.

    Args:
        entry: AppEntry de la aplicación a lanzar/enfocar.

    Returns:
        True si se abrió o enfocó correctamente, False si hubo error.
    """
    from modulos.gestor_aplicaciones import gestor_apps_sistema

    # 1. Comprobar si ya existe ventana para esta aplicación o sus aliases
    nombres_a_buscar = [entry.nombre] + entry.aliases
    for n in nombres_a_buscar:
        v = gestor_apps_sistema.buscar_ventana(n)
        if v:
            logger.info("Ventana existente encontrada para '%s'. Enfocando...", entry.nombre)
            return gestor_apps_sistema.enfocar_ventana(v.window_id)

    # 2. Si no existe ventana, abrir la aplicación usando GestorAplicaciones
    ok, _ = gestor_apps_sistema.abrir_aplicacion(entry.nombre, entry.exec_cmd)
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# PLUGIN
# ─────────────────────────────────────────────────────────────────────────────

class PluginAplicaciones(plugins.BasePlugin):
    """Plugin para abrir aplicaciones instaladas en Ubuntu."""

    def __init__(self) -> None:
        super().__init__(
            nombre="aplicaciones",
            intenciones=["ABRIR_APP"],
            descripcion="Abre cualquier aplicación instalada en tu sistema.",
            categoria="Sistema",
        )
        self._gestor = _gestor_apps

    def manejar(self, intencion: str, entidades: dict, contexto: dict) -> str:
        from nucleo.memoria import registrar_app_usada
        from modulos.gestor_aplicaciones import gestor_apps_sistema

        nombre_app = entidades.get("app", "").strip()

        if not nombre_app:
            return "¿Qué aplicación deseas abrir?"

        # Verificar primero si ya existe ventana abierta en el escritorio
        v_existente = gestor_apps_sistema.buscar_ventana(nombre_app)
        if v_existente:
            gestor_apps_sistema.enfocar_ventana(v_existente.window_id)
            nombre_amigable = gestor_apps_sistema.obtener_nombre_amigable_app(v_existente.to_dict())
            registrar_app_usada(nombre_amigable)
            return f"Cambiando a {nombre_amigable}."

        entry = self._gestor.buscar(nombre_app)

        if not entry:
            # Si no está en el índice .desktop, intentar gestor de aplicaciones directo
            ok, msg = gestor_apps_sistema.abrir_aplicacion(nombre_app)
            if ok:
                registrar_app_usada(nombre_app)
                return f"__abriendo__{nombre_app}"
            return f"No encontré ninguna aplicación llamada '{nombre_app}'. ¿Puedes intentarlo con otro nombre?"

        if abrir_app(entry):
            registrar_app_usada(entry.nombre)
            return f"__abriendo__{entry.nombre}"  # señal para que voz use contexto 'abriendo'
        else:
            return f"No pude abrir {entry.nombre}. Puede que el programa no esté disponible."


# Registro automático al importar este módulo
plugins.registrar(PluginAplicaciones())
