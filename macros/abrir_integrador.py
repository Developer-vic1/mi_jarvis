"""
macros/abrir_integrador.py — Macro de desarrollo para el proyecto Integrador (SAVP-TIS3).

Ejecuta secuencialmente los pasos de apertura y verificación del entorno de trabajo,
consultando el estado del escritorio (GestorAplicaciones) para reutilizar ventanas
y procesos existentes sin duplicados, y sin levantar servidores PHP innecesarios.
"""

import os
import time
import shutil
import logging
import subprocess
import urllib.request
from datetime import datetime
from typing import Optional

import psutil  # type: ignore[import]

from eventos.bus import bus, Eventos
from nucleo.voz import hablar
from nucleo.memoria import registrar_proyecto
from modulos.gestor_aplicaciones import gestor_apps_sistema

logger = logging.getLogger("jarvis.macros.abrir_integrador")

RUTA_PROYECTO = "/home/victor/UNIFRANZ/savp-tis3"
URL_LOCAL = "http://localhost"


def _emitir_paso(paso: str, ok: Optional[bool], descripcion: str) -> None:
    bus.emitir(Eventos.PROGRESO_MACRO, {"paso": paso, "ok": ok, "descripcion": descripcion})


def _http_ok() -> bool:
    for puerto in [80, 8000, 8080]:
        try:
            url = f"http://localhost:{puerto}" if puerto != 80 else "http://localhost"
            req = urllib.request.Request(url, headers={"User-Agent": "Jarvis-Monitor/1.0"})
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.status in [200, 301, 302, 404]:
                    return True
        except Exception:
            continue
    return False


def _vite_activo(ruta_abs: str) -> bool:
    for proc in psutil.process_iter(["name", "cmdline", "cwd"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or []).lower()
            cwd = proc.info.get("cwd") or ""
            if ("vite" in cmdline or "npm run dev" in cmdline) and os.path.abspath(cwd) == ruta_abs:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def _sail_activo(ruta_abs: str) -> bool:
    try:
        sail_path = os.path.join(ruta_abs, "vendor/bin/sail")
        if os.path.exists(sail_path):
            res_sail = subprocess.run([sail_path, "ps"], cwd=ruta_abs, capture_output=True, text=True, timeout=10)
            salida = (res_sail.stdout + res_sail.stderr).lower()
            if res_sail.returncode == 0 and any(p in salida for p in ["running", "up", "healthy"]):
                return True
    except Exception as e:
        logger.debug("No se pudo consultar sail ps: %s", e)

    try:
        res_ps = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=5)
        salida = res_ps.stdout.lower()
        return res_ps.returncode == 0 and ("savp-tis3" in salida or "laravelsail" in salida or "sail" in salida)
    except Exception:
        return False


def _log_paso(
    paso_num: int,
    nombre_paso: str,
    comando: str,
    exito: bool,
    tiempo_seg: float,
    error: Optional[str] = None
) -> None:
    """Registra en los logs los detalles técnicos de la ejecución de cada paso."""
    hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    estado = "ÉXITO" if exito else "FALLO"
    log_msg = (
        f"[{hora}] [PASO {paso_num}: {nombre_paso}] "
        f"Comando: '{comando}' | Resultado: {estado} | "
        f"Tiempo: {tiempo_seg:.2f}s"
    )
    if error:
        log_msg += f" | Error: {error}"

    if exito:
        logger.info(log_msg)
    else:
        logger.error(log_msg)


def ejecutar_abrir_integrador() -> tuple[bool, str]:
    """
    Ejecuta la macro ABRIR_INTEGRADOR optimizada paso a paso.

    Returns:
        Tupla (éxito: bool, resumen: str).
    """
    logger.info("====================================================")
    logger.info("=== INICIANDO SECUENCIA MACRO: ABRIR_INTEGRADOR ===")
    logger.info("====================================================")

    ruta_abs = os.path.abspath(RUTA_PROYECTO)
    errores_pasos: list[str] = []

    # -------------------------------------------------------------------------
    # PASO 1: Validar existencia de la carpeta del proyecto
    # -------------------------------------------------------------------------
    t_inicio = time.time()
    cmd_p1 = f"os.path.exists('{ruta_abs}')"
    if not os.path.exists(ruta_abs):
        err = f"La carpeta '{ruta_abs}' no existe en el sistema."
        _log_paso(1, "Validar Carpeta", cmd_p1, False, time.time() - t_inicio, err)
        _emitir_paso("Proyecto", False, err)
        hablar("No se encontró la carpeta del proyecto integrador. Cancelando la orden.")
        return False, err

    _log_paso(1, "Validar Carpeta", cmd_p1, True, time.time() - t_inicio)
    _emitir_paso("Proyecto", True, "Proyecto localizado")
    hablar("Iniciando el entorno de desarrollo de tu proyecto integrador.")
    registrar_proyecto("integrador", ruta_abs)
    gestor_apps_sistema.estado.ultimo_proyecto = ruta_abs

    # -------------------------------------------------------------------------
    # PASO 2 & 3: Buscar editor y enfocarlo / abrirlo sin duplicar
    # -------------------------------------------------------------------------
    t_inicio = time.time()
    editores_prioridad = [
        ("Antigravity", "antigravity"),
        ("Visual Studio Code", "code"),
        ("Cursor", "cursor"),
    ]
    editor_encontrado: Optional[str] = None
    bin_editor: Optional[str] = None

    for nombre_ed, executable in editores_prioridad:
        path_ed = shutil.which(executable)
        if path_ed:
            editor_encontrado = nombre_ed
            bin_editor = path_ed
            break

    if not bin_editor or not editor_encontrado:
        err = "No se encontró ningún editor disponible (antigravity, code, cursor)."
        _log_paso(2, "Buscar/Abrir Editor", "shutil.which", False, time.time() - t_inicio, err)
        _emitir_paso("Editor", False, err)
        hablar("Atención: No se encontró ningún editor de código instalado.")
        errores_pasos.append("Editor no encontrado")
    else:
        # Verificar si ya existe ventana abierta del editor
        v_editor = gestor_apps_sistema.buscar_ventana(editor_encontrado)
        titulo_editor = (v_editor.titulo.lower() if v_editor else "")
        proyecto_en_editor = any(x in titulo_editor for x in ["savp", "tis3", "integrador"])
        if v_editor and proyecto_en_editor:
            gestor_apps_sistema.enfocar_ventana(v_editor.window_id)
            _log_paso(2, "Buscar/Abrir Editor", f"Enfocar ventana existente: {editor_encontrado}", True, time.time() - t_inicio)
            _emitir_paso("Editor", True, "Editor con proyecto ya abierto")
        else:
            cmd_p3 = f"{bin_editor} {ruta_abs}"
            try:
                subprocess.Popen([bin_editor, ruta_abs])
                time.sleep(1.5)
                _log_paso(2, "Buscar/Abrir Editor", cmd_p3, True, time.time() - t_inicio)
                _emitir_paso("Editor", True, "Proyecto abierto en editor")
            except Exception as e:
                err = str(e)
                _log_paso(2, "Buscar/Abrir Editor", cmd_p3, False, time.time() - t_inicio, err)
                _emitir_paso("Editor", False, err)
                hablar(f"No se pudo abrir {editor_encontrado}.")
                errores_pasos.append(f"Fallo al abrir editor: {err}")

    # -------------------------------------------------------------------------
    # PASO 4: Verificar y levantar Docker Sail (solo si no está ya activo)
    # -------------------------------------------------------------------------
    t_inicio = time.time()
    cmd_p4 = "docker ps / ./vendor/bin/sail up -d"
    try:
        if _sail_activo(ruta_abs):
            _log_paso(3, "Verificar/Levantar Docker", "docker ps (contenedores ya activos)", True, time.time() - t_inicio)
            _emitir_paso("Docker", True, "Contenedores Sail ya activos")
            logger.info("Los contenedores Docker Sail ya están activos.")
        else:
            sail_abs = os.path.join(ruta_abs, "vendor/bin/sail")
            rel_sail = sail_abs if os.path.exists(sail_abs) else "sail"
            proc_sail = subprocess.run(
                [rel_sail, "up", "-d"],
                cwd=ruta_abs,
                capture_output=True,
                text=True,
                timeout=60
            )
            time.sleep(2.5)  # Esperar estabilización
            exito_docker = proc_sail.returncode == 0 and _sail_activo(ruta_abs)
            _log_paso(
                3, "Verificar/Levantar Docker", f"{rel_sail} up -d",
                exito_docker, time.time() - t_inicio,
                proc_sail.stderr if not exito_docker else None
            )
            _emitir_paso("Docker", exito_docker, "Sail levantado" if exito_docker else proc_sail.stderr[:120])
            if not exito_docker:
                hablar("No se pudieron levantar los contenedores de Docker Sail.")
                errores_pasos.append("Fallo Docker Sail")
    except Exception as e:
        err = str(e)
        _log_paso(3, "Verificar/Levantar Docker", cmd_p4, False, time.time() - t_inicio, err)
        _emitir_paso("Docker", False, err)
        hablar("Ocurrió un error al verificar Docker.")
        errores_pasos.append(f"Fallo Docker: {err}")

    # -------------------------------------------------------------------------
    # PASO 5: Abrir Google Chrome en localhost sin duplicar ventanas
    # -------------------------------------------------------------------------
    t_inicio = time.time()
    try:
        if _http_ok():
            ok_nav, msg_nav = gestor_apps_sistema.abrir_url_en_navegador(URL_LOCAL, "chrome")
            _log_paso(4, "Abrir/Enfocar Chrome", msg_nav, ok_nav, time.time() - t_inicio)
            _emitir_paso("Chrome", ok_nav, msg_nav)
            if not ok_nav:
                errores_pasos.append(f"Fallo Chrome: {msg_nav}")
        else:
            msg = "La aplicación web aún no responde; no se abre navegador todavía"
            _log_paso(4, "Abrir/Enfocar Chrome", "HTTP check", False, time.time() - t_inicio, msg)
            _emitir_paso("Chrome", False, msg)
            errores_pasos.append(msg)
    except Exception as e:
        err = str(e)
        _log_paso(4, "Abrir/Enfocar Chrome", "abrir_url_en_navegador", False, time.time() - t_inicio, err)
        _emitir_paso("Chrome", False, err)
        hablar("Ocurrió un inconveniente al abrir Chrome.")
        errores_pasos.append(f"Fallo Chrome: {err}")

    # -------------------------------------------------------------------------
    # PASO 6: Abrir Tilix ejecutando ÚNICAMENTE npm run dev (SIN artisan serve)
    # -------------------------------------------------------------------------
    t_inicio = time.time()
    bin_tilix = shutil.which("tilix") or "tilix"
    cmd_npm = "npm run dev"

    try:
        if _vite_activo(ruta_abs):
            _log_paso(5, "Tilix NPM Run Dev", "Vite ya activo", True, time.time() - t_inicio)
            _emitir_paso("Tilix/Vite", True, "Vite ya estaba ejecutándose")
        elif gestor_apps_sistema.buscar_ventana("tilix"):
            # Crear nueva pestaña si Tilix ya está abierto
            cmd_p6 = f"{bin_tilix} -a app-new-session -w {ruta_abs} -e bash -c '{cmd_npm}; exec bash'"
            subprocess.Popen([
                bin_tilix, "-a", "app-new-session", "-w", ruta_abs, "-e", f"bash -c '{cmd_npm}; exec bash'"
            ])
            _log_paso(5, "Tilix NPM Run Dev", f"Nueva pestaña en Tilix: {cmd_npm}", True, time.time() - t_inicio)
            _emitir_paso("Tilix/Vite", True, "npm run dev iniciado")
        else:
            cmd_p6 = f"{bin_tilix} -w {ruta_abs} -e bash -c '{cmd_npm}; exec bash'"
            subprocess.Popen([
                bin_tilix, "-w", ruta_abs, "-e", f"bash -c '{cmd_npm}; exec bash'"
            ])
            _log_paso(5, "Tilix NPM Run Dev", cmd_p6, True, time.time() - t_inicio)
            _emitir_paso("Tilix/Vite", True, "npm run dev iniciado")
        time.sleep(1.0)
    except Exception as e:
        err = str(e)
        _log_paso(5, "Tilix NPM Run Dev", "npm run dev", False, time.time() - t_inicio, err)
        _emitir_paso("Tilix/Vite", False, err)
        hablar("No se pudo iniciar la terminal Tilix para npm run dev.")
        errores_pasos.append(f"Fallo Tilix NPM Dev: {err}")

    # -------------------------------------------------------------------------
    # PASO 7: Verificación final de servicios activos (Laravel via Docker, Vite, Docker)
    # -------------------------------------------------------------------------
    t_inicio = time.time()
    time.sleep(3.0)  # Esperar estabilización

    fallos_verificacion: list[str] = []

    # 1. Verificar si el servidor responde en localhost
    laravel_ok = _http_ok()

    if not laravel_ok:
        fallos_verificacion.append("El servidor web en localhost no responde aún")

    # 2. Verificar si Vite (npm run dev) está activo
    vite_ok = False
    try:
        vite_ok = _vite_activo(ruta_abs)
    except Exception:
        pass

    if not vite_ok:
        fallos_verificacion.append("Vite (npm run dev) no se detecta activo")

    # 3. Verificar si Docker permanece activo
    docker_ok = False
    try:
        docker_ok = _sail_activo(ruta_abs)
    except Exception:
        pass

    if not docker_ok:
        fallos_verificacion.append("Docker no está respondiendo")

    exito_paso7 = len(fallos_verificacion) == 0
    _log_paso(
        6, "Verificación Final de Servicios", "HTTP + pgrep + docker ps",
        exito_paso7, time.time() - t_inicio,
        ", ".join(fallos_verificacion) if fallos_verificacion else None
    )

    if fallos_verificacion:
        msg_fallo = f"Servicios con advertencias: {', '.join(fallos_verificacion)}"
        hablar(f"Atención: {', '.join(fallos_verificacion)}.")
        return False, msg_fallo

    msg_exito = "Secuencia completada y todos los servicios verificados correctamente."
    hablar("El entorno de desarrollo para tu integrador ha sido cargado y verificado con éxito.")
    return True, msg_exito


def registrar() -> None:
    """Registra la macro ABRIR_INTEGRADOR en el gestor de macros."""
    from macros.gestor_macros import registrar_macro
    registrar_macro("ABRIR_INTEGRADOR", ejecutar_abrir_integrador)
