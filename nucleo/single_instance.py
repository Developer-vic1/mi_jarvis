"""
nucleo/single_instance.py — Garantiza una única instancia de Jarvis.

Implementa un mecanismo de lock basado en socket Unix:
- Si no hay instancia previa: adquiere el lock y continúa.
- Si hay instancia previa: envía señal "mostrar" y termina limpiamente.

Uso:
    from nucleo.single_instance import SingleInstance
    si = SingleInstance()
    if not si.adquirir():
        print("Jarvis ya está ejecutándose")
        sys.exit(0)
    # ... código normal ...
    # Al final:
    si.liberar()
"""

import logging
import os
import socket
import sys
import threading
from typing import Optional, Callable

logger = logging.getLogger("jarvis.single_instance")

# Ruta del socket Unix para comunicación entre instancias
_SOCKET_PATH = os.path.join(os.path.expanduser("~"), ".jarvis_single_instance.sock")
# Timeout en segundos para conectar con instancia existente
_CONNECT_TIMEOUT = 1.0


class SingleInstance:
    """
    Garantiza que solo una instancia de Jarvis se ejecute al mismo tiempo.

    Usa un socket Unix abstracto (sin archivo en disco) para el lock.
    Si detecta otra instancia, le envía la señal 'show' para que se muestre.

    Ejemplo:
        si = SingleInstance()
        if not si.adquirir():
            sys.exit(0)  # Ya había una instancia, la activamos
        try:
            app.run()
        finally:
            si.liberar()
    """

    SIGNAL_SHOW = b"show"
    SIGNAL_ACK  = b"ok"

    def __init__(self, callback_mostrar: Optional[Callable] = None) -> None:
        """
        Args:
            callback_mostrar: Función a llamar cuando otra instancia pide que
                              la ventana se muestre. Se ejecuta en hilo secundario.
        """
        self._callback_mostrar = callback_mostrar
        self._server_socket: Optional[socket.socket] = None
        self._lock_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def adquirir(self) -> bool:
        """
        Intenta adquirir el lock de instancia única.

        Returns:
            True si esta es la primera instancia (puede continuar).
            False si ya había una instancia (se le envió señal 'show').
        """
        # 1. Intentar conectar a instancia existente
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(_CONNECT_TIMEOUT)
            sock.connect(_SOCKET_PATH)
            # Hay una instancia en ejecución → enviarle señal de mostrar
            sock.sendall(self.SIGNAL_SHOW)
            try:
                ack = sock.recv(16)
                logger.info("Instancia existente reconoció la señal: %s", ack)
            except Exception:
                pass
            sock.close()
            logger.info("Ya existe una instancia de Jarvis. Enviando señal 'show'.")
            return False
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            # No hay instancia previa → intentar limpiar socket viejo si existe
            try:
                os.unlink(_SOCKET_PATH)
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.debug("No se pudo limpiar socket viejo: %s", e)

        # 2. Crear socket servidor (esta es la primera instancia)
        try:
            self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind(_SOCKET_PATH)
            self._server_socket.listen(5)
            self._server_socket.settimeout(0.5)  # No bloquear indefinidamente

            # Iniciar hilo que escucha señales de otras instancias
            self._stop_event.clear()
            self._lock_thread = threading.Thread(
                target=self._escuchar,
                daemon=True,
                name="SingleInstanceServer"
            )
            self._lock_thread.start()
            logger.info("SingleInstance: lock adquirido. Socket: %s", _SOCKET_PATH)
            return True

        except Exception as e:
            logger.error("No se pudo crear socket de instancia única: %s", e)
            # En caso de error, permitir ejecución normal
            return True

    def _escuchar(self) -> None:
        """Hilo que escucha peticiones de otras instancias."""
        while not self._stop_event.is_set():
            try:
                if self._server_socket is None:
                    break
                conn, _ = self._server_socket.accept()
                threading.Thread(
                    target=self._manejar_conexion,
                    args=(conn,),
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _manejar_conexion(self, conn: socket.socket) -> None:
        """Maneja una conexión entrante de otra instancia."""
        try:
            data = conn.recv(64)
            if data == self.SIGNAL_SHOW:
                logger.info("Recibida señal 'show' de otra instancia.")
                conn.sendall(self.SIGNAL_ACK)
                if self._callback_mostrar:
                    try:
                        self._callback_mostrar()
                    except Exception as e:
                        logger.error("Error en callback_mostrar: %s", e)
        except Exception as e:
            logger.debug("Error manejando conexión single instance: %s", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def liberar(self) -> None:
        """Libera el lock de instancia única al terminar."""
        self._stop_event.set()

        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None

        try:
            os.unlink(_SOCKET_PATH)
        except Exception:
            pass

        if self._lock_thread and self._lock_thread.is_alive():
            self._lock_thread.join(timeout=2.0)

        logger.info("SingleInstance: lock liberado.")


# ─────────────────────────────────────────────────────────────────────────────
# Instancia global (opcional, para uso desde main.py)
# ─────────────────────────────────────────────────────────────────────────────

_instancia: Optional[SingleInstance] = None


def verificar_instancia_unica(callback_mostrar: Optional[Callable] = None) -> bool:
    """
    Verifica que no haya otra instancia de Jarvis en ejecución.

    Si hay otra instancia, le envía señal de 'mostrar ventana' y devuelve False.
    Si no hay otra instancia, adquiere el lock y devuelve True.

    Args:
        callback_mostrar: Función a llamar cuando otra instancia pide que
                          la ventana se muestre.

    Returns:
        True si esta es la primera instancia.
        False si ya había una (la nueva instancia debe terminar).
    """
    global _instancia
    _instancia = SingleInstance(callback_mostrar=callback_mostrar)
    return _instancia.adquirir()


def liberar_instancia() -> None:
    """Libera el lock de instancia única. Llamar al cerrar Jarvis."""
    global _instancia
    if _instancia:
        _instancia.liberar()
        _instancia = None
