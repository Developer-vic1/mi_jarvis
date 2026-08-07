"""
plugins/archivos.py — Plugin de gestión de archivos y carpetas de Jarvis.

CRUD completo sobre el sistema de archivos:
- Abrir carpetas en el gestor de archivos
- Crear carpetas y archivos
- Renombrar, mover, copiar, eliminar
- Buscar archivos
- Vaciar papelera
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import plugins
from config import CARPETAS_CONOCIDAS, HOME_DIR
from rapidfuzz import fuzz, process as rfprocess  # type: ignore[import]

logger = logging.getLogger("jarvis.archivos")

INTENCIONES = [
    "ABRIR_CARPETA", "CREAR_CARPETA", "CREAR_ARCHIVO",
    "RENOMBRAR", "MOVER", "COPIAR", "ELIMINAR", "BUSCAR_ARCHIVO",
]


def _resolver_carpeta(nombre: str) -> Optional[str]:
    """
    Resuelve el nombre de una carpeta conocida a su ruta absoluta.
    Usa fuzzy matching para mayor tolerancia.

    Args:
        nombre: Nombre de la carpeta (e.g. 'descargas', 'escritorio').

    Returns:
        Ruta absoluta o None si no se reconoce.
    """
    nombre_lower = nombre.lower().strip()

    # Búsqueda exacta
    if nombre_lower in CARPETAS_CONOCIDAS:
        return CARPETAS_CONOCIDAS[nombre_lower]

    # Búsqueda fuzzy
    match = rfprocess.extractOne(
        nombre_lower,
        list(CARPETAS_CONOCIDAS.keys()),
        scorer=fuzz.ratio,
        score_cutoff=70,
    )
    if match:
        return CARPETAS_CONOCIDAS[match[0]]

    # Intentar como ruta absoluta
    if nombre.startswith("/") and os.path.exists(nombre):
        return nombre

    # Intentar relativo al home
    ruta_home = os.path.join(HOME_DIR, nombre)
    if os.path.exists(ruta_home):
        return ruta_home

    return None


def _abrir_en_explorador(ruta: str) -> bool:
    """Abre una ruta en Nautilus (explorador de archivos)."""
    try:
        subprocess.Popen(["xdg-open", ruta], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        logger.error("Error abriendo explorador en '%s': %s", ruta, e)
        return False


class PluginArchivos(plugins.BasePlugin):
    """Plugin de gestión de archivos y carpetas para Ubuntu."""

    def __init__(self) -> None:
        super().__init__(
            nombre="archivos",
            intenciones=INTENCIONES,
            descripcion=(
                "Gestiona archivos y carpetas: crear, abrir, mover, copiar, "
                "renombrar, eliminar y buscar."
            ),
            categoria="Archivos",
        )
        # Contexto de operación pendiente (para confirmaciones)
        self._pendiente: dict = {}

    def manejar(self, intencion: str, entidades: dict, contexto: dict) -> str:
        handlers = {
            "ABRIR_CARPETA": self._abrir_carpeta,
            "CREAR_CARPETA": self._crear_carpeta,
            "CREAR_ARCHIVO": self._crear_archivo,
            "RENOMBRAR": self._renombrar,
            "MOVER": self._mover,
            "COPIAR": self._copiar,
            "ELIMINAR": self._eliminar,
            "BUSCAR_ARCHIVO": self._buscar_archivo,
        }
        handler = handlers.get(intencion)
        if handler:
            return handler(entidades, contexto)
        return "No reconocí ese comando de archivos."

    # ── Abrir carpeta ─────────────────────────────────────────────────────────

    def _abrir_carpeta(self, entidades: dict, contexto: dict) -> str:
        carpeta = entidades.get("carpeta", "").strip()

        if not carpeta:
            return "¿Qué carpeta deseas abrir?"

        ruta = _resolver_carpeta(carpeta)

        if not ruta:
            return f"No encontré la carpeta '{carpeta}'. ¿Puedes especificar la ruta?"

        if not os.path.exists(ruta):
            return f"La carpeta '{ruta}' no existe."

        if _abrir_en_explorador(ruta):
            nombre_amigable = os.path.basename(ruta) or ruta
            return f"Abriendo carpeta {nombre_amigable}."
        return "No pude abrir el explorador de archivos."

    # ── Crear carpeta ─────────────────────────────────────────────────────────

    def _crear_carpeta(self, entidades: dict, contexto: dict) -> str:
        nombre = entidades.get("nombre", "").strip()

        if not nombre:
            return "¿Cómo quieres llamar a la carpeta?"

        # Sanear nombre
        nombre_seguro = _sanear_nombre(nombre)
        if not nombre_seguro:
            return "Ese nombre no es válido para una carpeta."

        # Preguntar ubicación si no está especificada
        ubicacion = contexto.get("ubicacion_actual", HOME_DIR)
        ruta = os.path.join(ubicacion, nombre_seguro)

        try:
            os.makedirs(ruta, exist_ok=True)
            logger.info("Carpeta creada: %s", ruta)
            return f"Carpeta '{nombre_seguro}' creada correctamente."
        except PermissionError:
            return f"No tengo permisos para crear la carpeta en '{ubicacion}'."
        except Exception as e:
            logger.error("Error creando carpeta: %s", e)
            return "No pude crear la carpeta."

    # ── Crear archivo ─────────────────────────────────────────────────────────

    def _crear_archivo(self, entidades: dict, contexto: dict) -> str:
        nombre = entidades.get("nombre", "").strip()

        if not nombre:
            return "¿Cómo quieres llamar al archivo?"

        nombre_seguro = _sanear_nombre(nombre)
        if not nombre_seguro:
            return "Ese nombre no es válido para un archivo."

        ubicacion = contexto.get("ubicacion_actual", HOME_DIR)
        ruta = os.path.join(ubicacion, nombre_seguro)

        try:
            Path(ruta).touch(exist_ok=True)
            logger.info("Archivo creado: %s", ruta)
            return f"Archivo '{nombre_seguro}' creado correctamente."
        except PermissionError:
            return f"No tengo permisos para crear el archivo en '{ubicacion}'."
        except Exception as e:
            logger.error("Error creando archivo: %s", e)
            return "No pude crear el archivo."

    # ── Renombrar ─────────────────────────────────────────────────────────────

    def _renombrar(self, entidades: dict, contexto: dict) -> str:
        objeto = entidades.get("objeto", "").strip()

        if not objeto:
            return "¿Qué archivo o carpeta deseas renombrar, y con qué nombre?"

        # Intentar extraer "X a Y" o "X por Y" del objeto
        m_a = None
        for sep in [" a ", " por ", " como "]:
            if sep in objeto:
                partes = objeto.split(sep, 1)
                if len(partes) == 2:
                    m_a = partes
                    break

        if not m_a:
            return (
                "Para renombrar necesito saber el nombre actual y el nuevo nombre. "
                "Por ejemplo: 'renombra pruebas a desarrollo'."
            )

        nombre_actual, nombre_nuevo = m_a
        ubicacion = contexto.get("ubicacion_actual", HOME_DIR)

        ruta_actual = _buscar_local(nombre_actual.strip(), ubicacion)
        if not ruta_actual:
            return f"No encontré '{nombre_actual}' en {ubicacion}."

        nombre_nuevo_seguro = _sanear_nombre(nombre_nuevo.strip())
        ruta_nueva = os.path.join(os.path.dirname(ruta_actual), nombre_nuevo_seguro)

        try:
            os.rename(ruta_actual, ruta_nueva)
            return f"Renombrado correctamente a '{nombre_nuevo_seguro}'."
        except Exception as e:
            logger.error("Error renombrando: %s", e)
            return "No pude renombrar el elemento."

    # ── Mover ─────────────────────────────────────────────────────────────────

    def _mover(self, entidades: dict, contexto: dict) -> str:
        objeto = entidades.get("objeto", "").strip()

        if not objeto:
            return "¿Qué deseas mover y a dónde?"

        for sep in [" a ", " al ", " hacia ", " en "]:
            if sep in objeto:
                partes = objeto.split(sep, 1)
                if len(partes) == 2:
                    origen_nombre, destino_nombre = partes
                    ubicacion = contexto.get("ubicacion_actual", HOME_DIR)
                    ruta_origen = _buscar_local(origen_nombre.strip(), ubicacion)
                    if not ruta_origen:
                        return f"No encontré '{origen_nombre}'."
                    ruta_destino = _resolver_carpeta(destino_nombre.strip()) or \
                                   os.path.join(ubicacion, destino_nombre.strip())
                    try:
                        shutil.move(ruta_origen, ruta_destino)
                        return f"Movido correctamente a {os.path.basename(ruta_destino)}."
                    except Exception as e:
                        logger.error("Error moviendo: %s", e)
                        return "No pude mover el elemento."

        return "Para mover necesito saber el origen y destino. Ej: 'mueve proyecto al escritorio'."

    # ── Copiar ────────────────────────────────────────────────────────────────

    def _copiar(self, entidades: dict, contexto: dict) -> str:
        objeto = entidades.get("objeto", "").strip()
        if not objeto:
            return "¿Qué deseas copiar y a dónde?"

        for sep in [" a ", " al ", " en "]:
            if sep in objeto:
                partes = objeto.split(sep, 1)
                if len(partes) == 2:
                    origen_nombre, destino_nombre = partes
                    ubicacion = contexto.get("ubicacion_actual", HOME_DIR)
                    ruta_origen = _buscar_local(origen_nombre.strip(), ubicacion)
                    if not ruta_origen:
                        return f"No encontré '{origen_nombre}'."
                    ruta_destino = _resolver_carpeta(destino_nombre.strip()) or \
                                   os.path.join(ubicacion, destino_nombre.strip())
                    try:
                        if os.path.isdir(ruta_origen):
                            dest_path = os.path.join(ruta_destino, os.path.basename(ruta_origen))
                            shutil.copytree(ruta_origen, dest_path)
                        else:
                            shutil.copy2(ruta_origen, ruta_destino)
                        return "Copiado correctamente."
                    except Exception as e:
                        logger.error("Error copiando: %s", e)
                        return "No pude copiar el elemento."

        return "Para copiar necesito origen y destino. Ej: 'copia proyecto a descargas'."

    # ── Eliminar ──────────────────────────────────────────────────────────────

    def _eliminar(self, entidades: dict, contexto: dict) -> str:
        objeto = entidades.get("objeto", "").strip()

        if not objeto:
            return "¿Qué deseas eliminar?"

        # Buscar en el directorio actual del contexto
        ubicacion = contexto.get("ubicacion_actual", HOME_DIR)
        ruta = _buscar_local(objeto, ubicacion)

        if not ruta:
            return f"No encontré '{objeto}' en {ubicacion}. ¿Puedes indicar la ruta?"

        # Pedir confirmación
        nombre_base = os.path.basename(ruta)
        tipo = "carpeta" if os.path.isdir(ruta) else "archivo"
        contexto["_confirmar_eliminar"] = ruta
        return (
            f"¿Confirmas que deseas eliminar la {tipo} '{nombre_base}'? "
            f"Di 'sí' para confirmar o 'no' para cancelar."
        )

    def confirmar_eliminar(self, ruta: str) -> str:
        """Ejecuta la eliminación tras confirmación del usuario."""
        try:
            if os.path.isdir(ruta):
                shutil.rmtree(ruta)
            else:
                os.remove(ruta)
            nombre_base = os.path.basename(ruta)
            logger.info("Eliminado: %s", ruta)
            return f"'{nombre_base}' eliminado correctamente."
        except PermissionError:
            return "No tengo permisos para eliminar ese elemento."
        except Exception as e:
            logger.error("Error eliminando '%s': %s", ruta, e)
            return "No pude eliminar el elemento."

    # ── Buscar archivo ────────────────────────────────────────────────────────

    def _buscar_archivo(self, entidades: dict, contexto: dict) -> str:
        objeto = entidades.get("objeto", "").strip()

        if not objeto:
            return "¿Qué archivo o carpeta deseas buscar?"

        ubicacion = contexto.get("ubicacion_actual", HOME_DIR)

        try:
            result = subprocess.run(
                ["find", ubicacion, "-iname", f"*{objeto}*", "-maxdepth", "5"],
                capture_output=True, text=True, timeout=10,
            )
            lineas = [l for l in result.stdout.strip().split("\n") if l]
            if not lineas:
                return f"No encontré ningún archivo llamado '{objeto}'."
            if len(lineas) == 1:
                return f"Encontré: {lineas[0]}"
            lista = "\n".join(lineas[:5])
            return f"Encontré {len(lineas)} coincidencias. Las primeras son:\n{lista}"
        except subprocess.TimeoutExpired:
            return "La búsqueda tardó demasiado. Intenta en una carpeta más específica."
        except Exception as e:
            logger.error("Error buscando archivo: %s", e)
            return "No pude realizar la búsqueda."


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────────────────────

def _sanear_nombre(nombre: str) -> str:
    """
    Sanea un nombre de archivo/carpeta eliminando caracteres peligrosos.

    Args:
        nombre: Nombre propuesto por el usuario.

    Returns:
        Nombre saneado, o string vacío si es inválido.
    """
    import re
    # Eliminar caracteres no permitidos en sistemas de archivos
    nombre = re.sub(r"[/\\:*?\"<>|]", "", nombre)
    nombre = nombre.strip(". ")
    return nombre[:255]  # límite de nombre en ext4


def _buscar_local(nombre: str, directorio: str, maxdepth: int = 2) -> Optional[str]:
    """
    Busca un archivo o carpeta por nombre en el directorio dado.

    Args:
        nombre: Nombre a buscar.
        directorio: Directorio donde buscar.
        maxdepth: Profundidad máxima de búsqueda.

    Returns:
        Ruta absoluta si se encontró, None si no.
    """
    try:
        result = subprocess.run(
            ["find", directorio, "-iname", nombre, "-maxdepth", str(maxdepth)],
            capture_output=True, text=True, timeout=5,
        )
        lineas = [l for l in result.stdout.strip().split("\n") if l]
        return lineas[0] if lineas else None
    except Exception as e:
        logger.debug("Error en _buscar_local: %s", e)
        return None


plugins.registrar(PluginArchivos())
