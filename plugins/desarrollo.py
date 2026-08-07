"""
plugins/desarrollo.py — Plugin de herramientas de desarrollo de Jarvis.

Comandos soportados:
- Git: pull, push, status, log
- Docker Compose: up, down
- Laravel: serve
- Flutter: run
- Python: ejecutar scripts
- Apertura de IDEs y herramientas
"""

import logging
import os
import subprocess
from typing import Optional

import plugins
from nucleo.memoria import obtener_ultimo_proyecto, registrar_proyecto

logger = logging.getLogger("jarvis.desarrollo")

RUTA_INTEGRADOR = "/home/victor/UNIFRANZ/savp-tis3/"

INTENCIONES = [
    "GIT_PULL", "GIT_STATUS", "GIT_LOG", "GIT_PUSH",
    "DOCKER_UP", "DOCKER_DOWN",
    "LARAVEL_SERVE", "FLUTTER_RUN", "PYTHON_RUN",
    "CAMBIAR_VENTANA", "ABRIR_INTEGRADOR",
]



def _ejecutar_en_terminal(cmd: str, directorio: Optional[str] = None) -> tuple[bool, str]:
    """
    Ejecuta un comando en una terminal Tilix visible para el usuario.
    Si Tilix no está disponible, usa gnome-terminal.

    Args:
        cmd: Comando a ejecutar.
        directorio: Directorio de trabajo (cwd).

    Returns:
        Tupla (éxito, mensaje).
    """
    cwd = directorio or _obtener_directorio_proyecto()

    # Intentar con Tilix
    for terminal in [
        ["tilix", "--new-session", "--working-directory", cwd, "--command", cmd],
        ["gnome-terminal", "--working-directory", cwd, "--", "bash", "-c", f"{cmd}; exec bash"],
        ["xterm", "-e", f"cd '{cwd}' && {cmd}"],
    ]:
        try:
            subprocess.Popen(
                terminal,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Comando en terminal: %s (cwd: %s)", cmd, cwd)
            return True, f"Ejecutando: {cmd}"
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.error("Error lanzando terminal: %s", e)
            continue

    # Fallback: ejecutar en background sin terminal visible
    try:
        subprocess.Popen(
            cmd, shell=True, cwd=cwd,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True, f"Ejecutando en segundo plano: {cmd}"
    except Exception as e:
        logger.error("Error ejecutando en background: %s", e)
        return False, str(e)


def _obtener_directorio_proyecto() -> str:
    """
    Devuelve el directorio del último proyecto registrado,
    o el home del usuario como fallback.
    """
    proyecto = obtener_ultimo_proyecto()
    if proyecto and os.path.exists(proyecto.ruta):
        return proyecto.ruta
    return os.path.expanduser("~")


def _ejecutar_git(args: list[str], cwd: Optional[str] = None) -> tuple[bool, str]:
    """Ejecuta un comando git y devuelve su salida."""
    directorio = cwd or _obtener_directorio_proyecto()
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True, timeout=30, cwd=directorio,
        )
        salida = (result.stdout + result.stderr).strip()
        exito = result.returncode == 0
        return exito, salida
    except subprocess.TimeoutExpired:
        return False, "El comando tardó demasiado."
    except FileNotFoundError:
        return False, "Git no está instalado."
    except Exception as e:
        return False, str(e)


class PluginDesarrollo(plugins.BasePlugin):
    """Plugin de herramientas de desarrollo."""

    def __init__(self) -> None:
        super().__init__(
            nombre="desarrollo",
            intenciones=INTENCIONES,
            descripcion=(
                "Ejecuta comandos de desarrollo: Git, Docker, Laravel, Flutter, "
                "y gestiona proyectos."
            ),
            categoria="Desarrollo",
        )

    def manejar(self, intencion: str, entidades: dict, contexto: dict) -> str:
        handlers = {
            "GIT_PULL": self._git_pull,
            "GIT_STATUS": self._git_status,
            "GIT_LOG": self._git_log,
            "GIT_PUSH": self._git_push,
            "DOCKER_UP": self._docker_up,
            "DOCKER_DOWN": self._docker_down,
            "LARAVEL_SERVE": self._laravel_serve,
            "FLUTTER_RUN": self._flutter_run,
            "PYTHON_RUN": self._python_run,
            "CAMBIAR_VENTANA": self._cambiar_ventana,
            "ABRIR_INTEGRADOR": lambda ent, ctx: abrir_integrador(),
        }
        handler = handlers.get(intencion)
        if handler:
            return handler(entidades, contexto)
        return "No reconocí ese comando de desarrollo."

    # ── Git ───────────────────────────────────────────────────────────────────

    def _git_pull(self, entidades: dict, contexto: dict) -> str:
        ok, salida = _ejecutar_git(["pull"])
        if ok:
            if "Already up to date" in salida or "Ya está actualizado" in salida:
                return "El repositorio ya está actualizado."
            return f"Git pull completado. {salida[:100]}"
        return f"Error en git pull: {salida[:100]}"

    def _git_status(self, entidades: dict, contexto: dict) -> str:
        ok, salida = _ejecutar_git(["status", "--short"])
        if not ok:
            return f"Error al consultar git status: {salida[:100]}"
        if not salida:
            return "El repositorio está limpio. No hay cambios pendientes."
        lineas = salida.split("\n")
        num = len(lineas)
        return f"Hay {num} cambio{'s' if num > 1 else ''} pendiente{'s' if num > 1 else ''}. {salida[:120]}"

    def _git_log(self, entidades: dict, contexto: dict) -> str:
        ok, salida = _ejecutar_git(["log", "--oneline", "-5"])
        if ok and salida:
            return f"Últimos commits:\n{salida}"
        return "No pude obtener el historial de commits."

    def _git_push(self, entidades: dict, contexto: dict) -> str:
        ok, salida = _ejecutar_git(["push"])
        if ok:
            return "Cambios enviados al repositorio remoto."
        return f"Error en git push: {salida[:100]}"

    # ── Docker ────────────────────────────────────────────────────────────────

    def _docker_up(self, entidades: dict, contexto: dict) -> str:
        ok, _ = _ejecutar_en_terminal("docker compose up")
        if ok:
            return "Levantando contenedores Docker."
        return "No pude levantar Docker Compose."

    def _docker_down(self, entidades: dict, contexto: dict) -> str:
        directorio = _obtener_directorio_proyecto()
        try:
            subprocess.Popen(
                ["docker", "compose", "down"],
                cwd=directorio,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return "Deteniendo contenedores Docker."
        except FileNotFoundError:
            return "Docker no está instalado o no está en el PATH."
        except Exception as e:
            return f"Error deteniendo contenedores: {e}"

    # ── Frameworks ────────────────────────────────────────────────────────────

    def _laravel_serve(self, entidades: dict, contexto: dict) -> str:
        ok, _ = _ejecutar_en_terminal("php artisan serve")
        if ok:
            return "Iniciando servidor Laravel en http://127.0.0.1:8000"
        return "No pude iniciar el servidor Laravel."

    def _flutter_run(self, entidades: dict, contexto: dict) -> str:
        ok, _ = _ejecutar_en_terminal("flutter run")
        if ok:
            return "Ejecutando Flutter."
        return "No pude ejecutar Flutter. Verifica que esté instalado y el proyecto sea válido."

    def _python_run(self, entidades: dict, contexto: dict) -> str:
        script = entidades.get("objeto", "").strip()
        if not script:
            return "¿Qué script Python deseas ejecutar?"
        ok, _ = _ejecutar_en_terminal(f"python3 {script}")
        if ok:
            return f"Ejecutando {script} con Python."
        return "No pude ejecutar el script."

    def _cambiar_ventana(self, entidades: dict, contexto: dict) -> str:
        app = entidades.get("app", "").strip()
        if not app:
            return "¿A qué ventana deseas cambiar?"
        from modulos.gestor_aplicaciones import gestor_apps_sistema
        ok, msg = gestor_apps_sistema.ensure_application_open(app)
        return msg if ok else f"No encontré ninguna ventana abierta de '{app}'."


def abrir_integrador() -> str:
    """
    Delegado a la macro oficial ABRIR_INTEGRADOR en el motor de macros.
    """
    from macros.abrir_integrador import ejecutar_abrir_integrador
    exito, mensaje = ejecutar_abrir_integrador()
    return mensaje



    # ── Git ───────────────────────────────────────────────────────────────────

    def _git_pull(self, entidades: dict, contexto: dict) -> str:
        ok, salida = _ejecutar_git(["pull"])
        if ok:
            if "Already up to date" in salida or "Ya está actualizado" in salida:
                return "El repositorio ya está actualizado."
            return f"Git pull completado. {salida[:100]}"
        return f"Error en git pull: {salida[:100]}"

    def _git_status(self, entidades: dict, contexto: dict) -> str:
        ok, salida = _ejecutar_git(["status", "--short"])
        if not ok:
            return f"Error al consultar git status: {salida[:100]}"
        if not salida:
            return "El repositorio está limpio. No hay cambios pendientes."
        lineas = salida.split("\n")
        num = len(lineas)
        return f"Hay {num} cambio{'s' if num > 1 else ''} pendiente{'s' if num > 1 else ''}. {salida[:120]}"

    def _git_log(self, entidades: dict, contexto: dict) -> str:
        ok, salida = _ejecutar_git(["log", "--oneline", "-5"])
        if ok and salida:
            return f"Últimos commits:\n{salida}"
        return "No pude obtener el historial de commits."

    def _git_push(self, entidades: dict, contexto: dict) -> str:
        ok, salida = _ejecutar_git(["push"])
        if ok:
            return "Cambios enviados al repositorio remoto."
        return f"Error en git push: {salida[:100]}"

    # ── Docker ────────────────────────────────────────────────────────────────

    def _docker_up(self, entidades: dict, contexto: dict) -> str:
        ok, msg = _ejecutar_en_terminal("docker compose up")
        if ok:
            return "Levantando contenedores Docker."
        return "No pude levantar Docker Compose."

    def _docker_down(self, entidades: dict, contexto: dict) -> str:
        directorio = _obtener_directorio_proyecto()
        try:
            subprocess.Popen(
                ["docker", "compose", "down"],
                cwd=directorio,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return "Deteniendo contenedores Docker."
        except FileNotFoundError:
            return "Docker no está instalado o no está en el PATH."
        except Exception as e:
            return f"Error deteniendo contenedores: {e}"

    # ── Laravel ───────────────────────────────────────────────────────────────

    def _laravel_serve(self, entidades: dict, contexto: dict) -> str:
        ok, msg = _ejecutar_en_terminal("php artisan serve")
        if ok:
            return "Iniciando servidor Laravel en http://127.0.0.1:8000"
        return "No pude iniciar el servidor Laravel."

    # ── Flutter ───────────────────────────────────────────────────────────────

    def _flutter_run(self, entidades: dict, contexto: dict) -> str:
        ok, msg = _ejecutar_en_terminal("flutter run")
        if ok:
            return "Ejecutando Flutter."
        return "No pude ejecutar Flutter. Verifica que esté instalado y el proyecto sea válido."

    # ── Python ────────────────────────────────────────────────────────────────

    def _python_run(self, entidades: dict, contexto: dict) -> str:
        script = entidades.get("objeto", "").strip()
        if not script:
            return "¿Qué script Python deseas ejecutar?"
        ok, msg = _ejecutar_en_terminal(f"python3 {script}")
        if ok:
            return f"Ejecutando {script} con Python."
        return "No pude ejecutar el script."

    # ── Cambiar ventana ───────────────────────────────────────────────────────

    def _cambiar_ventana(self, entidades: dict, contexto: dict) -> str:
        app = entidades.get("app", "").strip()
        if not app:
            return "¿A qué ventana deseas cambiar?"
        try:
            subprocess.run(["wmctrl", "-a", app], check=True, timeout=3)
            return f"Cambiando a {app}."
        except subprocess.CalledProcessError:
            return f"No encontré ninguna ventana abierta de '{app}'."
        except FileNotFoundError:
            return "wmctrl no está instalado."
        except Exception as e:
            return f"Error cambiando ventana: {e}"

    


plugins.registrar(PluginDesarrollo())
