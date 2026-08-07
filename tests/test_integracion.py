"""
tests/test_integracion.py — Tests de integración del sistema Jarvis.

Prueba el flujo completo: NLP → Plugin → Respuesta.
No activa el micrófono ni el TTS (mockeados).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch
# pyrefly: ignore [missing-import]
import pytest

import plugins
import plugins.calculadora      # noqa: F401
import plugins.datetime_info    # noqa: F401
import plugins.ayuda            # noqa: F401


class TestFlujoCompleto:
    """Tests de integración del ciclo NLP → Plugin → Respuesta."""

    @patch("nucleo.voz.hablar")
    def test_hora(self, mock_hablar):
        from nucleo.cerebro import Cerebro
        cerebro = Cerebro()
        cerebro._activar_sesion()

        with patch("nucleo.cerebro.hablar"):
            respuesta = cerebro.procesar("qué hora es")

        assert respuesta is not None
        assert "son las" in respuesta.lower() or ":" in respuesta

    @patch("nucleo.voz.hablar")
    def test_fecha(self, mock_hablar):
        from nucleo.cerebro import Cerebro
        cerebro = Cerebro()
        cerebro._activar_sesion()

        with patch("nucleo.cerebro.hablar"):
            respuesta = cerebro.procesar("qué fecha es hoy")

        assert respuesta is not None
        assert any(mes in respuesta.lower() for mes in [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ])

    @patch("nucleo.voz.hablar")
    def test_calculo(self, mock_hablar):
        from nucleo.cerebro import Cerebro
        cerebro = Cerebro()
        cerebro._activar_sesion()

        with patch("nucleo.cerebro.hablar"):
            respuesta = cerebro.procesar("cuánto es 10 más 5")

        assert respuesta is not None
        assert "15" in respuesta

    @patch("nucleo.voz.hablar")
    def test_wake_word_activa_sesion(self, mock_hablar):
        from nucleo.cerebro import Cerebro, EstadoJarvis
        cerebro = Cerebro()

        assert cerebro.estado == EstadoJarvis.REPOSO

        with patch("nucleo.cerebro.hablar"):
            with patch("nucleo.cerebro.hablar_contexto"):
                cerebro.procesar("jarvis")

        assert cerebro.estado == EstadoJarvis.ESCUCHANDO

    @patch("nucleo.voz.hablar")
    def test_sleep_word_desactiva_sesion(self, mock_hablar):
        from nucleo.cerebro import Cerebro, EstadoJarvis
        cerebro = Cerebro()
        cerebro._activar_sesion()

        assert cerebro.estado == EstadoJarvis.ESCUCHANDO

        with patch("nucleo.cerebro.hablar"):
            with patch("nucleo.cerebro.hablar_contexto"):
                cerebro.procesar("descansa")

        assert cerebro.estado == EstadoJarvis.REPOSO

    @patch("nucleo.voz.hablar")
    def test_modo_reposo_ignora_comandos(self, mock_hablar):
        from nucleo.cerebro import Cerebro, EstadoJarvis
        cerebro = Cerebro()

        assert cerebro.estado == EstadoJarvis.REPOSO

        with patch("nucleo.cerebro.hablar"):
            respuesta = cerebro.procesar("abre chrome")

        assert respuesta is None  # En reposo, ignora comandos sin wake word
        assert cerebro.estado == EstadoJarvis.REPOSO

    @patch("nucleo.voz.hablar")
    def test_ayuda(self, mock_hablar):
        from nucleo.cerebro import Cerebro
        cerebro = Cerebro()
        cerebro._activar_sesion()

        with patch("nucleo.cerebro.hablar"):
            respuesta = cerebro.procesar("qué puedes hacer")

        assert respuesta is not None
        assert len(respuesta) > 20  # Debe tener contenido

    def test_plugins_registrados(self):
        """Verifica que los plugins esenciales estén registrados."""
        import plugins.linux       # noqa: F401
        import plugins.web         # noqa: F401
        import plugins.archivos    # noqa: F401

        intenciones_requeridas = [
            "CALCULAR", "HORA", "FECHA", "AYUDA",
            "ABRIR_APP", "BUSCAR_WEB", "LINUX_VOL_UP",
        ]
        for intencion in intenciones_requeridas:
            plugin = plugins.obtener_plugin(intencion)
            assert plugin is not None, f"Intención '{intencion}' no tiene plugin registrado"


class TestMemoria:
    def test_guardar_y_recuperar_preferencia(self):
        from nucleo.memoria import guardar_preferencia, obtener_preferencia
        guardar_preferencia("test_clave", "test_valor")
        valor = obtener_preferencia("test_clave")
        assert valor == "test_valor"

    def test_preferencia_default(self):
        from nucleo.memoria import obtener_preferencia
        valor = obtener_preferencia("clave_inexistente", "default_test")
        assert valor == "default_test"

    def test_alias(self):
        from nucleo.memoria import registrar_alias, resolver_alias
        registrar_alias("mi_alias_test", "abrir chrome")
        resultado = resolver_alias("mi_alias_test")
        assert resultado == "abrir chrome"

    def test_alias_inexistente(self):
        from nucleo.memoria import resolver_alias
        resultado = resolver_alias("alias_que_no_existe_xyzxyz")
        assert resultado is None
