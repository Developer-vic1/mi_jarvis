# 🤖 JARVIS — Asistente de Escritorio para Linux

**JARVIS** es un asistente personal inteligente de escritorio diseñado para entornos Linux (Ubuntu / GNOME / Wayland / X11) construido con **Python 3.12**, **GTK4 / Cairo**, **Piper TTS** y arquitectura basada en **EventBus pub/sub**.

---

## 🌟 Características Principales

- **Interfaz de Escritorio GTK4 Estilo Jarvis**: Núcleo visual animado en Cairo 2D con resplandor energético, partículas orbitales, conexiones de red neuronal dinámicas, pulsaciones rítmicas y forma de onda sincronizada.
- **Máquina de Estados Conversacional**:
  `REPOSO` → `DESPERTANDO` → `ESCUCHANDO` → `PROCESANDO` / `EJECUTANDO` → `HABLANDO` → `REPOSO`.
- **Detección de Wake Word**: Despierta al escuchar la palabra clave **"Jarvis"** (o "Oye Jarvis", "Hey Jarvis").
- **Voz TTS Local con Piper**: Síntesis de voz natural y fluida en segundo plano usando modelos Piper ONNX (`es_ES-davefx-medium.onnx`).
- **Control por Micrófono Continuo & Recuperación de Audio**: Monitoreo reactivo de nivel de audio y calibración automática de ruido ambiental.
- **Sistema de Temas y Paletas de Colores**:
  - `jarvis_classic` (Cyan eléctrico original)
  - `jarvis_cyber` (Verde neón Matrix)
  - `jarvis_red` (Rojo/naranja energético)
  - `jarvis_amber` (Ámbar dorado premium)
  - `jarvis_neutral` (Gris/blanco profesional)
  - `jarvis_high_contrast` (Alto contraste accesibilidad)
- **Instancia Única (Single Instance)**: Basado en Socket Unix (`~/.jarvis_single_instance.sock`) para evitar procesos duplicados.
- **Autostart e Integración con Linux**: Launcher desacoplado `jarvis_launcher.sh` y acceso autostart en `~/.config/autostart/jarvis.desktop`.

---

## 🏗️ Arquitectura del Sistema

```text
[ Micrófono / Audio ]
        ↓
  escucha.py / monitor_audio.py
        ↓
[ Cerebro (cerebro.py) ] ←── NLP (nlp.py) & Plugins (plugins/)
        ↓
   EventBus (eventos/bus.py)
   ┌────┴──────────────────────────┐
   ▼                               ▼
[ Interfaz GTK4 ]            [ Voz (voz.py) ]
 (Ventana, Núcleo Visual,      (Worker Piper TTS
  Panel Estado, Temas)           + aplay PCM)
```

---

## 🚀 Instalación y Requisitos

### Requisitos del Sistema (Linux)

```bash
sudo apt update
sudo apt install -y python3-gi python3-gi-cairo libgtk-4-dev gir1.2-gtk-4.0 aplay portaudio19-dev
```

### Entorno Virtual (venv)

El entorno virtual debe crearse incluyendo los paquetes del sistema para permitir el acceso a `gi` (PyGObject) y GTK4:

```bash
cd /home/victor/mi_jarvis
python3 -m venv --system-site-packages venv
./venv/bin/pip install speechrecognition pyaudio rapidfuzz pytest
```

---

## 💻 Modos de Ejecución

### 1. Interfaz GTK4 Principal (Modo Normal)

```bash
./venv/bin/python main.py
```
o mediante el launcher:
```bash
./jarvis_launcher.sh
```

### 2. Modo Demostración Visual (Demo)

Cicla automáticamente por todos los estados visuales para pruebas de UI sin necesidad de micrófono:

```bash
./venv/bin/python main.py --demo
```

### 3. Modo Consola (Fallback sin GTK)

```bash
./venv/bin/python main.py --console
```

### 4. Ayuda y Argumentos

```bash
./venv/bin/python main.py --help
```

---

## 🔧 Diagnóstico y Pruebas

### Diagnóstico del Sistema

Comprueba automáticamente la disponibilidad de Python, venv, GTK4, PyGObject, Piper, Micrófono, Audio, EventBus, Autostart y SingleInstance:

```bash
./venv/bin/python diagnostico.py
```

### Suite de Pruebas Completa

Ejecuta el pipeline de pruebas completo (diagnóstico, compilación de sintaxis, 113+ pytest unitarios/integración, imports, launcher y autostart):

```bash
bash test_completo.sh
```

### Tests Unitarios (Pytest)

```bash
./venv/bin/python -m pytest tests/ -q
```

---

## ⚙️ Autostart al Iniciar Linux

JARVIS incluye la configuración `.desktop` para iniciar automáticamente con GNOME:

- **Archivo Launcher**: `/home/victor/mi_jarvis/jarvis_launcher.sh`
- **Archivo Autostart**: `~/.config/autostart/jarvis.desktop`

Para habilitar o deshabilitar autostart:
```bash
cp /home/victor/mi_jarvis/jarvis.desktop ~/.config/autostart/jarvis.desktop
```

---

## 📜 Licencia y Créditos

Desarrollado para Ubuntu Linux. Todos los derechos reservados.
