"""
nucleo/memoria.py — Módulo de memoria persistente de Jarvis.

Usa SQLite (stdlib, sin dependencias externas) para almacenar:
- Historial de interacciones
- Preferencias del usuario
- Alias personalizados
- Proyectos y rutas recientes

Todas las operaciones son tolerantes a fallos: nunca propagan excepciones
hacia el sistema principal.
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Generator, Optional

from config import DB_PATH, ALIAS_PATH, HISTORIAL_MAX_ROWS

logger = logging.getLogger("jarvis.memoria")


# ─────────────────────────────────────────────────────────────────────────────
# DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EntradaHistorial:
    """Representa una interacción registrada en el historial."""
    id: int
    timestamp: str
    texto_usuario: str
    intencion: str
    resultado: str


@dataclass
class Proyecto:
    """Representa un proyecto de desarrollo registrado."""
    nombre: str
    ruta: str
    ultima_vez: str


# ─────────────────────────────────────────────────────────────────────────────
# GESTOR DE BASE DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

class Memoria:
    """
    Interfaz de alto nivel para la memoria persistente de Jarvis.

    Ejemplo de uso:
        mem = Memoria()
        mem.guardar_interaccion("abre chrome", "ABRIR_APP", "Chrome abierto.")
        ultima = mem.obtener_ultima_app()
    """

    def __init__(self) -> None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self._inicializar_db()

    @contextmanager
    def _conexion(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager para conexiones SQLite seguras."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error("Error en base de datos: %s", e)
        finally:
            conn.close()

    def _inicializar_db(self) -> None:
        """Crea las tablas si no existen."""
        with self._conexion() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS historial (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    texto       TEXT    NOT NULL,
                    intencion   TEXT    NOT NULL DEFAULT '',
                    resultado   TEXT    NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS preferencias (
                    clave   TEXT PRIMARY KEY,
                    valor   TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS alias (
                    alias       TEXT PRIMARY KEY,
                    comando     TEXT NOT NULL,
                    creado_en   TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS proyectos (
                    nombre      TEXT PRIMARY KEY,
                    ruta        TEXT NOT NULL,
                    ultima_vez  TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS apps_recientes (
                    nombre      TEXT PRIMARY KEY,
                    veces       INTEGER NOT NULL DEFAULT 1,
                    ultima_vez  TEXT NOT NULL
                );
            """)
        logger.info("Base de datos inicializada: %s", DB_PATH)

    # ── Historial ─────────────────────────────────────────────────────────────

    def guardar_interaccion(
        self, texto: str, intencion: str = "", resultado: str = ""
    ) -> None:
        """
        Registra una interacción en el historial.

        Args:
            texto: Texto que dijo el usuario.
            intencion: Intención detectada por NLP.
            resultado: Resultado de la acción ejecutada.
        """
        try:
            with self._conexion() as conn:
                conn.execute(
                    "INSERT INTO historial (timestamp, texto, intencion, resultado) "
                    "VALUES (?, ?, ?, ?)",
                    (datetime.now().isoformat(), texto, intencion, resultado),
                )
                # Rotar historial si supera el máximo
                conn.execute(
                    f"DELETE FROM historial WHERE id NOT IN "
                    f"(SELECT id FROM historial ORDER BY id DESC LIMIT {HISTORIAL_MAX_ROWS})"
                )
        except Exception as e:
            logger.error("No se pudo guardar interacción: %s", e)

    def obtener_historial_reciente(self, n: int = 10) -> list[EntradaHistorial]:
        """
        Devuelve las últimas N interacciones del historial.

        Args:
            n: Número de entradas a devolver.

        Returns:
            Lista de EntradaHistorial en orden cronológico inverso.
        """
        try:
            with self._conexion() as conn:
                rows = conn.execute(
                    "SELECT id, timestamp, texto, intencion, resultado "
                    "FROM historial ORDER BY id DESC LIMIT ?",
                    (n,),
                ).fetchall()
                return [
                    EntradaHistorial(
                        id=r["id"],
                        timestamp=r["timestamp"],
                        texto_usuario=r["texto"],
                        intencion=r["intencion"],
                        resultado=r["resultado"],
                    )
                    for r in rows
                ]
        except Exception as e:
            logger.error("Error leyendo historial: %s", e)
            return []

    # ── Preferencias ──────────────────────────────────────────────────────────

    def guardar_preferencia(self, clave: str, valor: str) -> None:
        """Guarda o actualiza una preferencia del usuario."""
        try:
            with self._conexion() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO preferencias (clave, valor) VALUES (?, ?)",
                    (clave, str(valor)),
                )
        except Exception as e:
            logger.error("Error guardando preferencia '%s': %s", clave, e)

    def obtener_preferencia(self, clave: str, default: str = "") -> str:
        """
        Obtiene una preferencia del usuario.

        Args:
            clave: Nombre de la preferencia.
            default: Valor por defecto si no existe.

        Returns:
            Valor de la preferencia o default.
        """
        try:
            with self._conexion() as conn:
                row = conn.execute(
                    "SELECT valor FROM preferencias WHERE clave = ?", (clave,)
                ).fetchone()
                return row["valor"] if row else default
        except Exception as e:
            logger.error("Error leyendo preferencia '%s': %s", clave, e)
            return default

    # ── Alias ─────────────────────────────────────────────────────────────────

    def registrar_alias(self, alias: str, comando: str) -> None:
        """
        Registra un alias personalizado.

        Args:
            alias: Palabra o frase disparadora.
            comando: Comando a ejecutar cuando se diga el alias.
        """
        try:
            with self._conexion() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO alias (alias, comando, creado_en) "
                    "VALUES (?, ?, ?)",
                    (alias.lower().strip(), comando, datetime.now().isoformat()),
                )
            logger.info("Alias registrado: '%s' → '%s'", alias, comando)
        except Exception as e:
            logger.error("Error registrando alias: %s", e)

    def resolver_alias(self, texto: str) -> Optional[str]:
        """
        Busca si el texto coincide con algún alias registrado.

        Args:
            texto: Texto a verificar.

        Returns:
            Comando real si hay coincidencia, None si no.
        """
        try:
            with self._conexion() as conn:
                row = conn.execute(
                    "SELECT comando FROM alias WHERE alias = ?",
                    (texto.lower().strip(),),
                ).fetchone()
                return row["comando"] if row else None
        except Exception as e:
            logger.error("Error resolviendo alias: %s", e)
            return None

    def listar_alias(self) -> list[dict]:
        """Devuelve todos los alias registrados."""
        try:
            with self._conexion() as conn:
                rows = conn.execute("SELECT alias, comando FROM alias").fetchall()
                return [{"alias": r["alias"], "comando": r["comando"]} for r in rows]
        except Exception as e:
            logger.error("Error listando alias: %s", e)
            return []

    # ── Proyectos ─────────────────────────────────────────────────────────────

    def registrar_proyecto(self, nombre: str, ruta: str) -> None:
        """
        Registra o actualiza un proyecto de desarrollo.

        Args:
            nombre: Nombre del proyecto.
            ruta: Ruta absoluta al directorio del proyecto.
        """
        try:
            with self._conexion() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO proyectos (nombre, ruta, ultima_vez) "
                    "VALUES (?, ?, ?)",
                    (nombre.lower(), ruta, datetime.now().isoformat()),
                )
        except Exception as e:
            logger.error("Error registrando proyecto: %s", e)

    def obtener_ultimo_proyecto(self) -> Optional[Proyecto]:
        """
        Devuelve el proyecto más recientemente accedido.

        Returns:
            Proyecto o None si no hay registros.
        """
        try:
            with self._conexion() as conn:
                row = conn.execute(
                    "SELECT nombre, ruta, ultima_vez FROM proyectos "
                    "ORDER BY ultima_vez DESC LIMIT 1"
                ).fetchone()
                return (
                    Proyecto(
                        nombre=row["nombre"],
                        ruta=row["ruta"],
                        ultima_vez=row["ultima_vez"],
                    )
                    if row
                    else None
                )
        except Exception as e:
            logger.error("Error obteniendo último proyecto: %s", e)
            return None

    # ── Apps recientes ────────────────────────────────────────────────────────

    def registrar_app_usada(self, nombre_app: str) -> None:
        """Registra o incrementa el uso de una aplicación."""
        try:
            with self._conexion() as conn:
                conn.execute(
                    "INSERT INTO apps_recientes (nombre, veces, ultima_vez) "
                    "VALUES (?, 1, ?) "
                    "ON CONFLICT(nombre) DO UPDATE SET "
                    "veces = veces + 1, ultima_vez = excluded.ultima_vez",
                    (nombre_app.lower(), datetime.now().isoformat()),
                )
        except Exception as e:
            logger.error("Error registrando app: %s", e)

    def obtener_ultima_app(self) -> Optional[str]:
        """
        Devuelve el nombre de la última aplicación usada.

        Returns:
            Nombre de la app o None.
        """
        try:
            with self._conexion() as conn:
                row = conn.execute(
                    "SELECT nombre FROM apps_recientes "
                    "ORDER BY ultima_vez DESC LIMIT 1"
                ).fetchone()
                return row["nombre"] if row else None
        except Exception as e:
            logger.error("Error obteniendo última app: %s", e)
            return None

    def obtener_apps_frecuentes(self, n: int = 5) -> list[str]:
        """
        Devuelve las N aplicaciones más usadas.

        Args:
            n: Número de aplicaciones.

        Returns:
            Lista de nombres de apps ordenadas por frecuencia.
        """
        try:
            with self._conexion() as conn:
                rows = conn.execute(
                    "SELECT nombre FROM apps_recientes ORDER BY veces DESC LIMIT ?",
                    (n,),
                ).fetchall()
                return [r["nombre"] for r in rows]
        except Exception as e:
            logger.error("Error obteniendo apps frecuentes: %s", e)
            return []


# Instancia singleton
_memoria = Memoria()


# ─────────────────────────────────────────────────────────────────────────────
# API FUNCIONAL (para compatibilidad y conveniencia)
# ─────────────────────────────────────────────────────────────────────────────

def guardar_interaccion(texto: str, intencion: str = "", resultado: str = "") -> None:
    """Registra una interacción en el historial."""
    _memoria.guardar_interaccion(texto, intencion, resultado)


def obtener_ultima_app() -> Optional[str]:
    """Devuelve la última app usada."""
    return _memoria.obtener_ultima_app()


def obtener_ultimo_proyecto() -> Optional[Proyecto]:
    """Devuelve el último proyecto registrado."""
    return _memoria.obtener_ultimo_proyecto()


def guardar_preferencia(clave: str, valor: str) -> None:
    """Guarda una preferencia del usuario."""
    _memoria.guardar_preferencia(clave, valor)


def obtener_preferencia(clave: str, default: str = "") -> str:
    """Obtiene una preferencia del usuario."""
    return _memoria.obtener_preferencia(clave, default)


def registrar_alias(alias: str, comando: str) -> None:
    """Registra un alias personalizado."""
    _memoria.registrar_alias(alias, comando)


def resolver_alias(texto: str) -> Optional[str]:
    """Resuelve un alias a su comando real."""
    return _memoria.resolver_alias(texto)


def registrar_app_usada(nombre: str) -> None:
    """Registra uso de una aplicación."""
    _memoria.registrar_app_usada(nombre)


def registrar_proyecto(nombre: str, ruta: str) -> None:
    """Registra un proyecto."""
    _memoria.registrar_proyecto(nombre, ruta)
