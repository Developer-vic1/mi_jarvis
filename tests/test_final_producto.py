import os
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from eventos.bus import EventBus, Eventos, bus
from modulos.gestor_aplicaciones import GestorAplicaciones, VentanaInfo
from nucleo.single_instance import SingleInstance
from temas.gestor_temas import Paleta, gestor_temas


def test_eventbus_comodin_y_evento_directo():
    event_bus = EventBus()
    recibidos = []

    event_bus.suscribir(Eventos.COMMAND_RECEIVED, lambda evento, datos: recibidos.append((evento, datos)))
    event_bus.suscribir("*", lambda evento, datos: recibidos.append(("*", evento)))
    event_bus.emitir(Eventos.COMMAND_RECEIVED, {"texto": "jarvis"})

    assert (Eventos.COMMAND_RECEIVED, {"texto": "jarvis"}) in recibidos
    assert ("*", Eventos.COMMAND_RECEIVED) in recibidos


def test_paleta_expone_estructura_semantica_y_emite_cambio():
    recibidos = []
    bus.suscribir(Eventos.CAMBIO_TEMA, lambda evento, datos: recibidos.append(datos))
    try:
        original = gestor_temas.obtener_nombre()
        assert gestor_temas.cambiar_tema("jarvis_cyber") is True
        paleta = gestor_temas.obtener_paleta()

        assert isinstance(paleta, Paleta)
        assert paleta.background == paleta.BACKGROUND
        assert paleta.surface == paleta.SURFACE
        assert paleta.primary == paleta.PRIMARY
        assert paleta.secondary == paleta.SECONDARY
        assert paleta.accent == paleta.ACCENT
        assert paleta.text == paleta.TEXT
        assert paleta.muted == paleta.TEXT_DIM
        assert paleta.success == paleta.SUCCESS
        assert paleta.warning == paleta.WARNING
        assert paleta.error == paleta.ERROR
        assert any(d.get("nombre_tema") == "jarvis_cyber" for d in recibidos)
    finally:
        gestor_temas.cambiar_tema(original)
        bus.limpiar()


def test_single_instance_segunda_invocacion_activa_existente(tmp_path, monkeypatch):
    import nucleo.single_instance as single_instance_mod

    socket_path = tmp_path / "jarvis.sock"
    monkeypatch.setattr(single_instance_mod, "_SOCKET_PATH", str(socket_path))

    activado = threading.Event()
    primera = SingleInstance(callback_mostrar=lambda: activado.set())
    assert primera.adquirir() is True
    try:
        segunda = SingleInstance()
        assert segunda.adquirir() is False
        assert activado.wait(1.5)
    finally:
        primera.liberar()


def test_detecta_ventana_activa_linux_por_xdotool():
    gestor = GestorAplicaciones()
    ventana = VentanaInfo("0x0000002a", 0, 123, "code.Code", "host", "main.py - Code")

    def fake_cmd(cmd, timeout=5.0):
        if cmd == ["xdotool", "getactivewindow"]:
            return True, str(int("0x0000002a", 16))
        return False, ""

    gestor._ejecutar_comando = fake_cmd
    gestor.listar_ventanas = lambda: [ventana]

    activa = gestor.obtener_ventana_activa()
    assert activa is not None
    assert gestor.obtener_nombre_amigable_app(activa) == "Visual Studio Code"


@patch.object(GestorAplicaciones, "buscar_ventana")
@patch.object(GestorAplicaciones, "enfocar_ventana")
@patch("modulos.gestor_aplicaciones.subprocess.Popen")
def test_ensure_application_open_reutiliza_ventana_existente(mock_popen, mock_enfocar, mock_buscar):
    gestor = GestorAplicaciones()
    mock_buscar.return_value = VentanaInfo("0x123", 0, 100, "google-chrome", "host", "Chrome")
    mock_enfocar.return_value = True

    ok, msg = gestor.ensure_application_open("chrome")

    assert ok is True
    assert "ya estaba abierta" in msg
    mock_enfocar.assert_called_once_with("0x123")
    mock_popen.assert_not_called()


@patch.object(GestorAplicaciones, "buscar_ventana")
@patch.object(GestorAplicaciones, "buscar_proceso")
def test_cerrar_aplicacion_informa_si_no_esta_abierta(mock_proceso, mock_buscar):
    gestor = GestorAplicaciones()
    mock_buscar.return_value = None
    mock_proceso.return_value = []

    ok, msg = gestor.cerrar_aplicacion("chrome")

    assert ok is False
    assert "No encontr" in msg


def test_launcher_y_autostart_apuntan_al_launcher_correcto():
    proyecto = Path(__file__).resolve().parents[1]
    launcher = proyecto / "jarvis_launcher.sh"
    desktop = proyecto / "jarvis.desktop"
    autostart = Path.home() / ".config" / "autostart" / "jarvis.desktop"

    assert launcher.exists()
    assert os.access(launcher, os.X_OK)
    assert "venv/bin/python" in launcher.read_text(encoding="utf-8")
    assert "main.py" in launcher.read_text(encoding="utf-8")

    expected_exec = "Exec=/home/victor/mi_jarvis/jarvis_launcher.sh"
    assert expected_exec in desktop.read_text(encoding="utf-8")
    assert expected_exec in autostart.read_text(encoding="utf-8")


def test_nucleo_visual_estados_minimos_si_hay_display():
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk

    if Gdk.Display.get_default() is None:
        pytest.skip("No hay display GTK disponible para instanciar DrawingArea")

    from interfaz.nucleo_visual import NucleoVisual

    nucleo = NucleoVisual()
    try:
        for estado in [
            "reposo", "escuchando", "procesando", "ejecutando",
            "hablando", "error", "esperando", "exito",
        ]:
            nucleo.set_estado(estado)
            assert nucleo._estado == estado
        nucleo.set_nivel_audio(2.0)
        assert nucleo._nivel_audio == 1.0
    finally:
        nucleo.detener()
