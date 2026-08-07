"""
nucleo/audio_security.py — Capa centralizada de seguridad y aislamiento de audio.

Responsabilidades:
1. Enumerar y clasificar rigurosamente todos los dispositivos de entrada/salida de audio.
2. PROHIBIR la selección de fuentes de audio del sistema (monitores de salida, sinks, loopbacks, PipeWire/PulseAudio monitors).
3. Seleccionar EXCLUSIVAMENTE micrófonos físicos válidos.
4. Prevenir que JARVIS se escuche a sí mismo (pausa del micrófono mientras habla el TTS).
5. Exponer un singleton global `gestor_audio_security` consumido por escucha.py, monitor_audio.py y la UI.
"""

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from eventos.bus import bus, Eventos

logger = logging.getLogger("jarvis.audio_security")

CONFIG_AUDIO_PATH = Path(__file__).resolve().parent.parent / "datos" / "audio_config.json"

# Patrones explícitamente bloqueados (audio del sistema, monitores de salida, loopback)
PATRONES_BLOQUEADOS = [
    r"\bmonitor\b",
    r"\bsink\b",
    r"\boutput\b",
    r"\bloopback\b",
    r"\bnull-sink\b",
    r"stereo\s*mix",
    r"mezcla\s*est[eé]reo",
    r"desktop\s*audio",
    r"system\s*audio",
    r"virtual",
    r"monitor of",
]

# Patrones característicos de hardware de entrada físico
PATRONES_FISICOS = [
    r"mic",
    r"micr[oó]fono",
    r"analog",
    r"hw:",
    r"sysdefault",
    r"front",
    r"headset",
    r"webcam",
    r"usb",
    r"alc\d+",
    r"hda",
    r"realtek",
    r"audio generic",
    r"input",
]


@dataclass
class DispositivoAudio:
    index: int
    nombre: str
    es_fisico: bool
    tipo: str  # "INPUT_PHYSICAL", "SYSTEM_MONITOR_BLOCKED", "OUTPUT_ONLY", "UNVERIFIED"
    max_inputs: int
    max_outputs: int
    razon_bloqueo: str = ""


class GestorSeguridadAudio:
    """
    Capa de seguridad centralizada para validación e aislamiento de audio.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._dispositivo_seleccionado_index: Optional[int] = None
        self._tts_hablando = False
        self._pausa_tts_hasta = 0.0
        self._estabilizacion_delay = 0.35  # Segundos tras terminar TTS antes de reabrir micrófono
        self._aec_habilitado = True
        self._noise_suppression_habilitado = True

        self._conectar_eventbus()
        self.cargar_configuracion()

    def _conectar_eventbus(self) -> None:
        """Se suscribe a eventos del sistema para controlar el estado de auto-escucha."""
        bus.suscribir(Eventos.HABLANDO, self._on_voice_started)
        bus.suscribir(Eventos.VOICE_STARTED, self._on_voice_started)
        bus.suscribir(Eventos.FIN_HABLA, self._on_voice_finished)
        bus.suscribir(Eventos.VOICE_FINISHED, self._on_voice_finished)

    def _on_voice_started(self, evento: str, datos: dict) -> None:
        with self._lock:
            self._tts_hablando = True
            logger.debug("AudioSecurity: TTS activo -> Micrófono silenciado (Prevenir auto-escucha)")

    def _on_voice_finished(self, evento: str, datos: dict) -> None:
        with self._lock:
            self._tts_hablando = False
            self._pausa_tts_hasta = time.time() + self._estabilizacion_delay
            logger.debug(
                "AudioSecurity: TTS finalizado -> Esperando estabilización (%.2fs)",
                self._estabilizacion_delay,
            )

    def esta_mic_pausado_por_tts(self) -> bool:
        """
        Devuelve True si el micrófono debe descartar/pausar captura porque JARVIS está hablando
        o el audio se está estabilizando.
        """
        with self._lock:
            if self._tts_hablando:
                return True
            return time.time() < self._pausa_tts_hasta

    def clasificar_dispositivo(self, index: int, nombre: str, max_inputs: int, max_outputs: int) -> DispositivoAudio:
        """
        Clasifica un dispositivo de audio según la política de seguridad estricta.

        Regla fundamental:
        - Si max_inputs == 0 -> OUTPUT_ONLY
        - Si el nombre contiene cualquier patrón bloqueado (monitor, sink, output, loopback) -> SYSTEM_MONITOR_BLOCKED
        - De lo contrario, si max_inputs > 0 -> INPUT_PHYSICAL
        """
        nombre_lower = nombre.lower()

        if max_inputs <= 0:
            return DispositivoAudio(
                index=index,
                nombre=nombre,
                es_fisico=False,
                tipo="OUTPUT_ONLY",
                max_inputs=max_inputs,
                max_outputs=max_outputs,
                razon_bloqueo="Dispositivo solo de salida",
            )

        for patron in PATRONES_BLOQUEADOS:
            if re.search(patron, nombre_lower):
                return DispositivoAudio(
                    index=index,
                    nombre=nombre,
                    es_fisico=False,
                    tipo="SYSTEM_MONITOR_BLOCKED",
                    max_inputs=max_inputs,
                    max_outputs=max_outputs,
                    razon_bloqueo=f"Audio del sistema / Monitor bloqueado ({patron})",
                )

        # Si coincide con patrones físicos típicos o es una entrada sin bloqueo
        es_fisico = any(re.search(p, nombre_lower) for p in PATRONES_FISICOS) or max_inputs > 0

        return DispositivoAudio(
            index=index,
            nombre=nombre,
            es_fisico=es_fisico,
            tipo="INPUT_PHYSICAL" if es_fisico else "UNVERIFIED",
            max_inputs=max_inputs,
            max_outputs=max_outputs,
        )

    def listar_dispositivos(self) -> List[DispositivoAudio]:
        """
        Enumera todos los dispositivos de audio de PyAudio y los clasifica.
        """
        dispositivos: List[DispositivoAudio] = []
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            num_devs = pa.get_device_count()
            for i in range(num_devs):
                try:
                    info = pa.get_device_info_by_index(i)
                    dev = self.clasificar_dispositivo(
                        index=i,
                        nombre=info.get("name", f"Dispositivo {i}"),
                        max_inputs=int(info.get("maxInputChannels", 0)),
                        max_outputs=int(info.get("maxOutputChannels", 0)),
                    )
                    dispositivos.append(dev)
                except Exception as e:
                    logger.debug("Error obteniendo info de dispositivo %d: %s", i, e)
            pa.terminate()
        except Exception as e:
            logger.error("Error al enumerar dispositivos PyAudio: %s", e)

        return dispositivos

    def obtener_microfonos_fisicos_disponibles(self) -> List[DispositivoAudio]:
        """
        Filtra y devuelve ÚNICAMENTE los micrófonos físicos autorizados.
        Excluye explícitamente todo monitor o sink.
        """
        todos = self.listar_dispositivos()
        fisicos = [d for d in todos if d.tipo == "INPUT_PHYSICAL" and d.max_inputs > 0]
        return fisicos

    def resolver_microfono_fisico(self) -> Tuple[Optional[int], Optional[str]]:
        """
        Determina el índice del micrófono físico a utilizar siguiendo la prioridad:
        1. Selección guardada por el usuario (si sigue siendo válida y es física).
        2. Primer micrófono físico detectado por hardware.
        3. Si no existe ninguno -> Devuelve (None, None) y activa estado seguro.

        NUNCA SELECCIONA UN MONITOR O AUDIO DEL SISTEMA COMO FALLBACK.
        """
        fisicos = self.obtener_microfonos_fisicos_disponibles()

        logger.info("[Audio] Dispositivos de audio inspeccionados:")

        for d in self.listar_dispositivos():
            if d.tipo == "SYSTEM_MONITOR_BLOCKED":
                logger.info("  [Audio] Dispositivo %d: '%s' -> BLOQUEADO (%s)", d.index, d.nombre, d.razon_bloqueo)
            elif d.tipo == "INPUT_PHYSICAL":
                logger.info("  [Audio] Dispositivo %d: '%s' -> MICRÓFONO FÍSICO PERMITIDO", d.index, d.nombre)

        if not fisicos:
            logger.error("[Audio] ERROR: No se encontró ningún micrófono físico válido.")
            logger.error("[Audio] Se rehúsa explícitamente el uso de fuentes monitor/audio del sistema.")
            return None, None

        # 1. Si hay preferencia del usuario, verificar si sigue siendo física
        if self._dispositivo_seleccionado_index is not None:
            for f in fisicos:
                if f.index == self._dispositivo_seleccionado_index:
                    logger.info("[Audio] Micrófono físico seleccionado por usuario: '%s' (Índice %d)", f.nombre, f.index)
                    return f.index, f.nombre

        # 2. Selección automática del primer micrófono físico (priorizar hw: o ALC/Analog si existe)
        seleccionado = fisicos[0]
        for f in fisicos:
            if "hw:" in f.nombre or "analog" in f.nombre.lower() or "alc" in f.nombre.lower():
                seleccionado = f
                break

        logger.info("[Audio] Micrófono físico seleccionado: '%s'", seleccionado.nombre)
        logger.info("[Audio] Índice: %d | Tipo: INPUT_PHYSICAL", seleccionado.index)
        logger.info("[Audio] System monitor: RECHAZADO Y BLOQUEADO")

        return seleccionado.index, seleccionado.nombre

    def fijar_microfono_seleccionado(self, index: int) -> bool:
        """Establece manualmente el micrófono físico deseado por el usuario."""
        todos = self.listar_dispositivos()
        for d in todos:
            if d.index == index:
                if d.tipo == "SYSTEM_MONITOR_BLOCKED":
                    logger.warning("Intento rechazado de seleccionar fuente monitor '%s'", d.nombre)
                    return False
                if d.max_inputs > 0:
                    self._dispositivo_seleccionado_index = index
                    self.guardar_configuracion()
                    logger.info("Micrófono físico cambiado a índice %d: %s", index, d.nombre)
                    return True
        return False

    def guardar_configuracion(self) -> None:
        try:
            CONFIG_AUDIO_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "selected_mic_index": self._dispositivo_seleccionado_index,
                "aec_enabled": self._aec_habilitado,
                "noise_suppression": self._noise_suppression_habilitado,
            }
            with open(CONFIG_AUDIO_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("Error guardando configuración de audio: %s", e)

    def cargar_configuracion(self) -> None:
        try:
            if CONFIG_AUDIO_PATH.exists():
                with open(CONFIG_AUDIO_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                self._dispositivo_seleccionado_index = data.get("selected_mic_index")
                self._aec_habilitado = data.get("aec_enabled", True)
                self._noise_suppression_habilitado = data.get("noise_suppression", True)
        except Exception as e:
            logger.debug("Error cargando configuración de audio: %s", e)


# Singleton global de seguridad de audio
gestor_audio_security = GestorSeguridadAudio()
