"""
tests/test_audio_security.py — Pruebas unitarias de aislamiento de audio y seguridad de micrófono.
"""

import time
from unittest.mock import patch, MagicMock
import pytest

from nucleo.audio_security import GestorSeguridadAudio, DispositivoAudio
from eventos.bus import bus, Eventos


def test_clasificacion_dispositivos_permitidos_vs_bloqueados():
    gestor = GestorSeguridadAudio()

    # ── PERMITIDOS ──
    permitidos = [
        "Built-in Microphone",
        "USB Microphone",
        "Webcam Microphone",
        "External Microphone",
        "HD-Audio Generic: ALC257 Analog (hw:1,0)",
        "front:CARD=Generic,DEV=0",
        "sysdefault:CARD=Generic",
    ]

    for nombre in permitidos:
        dev = gestor.clasificar_dispositivo(index=1, nombre=nombre, max_inputs=2, max_outputs=0)
        assert dev.tipo == "INPUT_PHYSICAL", f"Esperado INPUT_PHYSICAL para '{nombre}', obtenido '{dev.tipo}'"
        assert dev.es_fisico is True

    # ── BLOQUEADOS ──
    bloqueados = [
        "Monitor of Built-in Audio",
        "Monitor of USB Audio",
        "PulseAudio Monitor",
        "PipeWire Monitor",
        "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor",
        "Loopback Audio",
        "Null Output Sink",
        "Stereo Mix",
        "Desktop Audio Capture",
    ]

    for nombre in bloqueados:
        dev = gestor.clasificar_dispositivo(index=2, nombre=nombre, max_inputs=2, max_outputs=2)
        assert dev.tipo == "SYSTEM_MONITOR_BLOCKED", f"Esperado SYSTEM_MONITOR_BLOCKED para '{nombre}', obtenido '{dev.tipo}'"
        assert dev.es_fisico is False


def test_prevencion_auto_escucha_tts():
    gestor = GestorSeguridadAudio()
    assert gestor.esta_mic_pausado_por_tts() is False

    # Simular evento VOICE_STARTED / HABLANDO
    bus.emitir(Eventos.VOICE_STARTED, {"texto": "Hablando JARVIS"})
    assert gestor.esta_mic_pausado_por_tts() is True

    # Simular evento VOICE_FINISHED / FIN_HABLA
    bus.emitir(Eventos.VOICE_FINISHED, {"texto": "Fin habla"})
    # Debe seguir pausado por la ventana de estabilización (0.35s)
    assert gestor.esta_mic_pausado_por_tts() is True

    # Tras esperar el tiempo de estabilización, se reactiva
    time.sleep(0.4)
    assert gestor.esta_mic_pausado_por_tts() is False


def test_failsafe_sin_microfono_fisico():
    gestor = GestorSeguridadAudio()

    # Mockear que solo existen dispositivos monitor bloqueados
    monitores = [
        DispositivoAudio(index=0, nombre="PipeWire Monitor", es_fisico=False, tipo="SYSTEM_MONITOR_BLOCKED", max_inputs=2, max_outputs=2),
        DispositivoAudio(index=1, nombre="Monitor of Built-in", es_fisico=False, tipo="SYSTEM_MONITOR_BLOCKED", max_inputs=2, max_outputs=2),
    ]

    with patch.object(gestor, "listar_dispositivos", return_value=monitores):
        idx, nombre = gestor.resolver_microfono_fisico()
        assert idx is None
        assert nombre is None
        # Prohibido usar fuentes monitor como fallback
        assert gestor.fijar_microfono_seleccionado(0) is False
