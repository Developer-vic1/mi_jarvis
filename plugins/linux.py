"""
plugins/linux.py — Plugin de control del sistema Linux/Ubuntu.

Capacidades:
- Control de energía: apagar, reiniciar, bloquear, cerrar sesión
- Control de volumen: subir, bajar, silenciar (pactl)
- Control de brillo: subir, bajar (brightnessctl)
- Métricas del sistema: RAM, CPU, disco (psutil)
- Procesos: listar los más activos
- Actualizaciones del sistema
"""

import logging
import subprocess
from typing import Optional

import psutil  # type: ignore[import]

import plugins

logger = logging.getLogger("jarvis.linux")

INTENCIONES = [
    "LINUX_APAGAR", "LINUX_REINICIAR", "LINUX_BLOQUEAR", "LINUX_CERRAR_SESION",
    "LINUX_VOL_UP", "LINUX_VOL_DOWN", "LINUX_VOL_MUTE",
    "LINUX_BRILLO_UP", "LINUX_BRILLO_DOWN",
    "LINUX_RAM", "LINUX_CPU", "LINUX_DISCO", "LINUX_PROCESOS",
    "LINUX_ACTUALIZAR",
]


def _ejecutar(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    """
    Ejecuta un comando del sistema de forma segura.

    Returns:
        Tupla (éxito, salida/error).
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Tiempo de espera agotado."
    except FileNotFoundError:
        return False, f"Comando no encontrado: {cmd[0]}"
    except Exception as e:
        return False, str(e)


def _formatear_bytes(bytes_val: int) -> str:
    """Convierte bytes a representación legible."""
    for unidad in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unidad}"
        bytes_val //= 1024
    return f"{bytes_val} TB"


class PluginLinux(plugins.BasePlugin):
    """Plugin de control del sistema Ubuntu/Linux."""

    def __init__(self) -> None:
        super().__init__(
            nombre="linux",
            intenciones=INTENCIONES,
            descripcion=(
                "Controla el sistema: volumen, brillo, RAM, CPU, disco, "
                "apagar, reiniciar, bloquear pantalla."
            ),
            categoria="Sistema",
        )

    def manejar(self, intencion: str, entidades: dict, contexto: dict) -> str:
        handlers = {
            "LINUX_APAGAR": self._apagar,
            "LINUX_REINICIAR": self._reiniciar,
            "LINUX_BLOQUEAR": self._bloquear,
            "LINUX_CERRAR_SESION": self._cerrar_sesion,
            "LINUX_VOL_UP": self._volumen_subir,
            "LINUX_VOL_DOWN": self._volumen_bajar,
            "LINUX_VOL_MUTE": self._volumen_silenciar,
            "LINUX_BRILLO_UP": self._brillo_subir,
            "LINUX_BRILLO_DOWN": self._brillo_bajar,
            "LINUX_RAM": self._info_ram,
            "LINUX_CPU": self._info_cpu,
            "LINUX_DISCO": self._info_disco,
            "LINUX_PROCESOS": self._info_procesos,
            "LINUX_ACTUALIZAR": self._actualizar,
        }
        handler = handlers.get(intencion)
        if handler:
            return handler(entidades, contexto)
        return "No reconocí ese comando del sistema."

    # ── Energía ───────────────────────────────────────────────────────────────

    def _apagar(self, entidades: dict, contexto: dict) -> str:
        ok, _ = _ejecutar(["shutdown", "now"])
        return "Apagando el sistema. Hasta luego." if ok else "No pude apagar el sistema."

    def _reiniciar(self, entidades: dict, contexto: dict) -> str:
        ok, _ = _ejecutar(["reboot"])
        return "Reiniciando el sistema." if ok else "No pude reiniciar. Puede requerir permisos de administrador."

    def _bloquear(self, entidades: dict, contexto: dict) -> str:
        ok, _ = _ejecutar(["loginctl", "lock-session"])
        if not ok:
            # Fallback con gnome-screensaver
            ok, _ = _ejecutar(["gnome-screensaver-command", "--lock"])
        if not ok:
            ok, _ = _ejecutar(["xdg-screensaver", "lock"])
        return "Pantalla bloqueada." if ok else "No pude bloquear la pantalla."

    def _cerrar_sesion(self, entidades: dict, contexto: dict) -> str:
        ok, _ = _ejecutar(["gnome-session-quit", "--logout", "--no-prompt"])
        return "Cerrando sesión." if ok else "No pude cerrar la sesión."

    # ── Volumen ───────────────────────────────────────────────────────────────

    def _volumen_subir(self, entidades: dict, contexto: dict) -> str:
        ok, _ = _ejecutar(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"])
        return "Volumen aumentado." if ok else "No pude cambiar el volumen."

    def _volumen_bajar(self, entidades: dict, contexto: dict) -> str:
        ok, _ = _ejecutar(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"])
        return "Volumen reducido." if ok else "No pude cambiar el volumen."

    def _volumen_silenciar(self, entidades: dict, contexto: dict) -> str:
        ok, _ = _ejecutar(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
        return "Silencio activado." if ok else "No pude silenciar el audio."

    # ── Brillo ────────────────────────────────────────────────────────────────

    def _brillo_subir(self, entidades: dict, contexto: dict) -> str:
        ok, _ = _ejecutar(["brightnessctl", "set", "+10%"])
        if not ok:
            ok, _ = _ejecutar(["xbacklight", "-inc", "10"])
        return "Brillo aumentado." if ok else "No pude cambiar el brillo. Verifica que brightnessctl esté instalado."

    def _brillo_bajar(self, entidades: dict, contexto: dict) -> str:
        ok, _ = _ejecutar(["brightnessctl", "set", "10%-"])
        if not ok:
            ok, _ = _ejecutar(["xbacklight", "-dec", "10"])
        return "Brillo reducido." if ok else "No pude cambiar el brillo."

    # ── Métricas ──────────────────────────────────────────────────────────────

    def _info_ram(self, entidades: dict, contexto: dict) -> str:
        mem = psutil.virtual_memory()
        usada = _formatear_bytes(mem.used)
        total = _formatear_bytes(mem.total)
        porcentaje = mem.percent
        return f"Memoria RAM: {usada} usados de {total} totales. {porcentaje:.0f}% de uso."

    def _info_cpu(self, entidades: dict, contexto: dict) -> str:
        cpu_pct = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        freq = psutil.cpu_freq()
        freq_str = f" a {freq.current:.0f} MHz" if freq else ""
        return f"CPU al {cpu_pct:.0f}% de uso. {cpu_count} núcleos{freq_str}."

    def _info_disco(self, entidades: dict, contexto: dict) -> str:
        disco = psutil.disk_usage("/")
        total = _formatear_bytes(disco.total)
        usado = _formatear_bytes(disco.used)
        libre = _formatear_bytes(disco.free)
        porcentaje = disco.percent
        return f"Disco: {usado} usados de {total}. {libre} libres. {porcentaje:.0f}% ocupado."

    def _info_procesos(self, entidades: dict, contexto: dict) -> str:
        procs = []
        for p in sorted(psutil.process_iter(["pid", "name", "cpu_percent"]),
                         key=lambda x: x.info.get("cpu_percent", 0) or 0, reverse=True)[:5]:
            nombre = p.info.get("name", "?")
            cpu = p.info.get("cpu_percent", 0) or 0
            procs.append(f"{nombre} ({cpu:.0f}% CPU)")
        if procs:
            lista = ", ".join(procs)
            return f"Los procesos más activos son: {lista}."
        return "No pude obtener información de procesos."

    # ── Actualización ─────────────────────────────────────────────────────────

    def _actualizar(self, entidades: dict, contexto: dict) -> str:
        ok, salida = _ejecutar(
            ["pkexec", "apt-get", "update", "-q"],
            timeout=60,
        )
        if ok:
            return "Sistema actualizado correctamente."
        return "No pude actualizar el sistema. Puede requerir permisos de administrador."


plugins.registrar(PluginLinux())
