"""
tests/test_nlp.py — Tests del motor NLP de Jarvis.

Cubre: normalización, corrección fonética, extracción de intenciones y entidades.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from nucleo.nlp import normalizar, corregir_fonetico, analizar, extraer_intencion


class TestNormalizacion:
    def test_minusculas(self):
        assert normalizar("ABRE CHROME") == "abre chrome"

    def test_quita_tildes(self):
        resultado = normalizar("Abrí el archivo")
        assert "abri" in resultado

    def test_preserva_enie(self):
        resultado = normalizar("año")
        assert "año" in resultado

    def test_strip(self):
        assert normalizar("  hola  ") == "hola"

    def test_espacios_multiples(self):
        assert normalizar("abre   chrome") == "abre chrome"


class TestCorreccionFonetica:
    def test_docker(self):
        resultado = corregir_fonetico("doker")
        assert "docker" in resultado

    def test_chrome(self):
        resultado = corregir_fonetico("crome")
        assert "chrome" in resultado

    def test_google(self):
        resultado = corregir_fonetico("gugel")
        assert "google" in resultado

    def test_pgadmin(self):
        resultado = corregir_fonetico("pladmin")
        assert "pgadmin" in resultado

    def test_sin_correccion(self):
        resultado = corregir_fonetico("jarvis abre")
        assert "jarvis" in resultado
        assert "abre" in resultado


class TestExtraccionIntencion:
    @pytest.mark.parametrize("texto,intencion_esperada", [
        ("abre chrome", "ABRIR_APP"),
        ("ejecuta docker", "ABRIR_APP"),
        ("lanza tilix", "ABRIR_APP"),
        ("quiero abrir vscode", "ABRIR_APP"),
        ("busca python", "BUSCAR_WEB"),
        ("googlea laravel", "BUSCAR_WEB"),
        ("abre youtube", "ABRIR_WEB"),
        ("ve a github", "ABRIR_WEB"),
        ("qué hora es", "HORA"),
        ("qué fecha es", "FECHA"),
        ("cuánto es 5 más 3", "CALCULAR"),
        ("qué significa algoritmo", "DEFINIR"),
        ("sube el volumen", "LINUX_VOL_UP"),
        ("apaga el sistema", "LINUX_APAGAR"),
        ("git pull", "GIT_PULL"),
        ("git status", "GIT_STATUS"),
        ("crea una carpeta", "CREAR_CARPETA"),
        ("descansa", "DESCANSAR"),
        ("qué puedes hacer", "AYUDA"),
        ("en qué programa estoy", "VENTANA_ACTIVA"),
        ("qué aplicaciones tengo abiertas", "LISTAR_APLICACIONES"),
        ("cierra chrome", "CERRAR_APP"),
        ("trae docker al frente", "ENFOCAR_APP"),
        ("minimiza chrome", "MINIMIZAR_APP"),
        ("maximiza vscode", "MAXIMIZAR_APP"),
    ])
    def test_intencion(self, texto, intencion_esperada):
        intencion, confianza = extraer_intencion(normalizar(texto))
        assert intencion == intencion_esperada, (
            f"'{texto}' → esperaba '{intencion_esperada}', "
            f"obtuve '{intencion}' ({confianza:.0f}%)"
        )


class TestAnalisis:
    def test_analisis_completo_app(self):
        resultado = analizar("abre chrome por favor")
        assert resultado.intencion == "ABRIR_APP"
        assert "chrome" in resultado.entidades.get("app", "")
        assert resultado.confianza >= 65

    def test_analisis_con_error_fonetico(self):
        resultado = analizar("abre doker")
        assert resultado.intencion == "ABRIR_APP"
        assert resultado.tiene_intencion

    def test_analisis_calculo(self):
        resultado = analizar("cuánto es raíz de 144")
        assert resultado.intencion == "CALCULAR"
        assert resultado.entidades.get("expresion")

    def test_analisis_definicion(self):
        resultado = analizar("qué significa algoritmo")
        assert resultado.intencion == "DEFINIR"
        assert "algoritmo" in resultado.entidades.get("palabra", "")

    def test_sin_intencion(self):
        resultado = analizar("asdfghjkl")
        assert not resultado.tiene_intencion

    def test_busqueda_web(self):
        resultado = analizar("busca documentación de Python")
        assert resultado.intencion == "BUSCAR_WEB"
        assert resultado.entidades.get("query")
