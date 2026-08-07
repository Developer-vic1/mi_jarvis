#!/usr/bin/env bash
# jarvis_launcher.sh — Script de arranque de Jarvis desde el venv.
#
# Garantiza:
# - Ejecución desde el directorio correcto del proyecto
# - Uso del Python del venv (con GTK4/gi disponible)
# - Sin terminal visible cuando se lanza desde autostart
# - Registro de errores en logs/launcher.log
# - Ejecución desacoplada de la terminal salvo JARVIS_FOREGROUND=1

set -euo pipefail

# Directorio del proyecto resuelto desde la ubicación real del launcher
JARVIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${JARVIS_DIR}/venv/bin/python"
LOG_DIR="${JARVIS_DIR}/logs"
LAUNCHER_LOG="${LOG_DIR}/launcher.log"

# Verificar que el venv existe
if [ ! -f "${VENV_PYTHON}" ]; then
    echo "ERROR: No se encontró el Python del venv en ${VENV_PYTHON}"
    echo "Recrea el entorno virtual con: python3 -m venv --system-site-packages venv"
    exit 1
fi

# Asegurar que el directorio de datos existe
mkdir -p "${JARVIS_DIR}/datos" "${LOG_DIR}"

export PYTHONUNBUFFERED=1
export JARVIS_DIR
export GDK_BACKEND="${GDK_BACKEND:-wayland,x11}"

# Ejecutar Jarvis desde el directorio correcto
cd "${JARVIS_DIR}"

if [ "${JARVIS_FOREGROUND:-0}" = "1" ]; then
    exec "${VENV_PYTHON}" "${JARVIS_DIR}/main.py" "$@" >>"${LAUNCHER_LOG}" 2>&1
fi

if command -v setsid >/dev/null 2>&1; then
    setsid "${VENV_PYTHON}" "${JARVIS_DIR}/main.py" "$@" >>"${LAUNCHER_LOG}" 2>&1 < /dev/null &
else
    nohup "${VENV_PYTHON}" "${JARVIS_DIR}/main.py" "$@" >>"${LAUNCHER_LOG}" 2>&1 < /dev/null &
fi

disown || true
exit 0
