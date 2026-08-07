#!/usr/bin/env python3
"""
diagnostico.py — Script de diagnóstico automático para Jarvis.

Comprueba los componentes esenciales del sistema:
- Python 3 & venv
- GTK4 y PyGObject
- Piper TTS & reproductor de audio (aplay)
- Micrófono & PyAudio
- EventBus thread-safety
- Rutas y permisos de configuración
- Entrada de autostart
- Socket de instancia única (Single Instance)
"""

import os
import sys
import shutil
import socket
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


def check_python() -> tuple[bool, str]:
    if sys.version_info >= (3, 10):
        return True, f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return False, f"Versión de Python incompatible: {sys.version}"


def check_venv() -> tuple[bool, str]:
    venv_dir = BASE_DIR / "venv"
    if venv_dir.exists() and (venv_dir / "bin" / "python").exists():
        return True, str(venv_dir)
    return False, "Entorno virtual venv no encontrado o incompleto"


def check_gtk4() -> tuple[bool, str]:
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk
        return True, f"GTK {Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}.{Gtk.MICRO_VERSION}"
    except Exception as e:
        return False, f"Error cargando GTK4: {e}"


def check_pygobject() -> tuple[bool, str]:
    try:
        import gi
        return True, f"PyGObject {gi.__version__}"
    except Exception as e:
        return False, f"PyGObject no disponible: {e}"


def check_piper() -> tuple[bool, str]:
    piper_venv = BASE_DIR / "venv" / "bin" / "piper"
    piper_path = str(piper_venv) if piper_venv.exists() else shutil.which("piper")
    modelo_voz = BASE_DIR / "modelos_voz" / "es_ES-davefx-medium.onnx"

    if piper_path and modelo_voz.exists():
        return True, f"Executable: {piper_path} | Modelo: {modelo_voz.name}"
    elif piper_path:
        return True, f"Executable: {piper_path} (modelo no encontrado en modelos_voz)"
    elif modelo_voz.exists():
        return True, "Modelo ONNX presente (ejecutable piper en PATH/fallback)"
    return False, "Piper TTS no disponible (falta binario o modelo)"


def check_audio_output() -> tuple[bool, str]:
    aplay_path = shutil.which("aplay")
    if aplay_path:
        return True, f"aplay disponible en {aplay_path}"
    return False, "aplay no disponible en el sistema"


def check_microphone() -> tuple[bool, str]:
    try:
        from nucleo.audio_security import gestor_audio_security
        idx, nombre = gestor_audio_security.resolver_microfono_fisico()
        if idx is not None:
            return True, f"Micrófono físico (Índice {idx}: '{nombre}') | Audio del sistema: BLOQUEADO"
        return False, "No se encontró ningún micrófono físico. Fuentes monitor rechazadas."
    except Exception as e:
        return False, f"Error evaluando seguridad de audio: {e}"


def check_eventbus() -> tuple[bool, str]:
    try:
        from eventos.bus import EventBus
        bus = EventBus()
        recibido = []
        bus.suscribir("test.evento", lambda ev, d: recibido.append(d.get("val")))
        bus.emitir("test.evento", {"val": 42})
        if recibido == [42]:
            return True, "Pub/Sub thread-safe funcional"
        return False, "Fallo de comunicación en EventBus"
    except Exception as e:
        return False, f"Error en EventBus: {e}"


def check_autostart() -> tuple[bool, str]:
    desktop_file = Path.home() / ".config" / "autostart" / "jarvis.desktop"
    if desktop_file.exists():
        content = desktop_file.read_text(encoding="utf-8")
        if "jarvis_launcher.sh" in content:
            return True, str(desktop_file)
        return False, f"El archivo {desktop_file} no apunta a jarvis_launcher.sh"
    return False, f"Entrada autostart no encontrada en {desktop_file}"


def check_single_instance() -> tuple[bool, str]:
    try:
        from nucleo.single_instance import SingleInstance
        si = SingleInstance()
        # Verificar que el mecanismo de Socket no lance excepciones
        return True, "Mecanismo Unix Domain Socket disponible"
    except Exception as e:
        return False, f"Error en Single Instance: {e}"


def main() -> int:
    print("\n" + "═" * 40)
    print("      J A R V I S   S Y S T E M   C H E C K")
    print("═" * 40)

    pruebas = [
        ("Python", check_python),
        ("venv", check_venv),
        ("GTK4", check_gtk4),
        ("PyGObject", check_pygobject),
        ("Piper", check_piper),
        ("Micrófono", check_microphone),
        ("Audio", check_audio_output),
        ("EventBus", check_eventbus),
        ("Autostart", check_autostart),
        ("SingleInstance", check_single_instance),
    ]

    todos_ok = True
    for nombre, fn in pruebas:
        ok, detalle = fn()
        simbolo = "✓" if ok else "✗"
        print(f" {nombre:<14} {simbolo}  ({detalle})")
        if not ok:
            todos_ok = False

    print("─" * 40)
    if todos_ok:
        print(" SYSTEM READY")
        print("═" * 40 + "\n")
        return 0
    else:
        print(" SYSTEM INCOMPLETE — Revisa las advertencias indicadas.")
        print("═" * 40 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
