"""
tests/test_calculadora.py — Tests del plugin de calculadora.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from plugins.calculadora import _normalizar_expresion, evaluar, _formatear_resultado


class TestNormalizacionMatematica:
    def test_raiz_cuadrada(self):
        expr = _normalizar_expresion("raíz de 16")
        assert expr and "sqrt(16)" in expr

    def test_raiz_cuadrada_alt(self):
        expr = _normalizar_expresion("raíz cuadrada de 25")
        assert expr and "sqrt(25)" in expr

    def test_potencia(self):
        expr = _normalizar_expresion("2 elevado a 8")
        assert expr and "2**8" in expr

    def test_cuadrado(self):
        expr = _normalizar_expresion("4 al cuadrado")
        assert expr and "4**2" in expr

    def test_cubo(self):
        expr = _normalizar_expresion("3 al cubo")
        assert expr and "3**3" in expr

    def test_porcentaje(self):
        expr = _normalizar_expresion("15 porciento de 200")
        assert expr is not None
        resultado = evaluar(expr)
        assert resultado == pytest.approx(30.0)

    def test_logaritmo(self):
        expr = _normalizar_expresion("logaritmo de 100")
        assert expr and "log" in expr


class TestEvaluacion:
    @pytest.mark.parametrize("expresion,esperado", [
        ("2 + 3", 5),
        ("10 - 4", 6),
        ("3 * 7", 21),
        ("20 / 4", 5),
        ("2**8", 256),
        ("sqrt(144)", 12),
        ("(10 / 100) * 200", 20),
    ])
    def test_operaciones_basicas(self, expresion, esperado):
        resultado = evaluar(expresion)
        assert resultado == pytest.approx(esperado)

    def test_division_por_cero(self):
        resultado = evaluar("1 / 0")
        assert resultado is None

    def test_expresion_invalida(self):
        resultado = evaluar("import os")
        assert resultado is None

    def test_expresion_vacia(self):
        resultado = evaluar("")
        assert resultado is None


class TestFormato:
    def test_entero(self):
        assert _formatear_resultado(5.0) == "5"

    def test_decimal(self):
        resultado = _formatear_resultado(3.14159)
        assert "3.14" in resultado

    def test_entero_grande(self):
        assert _formatear_resultado(256.0) == "256"


class TestPluginCompleto:
    def test_plugin_raiz(self):
        import plugins.calculadora  # noqa: F401
        import plugins
        plugin = plugins.obtener_plugin("CALCULAR")
        assert plugin is not None
        respuesta = plugin.manejar("CALCULAR", {"expresion": "raíz de 144"}, {})
        assert "12" in respuesta

    def test_plugin_suma(self):
        import plugins
        plugin = plugins.obtener_plugin("CALCULAR")
        assert plugin is not None
        respuesta = plugin.manejar("CALCULAR", {"expresion": "5 + 8"}, {})
        assert "13" in respuesta

    def test_plugin_sin_expresion(self):
        import plugins
        plugin = plugins.obtener_plugin("CALCULAR")
        assert plugin is not None
        respuesta = plugin.manejar("CALCULAR", {}, {})
        assert "calcular" in respuesta.lower() or "qué" in respuesta.lower()
