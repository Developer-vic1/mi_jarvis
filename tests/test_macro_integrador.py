"""
tests/test_macro_integrador.py — Test automatizado para la macro ABRIR_INTEGRADOR.
"""

import os
import sys
import time
import subprocess
import urllib.request

# Agregar directorio raíz al path de Python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from macros.gestor_macros import cargar_macros, ejecutar_macro
from nucleo.nlp import analizar


def probar_macro_integrador():
    print("\n========================================================")
    print("🚀 INICIANDO TEST AUTOMATIZADO DE LA MACRO ABRIR_INTEGRADOR")
    print("========================================================\n")

    # 1. Probar reconocimiento NLP
    frases_test = [
        "abre mi integrador",
        "abrir integrador",
        "inicia mi integrador",
        "abre proyecto integrador",
        "abre el proyecto",
        "carga el proyecto",
        "abre entorno de trabajo",
        "carga entorno",
        "abre savp",
        "abre savp tis3",
        "inicia savp",
        "proyecto savp",
        "trabajo integrador",
        "quiero trabajar",
        "vamos a programar",
    ]

    print("--- 1. VERIFICACIÓN NLP DE PRIORIDAD ABSOLUTA DE FRASES ---")
    nlp_paso = True
    for frase in frases_test:
        resultado = analizar(frase)
        es_correcta = resultado.intencion == "ABRIR_INTEGRADOR"
        simbolo = "✓" if es_correcta else "✗"
        print(f"  [{simbolo}] Frase: '{frase}' -> Intención: {resultado.intencion} ({resultado.confianza:.0f}%)")
        if not es_correcta:
            nlp_paso = False

    if not nlp_paso:
        print("\n❌ FALLO EN RECONOCIMIENTO NLP. Algunas frases no identificaron ABRIR_INTEGRADOR.")
        return False

    # 2. Inicializar macros
    cargar_macros()

    # 3. Ejecutar la Macro
    print("\n--- 2. EJECUTANDO MACRO ABRIR_INTEGRADOR ---")
    exito_exec, msg_exec = ejecutar_macro("ABRIR_INTEGRADOR")
    print(f"Resultado de ejecución: Éxito={exito_exec} | Mensaje: {msg_exec}")

    # 4. Realizar las 7 verificaciones estrictas requeridas
    print("\n--- 3. VERIFICACIONES DE ESTADO Y SERVICIOS TRAS LA MACRO ---")
    verificaciones = {}

    # Check 1: Existe la carpeta del proyecto
    ruta_proj = "/home/victor/UNIFRANZ/savp-tis3"
    verificaciones["1. Carpeta de proyecto existe"] = os.path.exists(ruta_proj)

    # Check 2: Se abrió el editor (antigravity, code, cursor)
    try:
        res_ed = subprocess.run(["pgrep", "-f", "antigravity|code|cursor"], capture_output=True, text=True)
        verificaciones["2. Editor de código abierto"] = bool(res_ed.stdout.strip())
    except Exception:
        verificaciones["2. Editor de código abierto"] = False

    # Check 3: Chrome fue lanzado
    try:
        res_chrome = subprocess.run(["pgrep", "-f", "chrome"], capture_output=True, text=True)
        verificaciones["3. Google Chrome fue lanzado"] = bool(res_chrome.stdout.strip())
    except Exception:
        verificaciones["3. Google Chrome fue lanzado"] = False

    # Check 4: Docker está activo
    try:
        res_docker = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=5)
        verificaciones["4. Docker servicio activo"] = res_docker.returncode == 0
    except Exception:
        verificaciones["4. Docker servicio activo"] = False

    # Check 5: Sail quedó arriba
    try:
        res_sail = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=5)
        verificaciones["5. Contenedores Sail activos"] = (
            res_sail.returncode == 0 and
            ("savp-tis3" in res_sail.stdout or "laravelsail" in res_sail.stdout or res_sail.stdout.count('\n') > 1)
        )
    except Exception:
        verificaciones["5. Contenedores Sail activos"] = False

    # Check 6: Servidor web responde (HTTP localhost)
    web_ok = False
    for puerto in [8000, 80, 8080]:
        try:
            url = f"http://localhost:{puerto}"
            req = urllib.request.Request(url, headers={"User-Agent": "Jarvis-Test"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status in [200, 301, 302, 404]:
                    web_ok = True
                    break
        except Exception:
            pass
    verificaciones["6. Servidor Docker/Nginx responde (HTTP)"] = web_ok

    # Check 7: npm run dev continúa ejecutándose
    try:
        res_npm = subprocess.run(["pgrep", "-f", "vite|npm run dev"], capture_output=True, text=True)
        verificaciones["7. npm run dev continúa ejecutándose"] = bool(res_npm.stdout.strip())
    except Exception:
        verificaciones["7. npm run dev continúa ejecutándose"] = False

    # Resumen de verificaciones
    print("\n--- RESUMEN DE COMPROBACIONES ---")
    todo_ok = True
    for nombre, resultado in verificaciones.items():
        simbolo = "✓" if resultado else "✗"
        print(f"  [{simbolo}] {nombre}: {'APROBADO' if resultado else 'FALLIDO'}")
        if not resultado:
            todo_ok = False

    if todo_ok:
        print("\n🎉 TODAS LAS VERIFICACIONES (7/7) PASARON EXITOSAMENTE.")
    else:
        print("\n⚠️ ALGUNAS VERIFICACIONES FALLARON. REVISAR RESULTADOS ARRIBA.")

    return todo_ok


if __name__ == "__main__":
    exito = probar_macro_integrador()
    sys.exit(0 if exito else 1)
