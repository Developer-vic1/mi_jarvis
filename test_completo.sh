#!/usr/bin/env bash
# test_completo.sh — Script de verificación integral para JARVIS
#
# Ejecuta diagnóstico, compilación, suite de pytest, validación de imports,
# launcher, autostart y single instance.

set -euo pipefail

JARVIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${JARVIS_DIR}/venv/bin/python"

cd "${JARVIS_DIR}"

echo "=========================================================="
echo "          J A R V I S   T E S T   S U I T E"
echo "=========================================================="

# 1. Diagnóstico
echo -e "\n[1/7] Ejecutando diagnóstico de componentes..."
"${VENV_PYTHON}" diagnostico.py || { echo "FAIL: Diagnóstico del sistema falló."; exit 1; }

# 2. Compilación de sintaxis
echo -e "\n[2/7] Verificando compilación de sintaxis Python (py_compile)..."
"${VENV_PYTHON}" -m py_compile main.py config.py diccionarios.py diagnostico.py \
    eventos/*.py interfaz/*.py macros/*.py modulos/*.py nucleo/*.py plugins/*.py temas/*.py || {
    echo "FAIL: Error en compilación de sintaxis Python."; exit 1;
}

# 3. Tests unitarios e integración (Pytest)
echo -e "\n[3/7] Ejecutando tests unitarios e integración con pytest..."
"${VENV_PYTHON}" -m pytest tests/ -q || { echo "FAIL: Pruebas de pytest fallaron."; exit 1; }

# 4. Validación de imports principales
echo -e "\n[4/7] Validando importación limpia de módulos clave..."
"${VENV_PYTHON}" -c "
import main
import config
import eventos.bus
import temas.gestor_temas
import nucleo.cerebro
import nucleo.voz
import nucleo.escucha
import nucleo.single_instance
import interfaz.ventana_principal
import interfaz.nucleo_visual
import interfaz.panel_estado
print('Todos los módulos importados correctamente.')
" || { echo "FAIL: Falló la importación de módulos clave."; exit 1; }

# 5. Validación del launcher
echo -e "\n[5/7] Probando jarvis_launcher.sh (--help)..."
JARVIS_FOREGROUND=1 "${JARVIS_DIR}/jarvis_launcher.sh" --help > /dev/null 2>&1 || {
    echo "FAIL: Error al ejecutar jarvis_launcher.sh."; exit 1;
}

# 6. Validación de autostart
echo -e "\n[6/7] Validando configuración de autostart..."
AUTOSTART_FILE="${HOME}/.config/autostart/jarvis.desktop"
if [ -f "${AUTOSTART_FILE}" ] && grep -q "jarvis_launcher.sh" "${AUTOSTART_FILE}"; then
    echo "Autostart verificado en ${AUTOSTART_FILE}."
else
    echo "FAIL: Archivo autostart no válido o no encontrado en ${AUTOSTART_FILE}."; exit 1;
fi

# 7. Validación de Single Instance
echo -e "\n[7/7] Probando mecanismo de Single Instance..."
"${VENV_PYTHON}" -c "
from nucleo.single_instance import SingleInstance
s1 = SingleInstance()
assert s1.adquirir() is True
s2 = SingleInstance()
assert s2.adquirir() is False
s1.liberar()
print('SingleInstance verificado exitosamente.')
" || { echo "FAIL: Mecanismo SingleInstance falló."; exit 1; }

echo -e "\n=========================================================="
echo "JARVIS TEST SUITE"
echo "================="
echo "PASS"
echo "=========================================================="
exit 0
