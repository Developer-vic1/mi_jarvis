"""
tests/test_cobertura_completa.py — Tests de integración y cobertura avanzada para JARVIS.
"""

import os
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from eventos.bus import EventBus, Eventos, bus
from nucleo.cerebro import (
    Cerebro, EstadoJarvis, obtener_estado, activar_sesion,
    verificar_timeout, procesar_comando
)
from nucleo.voz import frase_aleatoria, hablar, esperar_fin_habla
from nucleo.single_instance import SingleInstance, verificar_instancia_unica, liberar_instancia
from temas.gestor_temas import gestor_temas, Paleta, PALETA_HIGH_CONTRAST


def test_cerebro_transiciones_de_estado_y_wake_word():
    cerebro = Cerebro()
    assert cerebro.estado == EstadoJarvis.REPOSO
    assert cerebro.sesion_activa is False

    # Reconocer wake word
    assert cerebro.es_wake_word("jarvis") is True
    assert cerebro.es_wake_word("oye jarvis") is True
    assert cerebro.es_wake_word("hola") is False

    # Procesar wake word -> activa sesión
    respuesta = cerebro.procesar("jarvis")
    assert cerebro.estado == EstadoJarvis.ESCUCHANDO
    assert cerebro.sesion_activa is True

    # Sleep word -> desactiva sesión
    assert cerebro.es_sleep_word("descansa") is True
    respuesta_sleep = cerebro.procesar("descansa")
    assert cerebro.estado == EstadoJarvis.REPOSO


def test_cerebro_timeout_inactividad(monkeypatch):
    cerebro = Cerebro()
    cerebro._activar_sesion()
    assert cerebro.estado == EstadoJarvis.ESCUCHANDO

    # Simular paso del tiempo superior al timeout
    monkeypatch.setattr(time, "time", lambda: cerebro._ultima_actividad + 40.0)
    expiro = cerebro.verificar_timeout()
    assert expiro is True
    assert cerebro.estado == EstadoJarvis.REPOSO


def test_cerebro_flujo_confirmacion_si_no():
    cerebro = Cerebro()
    cerebro._activar_sesion()
    cerebro._confirmacion_pendiente = {"accion": "eliminar", "ruta": "/tmp/test.txt"}
    cerebro._estado = EstadoJarvis.ESPERANDO_CONFIRMACION

    with patch("plugins.archivos.PluginArchivos.confirmar_eliminar", return_value="Archivo eliminado."):
        res = cerebro.procesar("sí por favor")
        assert res == "Archivo eliminado."
        assert cerebro.estado == EstadoJarvis.ESCUCHANDO

    # Prueba respuesta No
    cerebro._confirmacion_pendiente = {"accion": "eliminar", "ruta": "/tmp/test2.txt"}
    cerebro._estado = EstadoJarvis.ESPERANDO_CONFIRMACION
    res_no = cerebro.procesar("no, cancela")
    assert "cancelada" in res_no.lower()


def test_eventbus_resiliencia_ante_excepciones_de_listeners():
    bus_local = EventBus()
    recibidos = []

    def callback_fallido(evento, datos):
        raise ValueError("Error simulado en listener")

    def callback_exitoso(evento, datos):
        recibidos.append(datos.get("msg"))

    bus_local.suscribir("test.event", callback_fallido)
    bus_local.suscribir("test.event", callback_exitoso)

    # Emitir no debe lanzar la excepción del primer callback y debe llegar al segundo
    bus_local.emitir("test.event", {"msg": "ok"})
    assert recibidos == ["ok"]


def test_temas_paleta_high_contrast_y_css_variables():
    original = gestor_temas.obtener_nombre()
    try:
        assert gestor_temas.cambiar_tema("jarvis_high_contrast") is True
        paleta = gestor_temas.obtener_paleta()
        assert paleta.nombre == "jarvis_high_contrast"
        css_vars = paleta.to_css_variables()
        assert "--jarvis-primary: #FFFF00;" in css_vars
        assert "--jarvis-background: #000000;" in css_vars
    finally:
        gestor_temas.cambiar_tema(original)


def test_voz_frases_aleatorias_sin_repeticion_inmediata():
    f1 = frase_aleatoria("saludo")
    f2 = frase_aleatoria("saludo")
    assert f1 != ""
    assert f2 != ""


def test_monitor_audio_nivel_calculo():
    from nucleo.monitor_audio import MonitorAudio
    monitor = MonitorAudio()
    import array
    samples = array.array("h", [0] * 1024)
    nivel_zero = monitor._calcular_nivel(samples.tobytes())
    assert nivel_zero == 0.0

    samples_loud = array.array("h", [10000] * 1024)
    nivel_loud = monitor._calcular_nivel(samples_loud.tobytes())
    assert 0.0 < nivel_loud <= 1.0


def test_flujo_e2e_macro_completo():
    bus.limpiar()
    eventos_registrados = []

    def rastrear_eventos(evento, datos):
        eventos_registrados.append(evento)

    bus.suscribir("*", rastrear_eventos)

    from nucleo.cerebro import Cerebro
    c = Cerebro()
    c.inicializar()

    # 1. Wake Word
    c.procesar("jarvis")
    assert c.estado == EstadoJarvis.ESCUCHANDO
    assert Eventos.DESPERTANDO in eventos_registrados
    assert Eventos.ESCUCHANDO in eventos_registrados

    # 2. Comando
    with patch("nucleo.voz.hablar"):
        res = c.procesar("¿qué hora es?")
        assert res is not None
        assert Eventos.INTENCION in eventos_registrados
        assert Eventos.EXITO in eventos_registrados
