"""
nucleo/monitor_audio.py — Monitor de entrada de micrófono de Jarvis.

Responsabilidades:
- Capturar niveles de audio reales del micrófono en segundo plano.
- Publicar eventos a EventBus sin acoplarse a la interfaz GTK.
- Emitir eventos de actividad / reposo del micrófono.
- Ser thread-safe y no bloquear el hilo principal.
"""

import array
import logging
import math
import threading
import time
from typing import Optional

from eventos.bus import bus, Eventos

logger = logging.getLogger("jarvis.monitor_audio")


class MonitorAudio:
    """Monitor de audio que publica niveles reales y estados de micrófono."""

    def __init__(
        self,
        rate: int = 16000,
        chunk: int = 1024,
        threshold: float = 0.02,
        idle_timeout: float = 0.4,
        poll_interval: float = 0.02,
    ) -> None:
        self.rate = rate
        self.chunk = chunk
        self.threshold = threshold
        self.idle_timeout = idle_timeout
        self.poll_interval = poll_interval

        self._pyaudio = None
        self._pyaudio_module = None
        self._stream = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._active_state = False
        self._ultima_actividad = 0.0

    def _crear_pyaudio(self):
        if self._pyaudio is None:
            try:
                import pyaudio  # type: ignore[import]
                self._pyaudio_module = pyaudio
                self._pyaudio = pyaudio.PyAudio()
            except ImportError as e:
                logger.error("PyAudio no está instalado: %s", e)
                self._pyaudio = None
                self._pyaudio_module = None
            except Exception as e:
                logger.error("Error inicializando PyAudio: %s", e)
                self._pyaudio = None
                self._pyaudio_module = None

    def iniciar(self) -> None:
        """Inicia el monitor de audio en un hilo separado."""
        if self._thread and self._thread.is_alive():
            return

        self._crear_pyaudio()
        if self._pyaudio is None:
            bus.emitir(Eventos.ERROR, {"mensaje": "Micrófono no disponible"})
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="MonitorAudio")
        self._thread.start()
        logger.info("MonitorAudio iniciado.")

    def detener(self) -> None:
        """Detiene el monitor de audio y cierra el stream con limpieza."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception as e:
                logger.debug("Error cerrando stream de audio: %s", e)
            finally:
                self._stream = None

        try:
            if self._pyaudio is not None:
                self._pyaudio.terminate()
        except Exception as e:
            logger.debug("Error terminando PyAudio: %s", e)
        finally:
            self._pyaudio = None
            self._pyaudio_module = None

        logger.info("MonitorAudio detenido.")

    def _abrir_stream(self) -> bool:
        """Intenta abrir el stream del micrófono físico resuelto por AudioSecurity."""
        if self._pyaudio_module is None:
            logger.error("No hay módulo PyAudio disponible para abrir el stream.")
            return False

        from nucleo.audio_security import gestor_audio_security
        idx, nombre = gestor_audio_security.resolver_microfono_fisico()
        if idx is None:
            logger.error("MonitorAudio: No se encontró ningún micrófono físico. Stream no abierto.")
            return False

        try:
            kwargs = {
                "format": self._pyaudio_module.paInt16,
                "channels": 1,
                "rate": self.rate,
                "input": True,
                "frames_per_buffer": self.chunk,
            }
            if idx is not None:
                kwargs["input_device_index"] = idx

            self._stream = self._pyaudio.open(**kwargs)
            logger.info("MonitorAudio: Stream abierto en micrófono físico '%s' (Índice %d).", nombre, idx)
            return True
        except Exception as e:
            logger.error("No se pudo abrir el stream de micrófono físico: %s", e)
            return False

    def _calcular_nivel(self, frame_data: bytes) -> float:
        """Calcula el nivel normalizado del audio a partir del frame de PCM."""
        try:
            # Interpretar bytes como enteros con signo de 16 bits (PCM)
            samples = array.array("h", frame_data)
            if not samples:
                return 0.0
            suma_cuadrados = sum(s * s for s in samples)
            rms = math.sqrt(suma_cuadrados / len(samples))
        except Exception:
            return 0.0

        # Convertir RMS a una escala logarítmica perceptual.
        nivel = math.log1p(rms) / math.log1p(32767)
        return max(0.0, min(1.0, nivel))

    def _run(self) -> None:
        """Bucle principal del monitor de audio."""
        if not self._abrir_stream():
            bus.emitir(Eventos.ERROR, {"mensaje": "Micrófono no disponible"})
            return

        from nucleo.audio_security import gestor_audio_security

        while not self._stop_event.is_set():
            try:
                frame = self._stream.read(self.chunk, exception_on_overflow=False)
            except Exception as e:
                logger.debug("Error leyendo frame de audio: %s", e)
                time.sleep(0.15)
                continue

            # Si JARVIS está hablando por TTS, forzar nivel a 0 y no activar micrófono
            if gestor_audio_security.esta_mic_pausado_por_tts():
                bus.emitir(Eventos.AUDIO_LEVEL, {"nivel": 0.0})
                if self._active_state:
                    self._active_state = False
                    bus.emitir(Eventos.MICROPHONE_IDLE, {"nivel": 0.0})
                time.sleep(self.poll_interval)
                continue

            nivel = self._calcular_nivel(frame)
            eventos = {
                "nivel": nivel,
            }
            bus.emitir(Eventos.AUDIO_LEVEL, eventos)

            ahora = time.time()
            if nivel >= self.threshold:
                self._ultima_actividad = ahora
                if not self._active_state:
                    self._active_state = True
                    bus.emitir(Eventos.MICROPHONE_ACTIVE, eventos)
            elif self._active_state and (ahora - self._ultima_actividad) > self.idle_timeout:
                self._active_state = False
                bus.emitir(Eventos.MICROPHONE_IDLE, eventos)

            time.sleep(self.poll_interval)


# Singleton global para el monitor de audio
monitor_audio = MonitorAudio()
