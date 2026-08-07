"""
nucleo/listener_voz.py — Listener continuo de voz para la interfaz GTK.

Ejecuta reconocimiento de voz en segundo plano para que la UI permanezca fluida.
El hilo principal GTK solo recibe eventos a través del EventBus.
"""

import logging
import threading
from typing import Callable, Optional

from eventos.bus import bus, Eventos

logger = logging.getLogger("jarvis.listener_voz")


class ListenerVoz:
    """Bucle de escucha en background con parada limpia."""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def iniciar(self, procesar: Callable[[str], object]) -> None:
        """Inicia el listener si no está ejecutándose."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(procesar,),
            daemon=True,
            name="JarvisVoiceListener",
        )
        self._thread.start()
        logger.info("Listener de voz iniciado.")

    def detener(self) -> None:
        """Solicita detener el listener."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("Listener de voz detenido.")

    def _run(self, procesar: Callable[[str], object]) -> None:
        from nucleo.escucha import escuchar_microfono

        while not self._stop_event.is_set():
            try:
                texto = escuchar_microfono()
                if self._stop_event.is_set():
                    break
                if not texto:
                    continue
                bus.emitir(Eventos.COMMAND_RECEIVED, {"texto": texto})
                procesar(texto)
            except Exception as e:
                logger.error("Error en listener de voz: %s", e, exc_info=True)
                bus.emitir(Eventos.ERROR, {"mensaje": f"Error en escucha: {e}"})


listener_voz = ListenerVoz()
