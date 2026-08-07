#!/usr/bin/env bash
# jarvis_launcher.sh — Script de arranque de Jarvis desde el venv.
#
# Garantiza:
# - Ejecución desde el directorio correcto del proyecto
# - Uso del Python del venv (con GTK4/gi disponible)
# - Sin terminal visible cuando se lanza desde autostart
# - Variable JARVIS_DEBUG=1 para activar modo debug

set -euo pipefail

# Directorio del proyecto (siempre el mismo, absoluto)
JARVIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${JARVIS_DIR}/venv/bin/python"

# Verificar que el venv existe
if [ ! -f "${VENV_PYTHON}" ]; then
    echo "ERROR: No se encontró el Python del venv en ${VENV_PYTHON}"
    echo "Recrea el entorno virtual con: python3 -m venv --system-site-packages venv"
    exit 1
fi

# Asegurar que el directorio de datos existe
mkdir -p "${JARVIS_DIR}/datos" "${JARVIS_DIR}/logs"

# Ejecutar Jarvis desde el directorio correcto
cd "${JARVIS_DIR}"
exec "${VENV_PYTHON}" "${JARVIS_DIR}/main.py" "$@"
