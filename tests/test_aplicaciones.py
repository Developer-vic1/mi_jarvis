"""
tests/test_aplicaciones.py — Tests del plugin de aplicaciones.

Nota: usa el índice real de apps instaladas en el sistema.
Los tests de fuzzy matching solo verifican que la búsqueda no crashea.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# pyrefly: ignore [missing-import]
import pytest
from plugins.aplicaciones import GestorApps, construir_indice, AppEntry, _limpiar_exec


class TestIndiceApps:
    def test_construir_indice_no_vacio(self):
        apps = construir_indice()
        assert len(apps) > 0, "El índice de apps no debe estar vacío"

    def test_apps_tienen_nombre_y_exec(self):
        apps = construir_indice()
        for app in apps:
            assert app.nombre, f"App sin nombre: {app}"
            assert app.exec_cmd, f"App sin exec_cmd: {app.nombre}"

    def test_apps_tienen_aliases(self):
        apps = construir_indice()
        for app in apps:
            assert len(app.aliases) >= 1, f"App sin aliases: {app.nombre}"

    def test_serialization(self):
        apps = construir_indice()
        if apps:
            d = apps[0].to_dict()
            app2 = AppEntry.from_dict(d)
            assert app2.nombre == apps[0].nombre


class TestBusquedaFuzzy:
    @pytest.fixture
    def gestor(self):
        return GestorApps()

    @pytest.mark.parametrize("nombre", [
        "chrome", "google chrome", "tilix", "terminal",
        "docker", "pgadmin", "calculadora",
    ])
    def test_busqueda_no_crashea(self, gestor, nombre):
        # Solo verificar que no lanza excepción
        resultado = gestor.buscar(nombre, umbral=50)
        # El resultado puede ser None si la app no está instalada

    def test_busqueda_vacia(self, gestor):
        resultado = gestor.buscar("")
        assert resultado is None

    def test_busqueda_google_chrome(self, gestor):
        resultado = gestor.buscar("google chrome")
        # Si Google Chrome está instalado, debe encontrarlo
        apps_sistema = [a.nombre.lower() for a in construir_indice()]
        if any("google chrome" in a for a in apps_sistema):
            assert resultado is not None
            assert "Chrome" in resultado.nombre or "chrome" in resultado.nombre.lower()


class TestLimpiarExec:
    def test_elimina_placeholders(self):
        args = _limpiar_exec("/usr/bin/chrome %U")
        assert "%U" not in " ".join(args)
        assert "/usr/bin/chrome" in args

    def test_exec_con_comillas(self):
        args = _limpiar_exec('"/usr/bin/app" --flag %F')
        assert "/usr/bin/app" in args

    def test_exec_vacio(self):
        args = _limpiar_exec("")
        assert args == []
