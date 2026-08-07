"""
modulos/gestor_aplicaciones.py — Administrador Inteligente de Sesión de Escritorio y Aplicaciones Linux (X11).

Este módulo es el único responsable de consultar el estado del sistema operativo,
buscar procesos y ventanas activas, enfocar aplicaciones sin duplicarlas,
cerrar aplicaciones elegantemente (SIGTERM → SIGKILL), y responder sobre el
estado actual del escritorio mediante wmctrl, xdotool y psutil.
"""

import os
import re
import time
import shutil
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any

import psutil  # type: ignore[import]

from eventos.bus import bus, Eventos

logger = logging.getLogger("jarvis.gestor_aplicaciones")


# ─────────────────────────────────────────────────────────────────────────────
# MAPEO Y ALIASES DE APLICACIONES PARA VENTANAS Y PROCESOS
# ─────────────────────────────────────────────────────────────────────────────

ALIAS_PROCESOS_VENTANAS: Dict[str, Dict[str, List[str]]] = {
    "chrome": {
        "nombres": ["google chrome", "chrome", "chromium", "navegador"],
        "clases": ["google-chrome", "chromium", "google-chrome-stable"],
        "procesos": ["chrome", "google-chrome", "google-chrome-stable"],
        "exec": ["google-chrome-stable", "google-chrome", "chrome"],
    },
    "vscode": {
        "nombres": ["visual studio code", "vscode", "vs code", "code", "editor"],
        "clases": ["code", "visual-studio-code", "code - url-handler"],
        "procesos": ["code"],
        "exec": ["code"],
    },
    "antigravity": {
        "nombres": ["antigravity", "antigravity ide"],
        "clases": ["antigravity"],
        "procesos": ["antigravity"],
        "exec": ["antigravity"],
    },
    "cursor": {
        "nombres": ["cursor"],
        "clases": ["cursor"],
        "procesos": ["cursor"],
        "exec": ["cursor"],
    },
    "docker": {
        "nombres": ["docker desktop", "docker", "contenedores"],
        "clases": ["docker desktop", "docker-desktop", "com.docker.backend"],
        "procesos": ["docker-desktop", "com.docker.backend", "dockerd"],
        "exec": ["/opt/docker-desktop/bin/docker-desktop", "docker-desktop"],
    },
    "tilix": {
        "nombres": ["tilix", "terminal tilix", "terminal", "consola"],
        "clases": ["tilix", "Tilix"],
        "procesos": ["tilix"],
        "exec": ["tilix"],
    },
    "terminal_gnome": {
        "nombres": ["gnome terminal", "terminal gnome", "terminal", "consola"],
        "clases": ["gnome-terminal-server", "Gnome-terminal"],
        "procesos": ["gnome-terminal", "gnome-terminal-server"],
        "exec": ["gnome-terminal"],
    },
    "pgadmin": {
        "nombres": ["pgadmin", "pgadmin4", "pg admin", "base de datos"],
        "clases": ["pgadmin4", "pgadmin"],
        "procesos": ["pgadmin4"],
        "exec": ["/usr/pgadmin4/bin/pgadmin4", "pgadmin4"],
    },
    "discord": {
        "nombres": ["discord"],
        "clases": ["discord", "Discord"],
        "procesos": ["discord"],
        "exec": ["discord"],
    },
    "spotify": {
        "nombres": ["spotify", "musica"],
        "clases": ["spotify", "Spotify"],
        "procesos": ["spotify"],
        "exec": ["spotify"],
    },
    "opera": {
        "nombres": ["opera", "opera gx"],
        "clases": ["opera", "Opera"],
        "procesos": ["opera", "opera-gx"],
        "exec": ["opera-gx", "opera"],
    },
}


def _infos_alias(nombre_app: str) -> List[Dict[str, List[str]]]:
    """Devuelve todas las definiciones de alias compatibles con un nombre."""
    nombre_lower = nombre_app.lower().strip()
    return [
        info for clave, info in ALIAS_PROCESOS_VENTANAS.items()
        if nombre_lower == clave or nombre_lower in info["nombres"]
    ]


@dataclass
class VentanaInfo:
    window_id: str
    desktop_id: int
    pid: int
    wm_class: str
    hostname: str
    titulo: str

    def to_dict(self) -> dict:
        return {
            "window_id": self.window_id,
            "desktop_id": self.desktop_id,
            "pid": self.pid,
            "wm_class": self.wm_class,
            "hostname": self.hostname,
            "titulo": self.titulo,
        }


@dataclass
class EstadoEscritorio:
    ultima_ventana_activa: Optional[str] = None
    ultimo_proyecto: Optional[str] = None
    ultima_carpeta: Optional[str] = None
    ultimo_navegador: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# CLASE PRINCIPAL: GESTOR DE APLICACIONES
# ─────────────────────────────────────────────────────────────────────────────

class GestorAplicaciones:
    """
    Administrador inteligente de ventanas, procesos y estado del escritorio.
    """

    def __init__(self) -> None:
        self.estado = EstadoEscritorio()

    # ── Ejecución Helper ──────────────────────────────────────────────────────

    def _ejecutar_comando(self, cmd: List[str], timeout: float = 5.0) -> Tuple[bool, str]:
        """Ejecuta un comando CLI de forma segura."""
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if res.returncode == 0:
                return True, res.stdout.strip()
            return False, res.stderr.strip()
        except Exception as e:
            logger.debug("Error ejecutando %s: %s", cmd, e)
            return False, str(e)

    # ── Inspección de Ventanas y Procesos ─────────────────────────────────────

    def listar_ventanas(self) -> List[VentanaInfo]:
        """
        Obtiene la lista completa de ventanas usando `wmctrl -lp -lx`.

        Returns:
            Lista de objetos VentanaInfo.
        """
        ok, salida = self._ejecutar_comando(["wmctrl", "-lp", "-lx"])
        if not ok or not salida:
            return []

        ventanas: List[VentanaInfo] = []
        for linea in salida.splitlines():
            linea = linea.strip()
            if not linea:
                continue
            # Formato wmctrl -lp -lx:
            # 0x00e00005  0 648316 dev.warp.Warp.dev.warp.Warp  victor-LOQ-15AHP9 DOCKER RUN
            partes = linea.split(None, 5)
            if len(partes) >= 5:
                w_id = partes[0]
                try:
                    desk_id = int(partes[1])
                except ValueError:
                    desk_id = 0
                try:
                    pid = int(partes[2])
                except ValueError:
                    pid = 0
                wm_class = partes[3]
                hostname = partes[4]
                titulo = partes[5] if len(partes) > 5 else ""

                ventanas.append(
                    VentanaInfo(
                        window_id=w_id,
                        desktop_id=desk_id,
                        pid=pid,
                        wm_class=wm_class,
                        hostname=hostname,
                        titulo=titulo,
                    )
                )

        return ventanas

    def listar_ventanas_usuario(self) -> List[VentanaInfo]:
        """
        Filtra únicamente las aplicaciones gráficas visibles del usuario,
        descartando paneles del sistema, docks y escritorios (-1 desktop_id).
        """
        ventanas = self.listar_ventanas()
        resultado = []
        ignorar_clases = [
            "desktop_window", "gnome-shell", "dock", "panel", "wrapper",
            "plasmashell", "krunner", "Xfce4-panel"
        ]

        for v in ventanas:
            # Omitir ventanas pegajosas de sistema
            if v.desktop_id == -1 and any(ig in v.wm_class.lower() for ig in ignorar_clases):
                continue
            if any(ig in v.wm_class.lower() for ig in ignorar_clases):
                continue
            if not v.titulo.strip():
                continue
            resultado.append(v)

        return resultado

    def buscar_proceso(self, nombre_app: str) -> List[psutil.Process]:
        """
        Busca procesos ejecutándose en el sistema por nombre o coincidencia de alias.
        """
        nombre_lower = nombre_app.lower().strip()
        procesos_objetivo: List[str] = [nombre_lower]

        # Buscar en todos los alias conocidos compatibles
        for info in _infos_alias(nombre_lower):
            procesos_objetivo.extend(info["procesos"])

        procesos_encontrados: List[psutil.Process] = []
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                p_name = (p.info.get("name") or "").lower()
                cmdline = " ".join(p.info.get("cmdline") or []).lower()

                for obj in procesos_objetivo:
                    if obj in p_name or obj in cmdline:
                        procesos_encontrados.append(p)
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return procesos_encontrados

    def buscar_ventana(self, nombre_app: str) -> Optional[VentanaInfo]:
        """
        Busca si existe una ventana abierta para una aplicación.

        Args:
            nombre_app: Nombre de la aplicación (e.g. "chrome", "vscode", "tilix")

        Returns:
            Objeto VentanaInfo si existe, None si no.
        """
        nombre_lower = nombre_app.lower().strip()
        ventanas = self.listar_ventanas_usuario()

        # Identificar posibles clases y títulos
        clases_objetivo: List[str] = [nombre_lower]
        nombres_objetivo: List[str] = [nombre_lower]

        for info in _infos_alias(nombre_lower):
            clases_objetivo.extend([c.lower() for c in info["clases"]])
            nombres_objetivo.extend([n.lower() for n in info["nombres"]])

        # 1. Coincidencia por WM_CLASS exacto/parcial
        for v in ventanas:
            w_class_lower = v.wm_class.lower()
            for c in clases_objetivo:
                if c in w_class_lower:
                    logger.info("Ventana encontrada por WM_CLASS: '%s' (%s)", v.titulo, v.window_id)
                    return v

        # 2. Coincidencia por Título de la ventana
        for v in ventanas:
            t_lower = v.titulo.lower()
            for n in nombres_objetivo:
                if n in t_lower:
                    logger.info("Ventana encontrada por Título: '%s' (%s)", v.titulo, v.window_id)
                    return v

        # 3. Coincidencia por PID de proceso
        procesos = self.buscar_proceso(nombre_app)
        pids = {p.pid for p in procesos}
        if pids:
            for v in ventanas:
                if v.pid in pids:
                    logger.info("Ventana encontrada por PID %d: '%s'", v.pid, v.titulo)
                    return v

        return None

    # ── Acciones de Ventana y Aplicación ──────────────────────────────────────

    def enfocar_ventana(self, window_id: str) -> bool:
        """
        Trae la ventana especificada al frente y le da el foco.
        """
        # Intentar wmctrl -i -a
        ok, _ = self._ejecutar_comando(["wmctrl", "-i", "-a", window_id])
        if ok:
            return True

        # Fallback con xdotool
        ok, _ = self._ejecutar_comando(["xdotool", "windowactivate", window_id])
        return ok

    def ensure_application_open(self, nombre_app: str, exec_cmd: Optional[str] = None) -> Tuple[bool, str]:
        """Alias público en inglés para abrir/enfocar sin duplicar instancias."""
        return self.abrir_aplicacion(nombre_app, exec_cmd)

    def abrir_aplicacion(self, nombre_app: str, exec_cmd: Optional[str] = None) -> Tuple[bool, str]:
        """
        Abre o enfoca una aplicación.

        Flujo obligatorio:
        1. Buscar si ya existe una ventana.
        2. Si la ventana existe -> NO abrir otra, simplemente ENFOCARLA.
        3. Si no existe -> Abrir la aplicación y registrar.

        Returns:
            Tupla (éxito: bool, mensaje: str)
        """
        ventana_existente = self.buscar_ventana(nombre_app)
        if ventana_existente:
            self.enfocar_ventana(ventana_existente.window_id)
            self.estado.ultima_ventana_activa = ventana_existente.titulo
            msg = f"La aplicación {nombre_app} ya estaba abierta. Se ha traído al frente."
            logger.info(msg)
            bus.emitir(Eventos.APPLICATION_DETECTED, {"app": nombre_app, "ventana": ventana_existente.to_dict()})
            return True, msg

        # Si no existe ventana, determinar comando Exec
        cmd_args: List[str] = []
        if exec_cmd:
            import shlex
            cmd_args = shlex.split(exec_cmd)
        else:
            # Buscar en mapeo interno
            nombre_lower = nombre_app.lower().strip()
            for info in _infos_alias(nombre_lower):
                for ex in info["exec"]:
                    path = shutil.which(ex)
                    if path:
                        cmd_args = [path]
                        break
                if cmd_args:
                    break

            if not cmd_args:
                # Intento genérico con shutil.which
                path = shutil.which(nombre_lower)
                if path:
                    cmd_args = [path]

        if not cmd_args:
            msg = f"No se encontró el ejecutable para la aplicación '{nombre_app}'."
            logger.error(msg)
            return False, msg

        try:
            subprocess.Popen(cmd_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("Aplicación iniciada: %s", cmd_args)
            # Esperar brevemente a que cree su ventana
            time.sleep(1.2)
            v_nueva = self.buscar_ventana(nombre_app)
            if v_nueva:
                self.enfocar_ventana(v_nueva.window_id)
                self.estado.ultima_ventana_activa = v_nueva.titulo

            bus.emitir(Eventos.APPLICATION_OPENED, {"app": nombre_app})
            return True, f"Abriendo {nombre_app}."
        except Exception as e:
            msg = f"Error al abrir la aplicación {nombre_app}: {e}"
            logger.error(msg)
            return False, msg

    def cerrar_aplicacion(self, nombre_app: str) -> Tuple[bool, str]:
        """
        Cierra una aplicación de forma segura y elegante.

        Flujo obligatorio:
        1. Buscar la ventana.
        2. Cerrar elegantemente (wmctrl -c / xdotool windowclose).
        3. Esperar 1.5 segundos.
        4. Si continúa abierta -> enviar SIGTERM (proc.terminate()).
        5. Esperar 1.5 segundos.
        6. Si continúa viva -> enviar SIGKILL (proc.kill()).
        Nunca usar kill -9 directamente al inicio.
        """
        nombre_lower = nombre_app.lower().strip()

        # 1. Buscar ventana y procesos
        ventana = self.buscar_ventana(nombre_app)
        procesos = self.buscar_proceso(nombre_app)

        if not ventana and not procesos:
            msg = f"No encontré ninguna ventana ni proceso activo para '{nombre_app}'."
            return False, msg

        # Intentar cierre elegante vía X11 (wmctrl -c)
        if ventana:
            logger.info("Enviando cierre elegante X11 a la ventana '%s' (%s)", ventana.titulo, ventana.window_id)
            self._ejecutar_comando(["wmctrl", "-i", "-c", ventana.window_id])
            time.sleep(1.5)

            # Verificar si la ventana se cerró
            ventana_check = self.buscar_ventana(nombre_app)
            if not ventana_check:
                msg = f"Se cerró {nombre_app} correctamente."
                logger.info(msg)
                bus.emitir(Eventos.APPLICATION_CLOSED, {"app": nombre_app})
                return True, msg

        # Actualizar lista de procesos vivos
        procesos_vivos = [p for p in procesos if p.is_running()]

        # 2. Si sigue abierta o no tenía ventana -> SIGTERM
        if procesos_vivos:
            logger.info("Aplicación '%s' sigue activa. Enviando SIGTERM a PIDs: %s",
                        nombre_app, [p.pid for p in procesos_vivos])
            for p in procesos_vivos:
                try:
                    p.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            time.sleep(1.5)
            procesos_vivos = [p for p in procesos_vivos if p.is_running()]

        if not procesos_vivos:
            msg = f"{nombre_app} finalizada correctamente."
            bus.emitir(Eventos.APPLICATION_CLOSED, {"app": nombre_app})
            return True, msg

        # 3. Si aún continúa viva -> SIGKILL
        logger.warning("Aplicación '%s' no respondió a SIGTERM. Enviando SIGKILL...", nombre_app)
        for p in procesos_vivos:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        time.sleep(0.5)
        msg = f"{nombre_app} fue forzada a cerrar."
        bus.emitir(Eventos.APPLICATION_CLOSED, {"app": nombre_app, "forzado": True})
        return True, msg

    def minimizar_aplicacion(self, nombre_app: str) -> Tuple[bool, str]:
        """Minimiza la ventana de una aplicación dada."""
        ventana = self.buscar_ventana(nombre_app)
        if not ventana:
            return False, f"No encontré ninguna ventana abierta de {nombre_app}."

        # Intentar con xdotool
        ok, _ = self._ejecutar_comando(["xdotool", "windowminimize", ventana.window_id])
        if not ok:
            # Fallback con wmctrl
            ok, _ = self._ejecutar_comando(["wmctrl", "-i", "-r", ventana.window_id, "-b", "add,hidden"])

        if ok:
            return True, f"Minimizando {nombre_app}."
        return False, f"No pude minimizar {nombre_app}."

    def maximizar_aplicacion(self, nombre_app: str) -> Tuple[bool, str]:
        """Maximiza la ventana de una aplicación dada."""
        ventana = self.buscar_ventana(nombre_app)
        if not ventana:
            return False, f"No encontré ninguna ventana abierta de {nombre_app}."

        self.enfocar_ventana(ventana.window_id)
        ok, _ = self._ejecutar_comando([
            "wmctrl", "-i", "-r", ventana.window_id, "-b", "add,maximized_vert,maximized_horz"
        ])
        if not ok:
            ok, _ = self._ejecutar_comando([
                "xdotool", "windowstate", "--add", "MAXIMIZED_VERT", "--add", "MAXIMIZED_HORZ", ventana.window_id
            ])

        if ok:
            return True, f"Maximizando {nombre_app}."
        return False, f"No pude maximizar {nombre_app}."

    def abrir_url_en_navegador(self, url: str, navegador_preferido: str = "chrome") -> Tuple[bool, str]:
        """
        Abre una URL reutilizando una ventana de navegador cuando sea posible.

        Si ya hay navegador abierto, solo lo enfoca para evitar pestañas/procesos
        duplicados en macros repetidas. Si no hay ventana, lanza el navegador con
        la URL inicial.
        """
        for nombre in [navegador_preferido, "chrome", "firefox"]:
            ventana = self.buscar_ventana(nombre)
            if ventana:
                self.enfocar_ventana(ventana.window_id)
                return True, f"El navegador ya estaba abierto. Se ha traído al frente."

        ejecutables = ["google-chrome-stable", "google-chrome", "chromium", "firefox"]
        for exe in ejecutables:
            path = shutil.which(exe)
            if not path:
                continue
            try:
                subprocess.Popen([path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                bus.emitir(Eventos.APPLICATION_OPENED, {"app": exe, "url": url})
                return True, f"Abriendo navegador en {url}."
            except Exception as e:
                logger.error("Error abriendo navegador %s: %s", exe, e)

        return False, "No se encontró un navegador disponible."

    # ── Consultas del Estado del Escritorio ───────────────────────────────────

    def obtener_ventana_activa(self) -> Optional[dict]:
        """
        Obtiene la ventana actualmente enfocada en el escritorio.

        Returns:
            Diccionario con datos de la ventana o None.
        """
        # Método 1: xdotool
        ok, w_id = self._ejecutar_comando(["xdotool", "getactivewindow"])
        if ok and w_id:
            try:
                # Convertir id decimal a hex
                w_hex = f"0x{int(w_id):08x}"
                ventanas = self.listar_ventanas()
                for v in ventanas:
                    if v.window_id.lower() == w_hex.lower() or int(v.window_id, 16) == int(w_id):
                        self.estado.ultima_ventana_activa = v.titulo
                        datos = v.to_dict()
                        bus.emitir(Eventos.APPLICATION_DETECTED, {"app": self.obtener_nombre_amigable_app(datos), "ventana": datos})
                        return datos
            except ValueError:
                pass

            ok_name, name = self._ejecutar_comando(["xdotool", "getwindowname", w_id])
            if ok_name and name:
                self.estado.ultima_ventana_activa = name
                datos = {"window_id": w_id, "titulo": name, "wm_class": "", "pid": 0}
                bus.emitir(Eventos.APPLICATION_DETECTED, {"app": self.obtener_nombre_amigable_app(datos), "ventana": datos})
                return datos

        # Método 2: xprop -root _NET_ACTIVE_WINDOW
        ok, xprop_out = self._ejecutar_comando(["xprop", "-root", "_NET_ACTIVE_WINDOW"])
        if ok and "window id #" in xprop_out:
            match = re.search(r"window id # (0x[0-9a-fA-F]+)", xprop_out)
            if match:
                hex_id = match.group(1)
                ventanas = self.listar_ventanas()
                for v in ventanas:
                    if int(v.window_id, 16) == int(hex_id, 16):
                        self.estado.ultima_ventana_activa = v.titulo
                        datos = v.to_dict()
                        bus.emitir(Eventos.APPLICATION_DETECTED, {"app": self.obtener_nombre_amigable_app(datos), "ventana": datos})
                        return datos

        return None

    def obtener_nombre_amigable_app(self, ventana_dict: dict) -> str:
        """
        Formatea el nombre de la aplicación de la ventana activa para respuesta de voz.
        """
        titulo = ventana_dict.get("titulo", "")
        wm_class = ventana_dict.get("wm_class", "")

        t_lower = titulo.lower()
        c_lower = wm_class.lower()

        if "code" in c_lower or "visual studio code" in t_lower:
            return "Visual Studio Code"
        if "chrome" in c_lower or "google chrome" in t_lower:
            return "Google Chrome"
        if "tilix" in c_lower or "tilix" in t_lower:
            return "Tilix"
        if "docker" in c_lower or "docker" in t_lower:
            return "Docker Desktop"
        if "pgadmin" in c_lower or "pgadmin" in t_lower:
            return "pgAdmin"
        if "discord" in c_lower or "discord" in t_lower:
            return "Discord"
        if "spotify" in c_lower or "spotify" in t_lower:
            return "Spotify"
        if "warp" in c_lower or "warp" in t_lower:
            return "Warp"
        if "firefox" in c_lower or "firefox" in t_lower:
            return "Firefox"

        # Nombre simplificado si no está en la lista de conocidos
        if title := titulo.split(" - ")[-1].strip():
            return title
        return titulo or wm_class or "la aplicación activa"

    def listar_nombres_aplicaciones_abiertas(self) -> List[str]:
        """
        Devuelve una lista con los nombres formateados de las aplicaciones gráficas abiertas.
        """
        ventanas = self.listar_ventanas_usuario()
        nombres = set()

        for v in ventanas:
            nombre = self.obtener_nombre_amigable_app(v.to_dict())
            if nombre:
                nombres.add(nombre)

        return sorted(list(nombres))

    def cerrar_todas_las_terminales(self) -> Tuple[bool, str]:
        """Cierra todas las instancias de terminales activas."""
        ventanas = self.listar_ventanas_usuario()
        cerradas = 0
        for v in ventanas:
            w_class = v.wm_class.lower()
            if any(t in w_class for t in ["tilix", "terminal", "warp", "konsole", "xterm"]):
                self._ejecutar_comando(["wmctrl", "-i", "-c", v.window_id])
                cerradas += 1

        if cerradas > 0:
            return True, f"Se han cerrado {cerradas} ventanas de terminal."
        return False, "No hay terminales abiertas."


# Instancia Singleton Global
gestor_apps_sistema = GestorAplicaciones()
