"""
tests/test_gestor_aplicaciones.py — Tests para el módulo GestorAplicaciones.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modulos.gestor_aplicaciones import GestorAplicaciones, VentanaInfo


class TestGestorAplicaciones(unittest.TestCase):

    def setUp(self):
        self.gestor = GestorAplicaciones()

    def test_listar_ventanas_no_crashea(self):
        # Debe ejecutar wmctrl sin lanzar excepciones
        ventanas = self.gestor.listar_ventanas()
        self.assertIsInstance(ventanas, list)

    def test_listar_ventanas_usuario_no_crashea(self):
        ventanas = self.gestor.listar_ventanas_usuario()
        self.assertIsInstance(ventanas, list)

    def test_obtener_ventana_activa_no_crashea(self):
        activa = self.gestor.obtener_ventana_activa()
        self.assertTrue(activa is None or isinstance(activa, dict))

    def test_obtener_nombre_amigable_app(self):
        self.assertEqual(
            self.gestor.obtener_nombre_amigable_app({"titulo": "test.py - Code", "wm_class": "code.Code"}),
            "Visual Studio Code"
        )
        self.assertEqual(
            self.gestor.obtener_nombre_amigable_app({"titulo": "Google - Google Chrome", "wm_class": "google-chrome"}),
            "Google Chrome"
        )
        self.assertEqual(
            self.gestor.obtener_nombre_amigable_app({"titulo": "Tilix Terminal", "wm_class": "tilix"}),
            "Tilix"
        )

    @patch.object(GestorAplicaciones, "buscar_ventana")
    @patch.object(GestorAplicaciones, "enfocar_ventana")
    def test_abrir_aplicacion_existente(self, mock_enfocar, mock_buscar):
        mock_buscar.return_value = VentanaInfo("0x123", 0, 100, "google-chrome", "host", "Chrome")
        mock_enfocar.return_value = True

        ok, msg = self.gestor.abrir_aplicacion("chrome")
        self.assertTrue(ok)
        self.assertIn("ya estaba abierta", msg)
        mock_enfocar.assert_called_with("0x123")

    @patch.object(GestorAplicaciones, "buscar_ventana")
    @patch.object(GestorAplicaciones, "buscar_proceso")
    @patch.object(GestorAplicaciones, "_ejecutar_comando")
    def test_cerrar_aplicacion_elegante(self, mock_cmd, mock_proceso, mock_buscar):
        # 1er llamado a buscar_ventana -> la encuentra. 2do llamado -> ya no existe.
        v = VentanaInfo("0x456", 0, 200, "code", "host", "VSCode")
        mock_buscar.side_effect = [v, None]
        mock_proceso.return_value = []
        mock_cmd.return_value = (True, "")

        ok, msg = self.gestor.cerrar_aplicacion("vscode")
        self.assertTrue(ok)
        self.assertIn("cerró", msg)
        mock_cmd.assert_called_with(["wmctrl", "-i", "-c", "0x456"])


if __name__ == "__main__":
    unittest.main()
