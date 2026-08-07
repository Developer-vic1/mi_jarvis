"""
main.py — Punto de entrada principal de Jarvis.

Configura el sistema de logging, verifica instancia única,
inicializa el cerebro y ejecuta la interfaz GTK o consola.

Flujo GTK:
    1. Verificar instancia única (evitar duplicados)
    2. Configurar logging
    3. Inicializar cerebro (plugins, índice de apps)
    4. Iniciar monitor de audio
    5. Saludo inicial (en thread separado para no bloquear GTK)
    6. Lanzar AppJarvis (bucle GTK)
    7. Al salir: liberar lock de instancia única
"""

import argparse
import logging
import logging.handlers
import os
import sys
import threading

# Asegurar que el directorio raíz del proyecto está en el PATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LOG_PATH, LOG_MAX_BYTES, LOG_BACKUP_COUNT, MODO_DEBUG


def configurar_logging() -> None:
    """
    Configura el sistema de logging de Jarvis.

    Escribe en archivo rotativo (jarvis.log) y en consola si está en modo debug.
    """
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    nivel = logging.DEBUG if MODO_DEBUG else logging.INFO

    # Handler de archivo rotativo
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_PATH,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(nivel)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # Handler de consola (siempre para advertencias+; debug solo si MODO_DEBUG)
    handlers: list[logging.Handler] = [file_handler]
    console_handler = logging.StreamHandler()
    console_level = logging.DEBUG if MODO_DEBUG else logging.WARNING
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(
        "%(levelname)-8s | %(name)-20s | %(message)s"
    ))
    handlers.append(console_handler)

    logging.basicConfig(
        level=nivel,
        handlers=handlers,
    )


def _imprimir_banner() -> None:
    """Muestra el banner de inicio en consola."""
    print("\n" + "═" * 60)
    print("  🤖  J A R V I S  —  Asistente Personal")
    print("  Ubuntu Linux · Python 3.12 · Piper TTS")
    print("═" * 60)
    print("  Di 'Jarvis' para activarme.")
    print("  Di 'descansa' para pasar a modo reposo.")
    print("  Di 'apagar sistema' para salir.")
    print("  [Ctrl+C] para interrumpir.")
    print("═" * 60 + "\n")


def iniciar_jarvis_app(modo_demo: bool = False) -> int:
    """Inicializa Jarvis en modo GTK y lanza la aplicación de escritorio."""
    configurar_logging()
    logger = logging.getLogger("jarvis.main")
    logger.info("=" * 50)
    logger.info("Jarvis GTK iniciando...")

    # ── Importaciones diferidas (no cargar GTK en modo --help o --console) ──
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import GLib
        from interfaz.ventana_principal import AppJarvis
    except Exception as e:
        logger.error("No se pudo cargar GTK: %s", e, exc_info=True)
        print(
            f"Error: No se pudo iniciar la interfaz GTK.\n"
            f"Detalle: {e}\n"
            f"Intenta: ./venv/bin/python main.py --console"
        )
        return 1

    # ── Single Instance ────────────────────────────────────────────────────────
    from nucleo.single_instance import verificar_instancia_unica, liberar_instancia

    # Callback para cuando otra instancia pida que nos mostremos
    # (se llama desde hilo secundario; usamos GLib.idle_add para seguridad GTK)
    _app_ref: list = []  # Referencia mutable a la app

    def _mostrar_ventana() -> None:
        """Trae Jarvis al frente si se intenta abrir otra instancia."""
        logger.info("Señal 'mostrar' recibida de otra instancia.")
        if _app_ref:
            GLib.idle_add(_app_ref[0].activate)

    es_primera_instancia = verificar_instancia_unica(callback_mostrar=_mostrar_ventana)
    if not es_primera_instancia:
        logger.info("Jarvis ya está ejecutándose. Activando instancia existente.")
        print("Jarvis ya está en ejecución. Activando la ventana existente.")
        return 0

    # ── Inicializar núcleo ────────────────────────────────────────────────────
    from nucleo.cerebro import inicializar
    from nucleo.monitor_audio import monitor_audio
    from nucleo.voz import hablar, frase_aleatoria

    inicializar()
    monitor_audio.iniciar()

    # ── Crear y ejecutar la aplicación GTK ────────────────────────────────────
    app = AppJarvis(modo_demo=modo_demo)
    _app_ref.append(app)

    # Saludo inicial en hilo separado (NO bloquear GTK)
    def saludo_inicial() -> None:
        import time
        time.sleep(1.5)  # Esperar a que la ventana aparezca
        hablar(frase_aleatoria("saludo"))

    threading.Thread(target=saludo_inicial, daemon=True, name="SaludoJarvis").start()

    try:
        exit_code = app.run(sys.argv)
        return exit_code
    except KeyboardInterrupt:
        logger.info("Jarvis detenido por KeyboardInterrupt.")
        return 0
    finally:
        monitor_audio.detener()
        liberar_instancia()
        logger.info("Jarvis terminado.")


def iniciar_jarvis_console() -> None:
    """Mantiene el bucle de consola clásico como modo de fallback."""
    configurar_logging()
    logger = logging.getLogger("jarvis.main")
    logger.info("=" * 50)
    logger.info("Jarvis consola iniciando...")

    _imprimir_banner()

    from nucleo.cerebro import inicializar, procesar_comando, sesion_activa, verificar_timeout, obtener_estado
    from nucleo.cerebro import EstadoJarvis
    from nucleo.voz import hablar, frase_aleatoria

    inicializar()
    hablar(frase_aleatoria("saludo"))

    from nucleo.escucha import escuchar_microfono, recalibrar_microfono

    logger.info("Jarvis activo. Esperando wake word.")

    ciclos_sin_habla = 0
    MAX_CICLOS_SIN_HABLA_RECALIBRAR = 20

    while True:
        try:
            if obtener_estado() != EstadoJarvis.REPOSO:
                if verificar_timeout():
                    print("\n[⏱️  Sesión expirada. Volviendo a modo reposo.]")
                    hablar(frase_aleatoria("reposo"))

            estado_actual = obtener_estado()
            if estado_actual == EstadoJarvis.REPOSO:
                print("\n[😴 Modo reposo — Di 'Jarvis' para activarme]", end="", flush=True)
            elif estado_actual == EstadoJarvis.ESPERANDO_CONFIRMACION:
                print("\n[❓ Esperando confirmación... ]", end="", flush=True)

            texto = escuchar_microfono()

            if not texto:
                ciclos_sin_habla += 1
                if ciclos_sin_habla >= MAX_CICLOS_SIN_HABLA_RECALIBRAR:
                    recalibrar_microfono()
                    ciclos_sin_habla = 0
                continue

            ciclos_sin_habla = 0
            print(f"\n[👤 Usuario]: '{texto}'")
            logger.info("Usuario dijo: '%s'", texto)
            procesar_comando(texto)

        except KeyboardInterrupt:
            print("\n\n[⚡ Interrupción manual]")
            hablar("Sistema interrumpido. Hasta luego.")
            logger.info("Jarvis detenido por KeyboardInterrupt.")
            break

        except Exception as e:
            logger.error("Error en bucle principal: %s", e, exc_info=True)
            print(f"\n[⚠️  Error en bucle principal: {e}")
            continue


def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inicia Jarvis como asistente de escritorio GTK o en modo consola.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  ./venv/bin/python main.py              # Interfaz GTK (modo normal)
  ./venv/bin/python main.py --console    # Modo consola (fallback sin GTK)
  ./venv/bin/python main.py --demo       # Interfaz GTK en modo demostración
        """
    )
    parser.add_argument("--console", action="store_true",
                        help="Ejecutar Jarvis en modo consola clásico (sin GTK).")
    parser.add_argument("--demo", action="store_true",
                        help="Iniciar la interfaz GTK en modo demostración visual.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parsear_argumentos()
    if args.console:
        iniciar_jarvis_console()
    else:
        exit_code = iniciar_jarvis_app(modo_demo=args.demo)
        sys.exit(exit_code)
