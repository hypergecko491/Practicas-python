import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import threading
import subprocess
import time
import json
import os
import re

from pynput import keyboard


# ============================================================
# AUTÓCLICKER ANDROID V4
#
# Control mediante ADB
#
# F9  = iniciar/detener grabación
# F10 = iniciar/detener reproducción
# F12 = emergencia
# ESC = detener reproducción/grabación
#
# Graba:
#   - Tap
#   - Long press
#   - Swipe / arrastre
#
# Guarda:
#   - Coordenadas
#   - Tiempo entre eventos
#   - Duración del toque
#
# Requiere:
#   - Android
#   - USB debugging
#   - ADB
#   - Python
#   - pynput
#
# ============================================================


# ============================================================
# CONFIGURACIÓN
# ============================================================

ADB = "adb"

recording = False
playing = False

events = []

record_thread = None
play_thread = None

global_keyboard_listener = None

stop_record_event = threading.Event()
stop_play_event = threading.Event()

events_lock = threading.Lock()

last_event_time = None


# ============================================================
# VARIABLES DEL DISPOSITIVO
# ============================================================

device_width = 0
device_height = 0

touch_min_x = 0
touch_max_x = 0
touch_min_y = 0
touch_max_y = 0

touch_device = None


# ============================================================
# ADB
# ============================================================

def adb_command(args, timeout=10):

    command = [ADB] + args

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="ignore"
        )

        return (
            result.returncode,
            result.stdout,
            result.stderr
        )

    except FileNotFoundError:

        return (
            -1,
            "",
            "ADB no fue encontrado."
        )

    except subprocess.TimeoutExpired:

        return (
            -1,
            "",
            "ADB tardó demasiado tiempo."
        )

    except Exception as error:

        return (
            -1,
            "",
            str(error)
        )


# ============================================================
# COMPROBAR ADB
# ============================================================

def check_adb():

    code, stdout, stderr = adb_command(
        ["devices"]
    )

    if code != 0:

        return False, (
            "No se pudo ejecutar ADB.\n\n"
            "Comprueba que ADB esté instalado y "
            "disponible en PATH."
        )

    devices = []

    for line in stdout.splitlines():

        line = line.strip()

        if not line:
            continue

        if line.startswith("List of devices"):
            continue

        parts = line.split()

        if len(parts) >= 2:

            serial = parts[0]
            state = parts[1]

            devices.append(
                (serial, state)
            )

    if not devices:

        return False, (
            "No se encontró ningún dispositivo Android.\n\n"
            "Comprueba:\n"
            "• USB conectado\n"
            "• Depuración USB activada\n"
            "• ADB instalado"
        )

    for serial, state in devices:

        if state == "device":

            return True, serial

    return False, (
        "El teléfono fue detectado pero todavía "
        "no está autorizado.\n\n"
        "Revisa el teléfono y acepta la ventana "
        "de autorización de depuración USB."
    )


# ============================================================
# RESOLUCIÓN DEL TELÉFONO
# ============================================================

def get_device_resolution():

    global device_width
    global device_height

    code, stdout, stderr = adb_command(
        ["shell", "wm", "size"]
    )

    if code != 0:

        return False

    matches = re.findall(
        r"(\d+)x(\d+)",
        stdout
    )

    if not matches:

        return False

    # Tomamos la última resolución reportada.
    width, height = matches[-1]

    device_width = int(width)
    device_height = int(height)

    return True


# ============================================================
# INFORMACIÓN DEL TOUCHSCREEN
# ============================================================

def find_touch_device():

    global touch_device
    global touch_min_x
    global touch_max_x
    global touch_min_y
    global touch_max_y

    code, stdout, stderr = adb_command(
        [
            "shell",
            "getevent",
            "-lp"
        ],
        timeout=15
    )

    if code != 0:

        return False

    current_device = None
    found_device = None

    min_x = None
    max_x = None
    min_y = None
    max_y = None

    for line in stdout.splitlines():

        line = line.strip()

        # ----------------------------------------------------
        # /dev/input/eventX
        # ----------------------------------------------------

        if line.startswith("/dev/input/"):

            current_device = line.split()[0]

            min_x = None
            max_x = None
            min_y = None
            max_y = None

        # ----------------------------------------------------
        # ABS_MT_POSITION_X
        # ----------------------------------------------------

        if (
            "ABS_MT_POSITION_X" in line
            or "ABS_X" in line
        ):

            match = re.search(
                r"min\s+(-?\d+),\s*max\s+(-?\d+)",
                line
            )

            if match:

                min_x = int(
                    match.group(1)
                )

                max_x = int(
                    match.group(2)
                )

        # ----------------------------------------------------
        # ABS_MT_POSITION_Y
        # ----------------------------------------------------

        if (
            "ABS_MT_POSITION_Y" in line
            or "ABS_Y" in line
        ):

            match = re.search(
                r"min\s+(-?\d+),\s*max\s+(-?\d+)",
                line
            )

            if match:

                min_y = int(
                    match.group(1)
                )

                max_y = int(
                    match.group(2)
                )

        # ----------------------------------------------------
        # Si encontramos ambos ejes
        # ----------------------------------------------------

        if (
            current_device
            and min_x is not None
            and max_x is not None
            and min_y is not None
            and max_y is not None
        ):

            found_device = current_device

            touch_min_x = min_x
            touch_max_x = max_x

            touch_min_y = min_y
            touch_max_y = max_y

            break

    if found_device:

        touch_device = found_device

        return True

    return False


# ============================================================
# CONVERSIÓN DE COORDENADAS
# ============================================================

def touch_to_screen(raw_x, raw_y):

    # --------------------------------------------------------
    # Si tenemos límites reales del touchscreen,
    # convertimos a coordenadas de Android.
    # --------------------------------------------------------

    if (
        touch_max_x > touch_min_x
        and touch_max_y > touch_min_y
        and device_width > 0
        and device_height > 0
    ):

        x_ratio = (
            raw_x - touch_min_x
        ) / (
            touch_max_x - touch_min_x
        )

        y_ratio = (
            raw_y - touch_min_y
        ) / (
            touch_max_y - touch_min_y
        )

        x = int(
            x_ratio * device_width
        )

        y = int(
            y_ratio * device_height
        )

        x = max(
            0,
            min(device_width - 1, x)
        )

        y = max(
            0,
            min(device_height - 1, y)
        )

        return x, y

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    return raw_x, raw_y


# ============================================================
# TIEMPO
# ============================================================

def get_delay():

    global last_event_time

    now = time.perf_counter()

    if last_event_time is None:

        delay = 0

    else:

        delay = (
            now - last_event_time
        )

    last_event_time = now

    return delay


# ============================================================
# AGREGAR EVENTO
# ============================================================

def add_event(event):

    with events_lock:

        events.append(event)


# ============================================================
# ESPERA INTERRUPTIBLE
# ============================================================

def interruptible_sleep(seconds):

    if seconds <= 0:

        return True

    end_time = (
        time.perf_counter()
        + seconds
    )

    while (
        playing
        and not stop_play_event.is_set()
    ):

        remaining = (
            end_time
            - time.perf_counter()
        )

        if remaining <= 0:

            return True

        time.sleep(
            min(0.01, remaining)
        )

    return False


# ============================================================
# PARSER DE GETEVENT
# ============================================================

def parse_getevent_line(line):

    """
    Intenta convertir una línea de getevent -lt
    en un evento estructurado.

    Ejemplos típicos:

    /dev/input/event2:
    EV_ABS ABS_MT_POSITION_X 00000123

    EV_ABS ABS_MT_POSITION_Y 00000456

    EV_KEY BTN_TOUCH DOWN
    """

    line = line.strip()

    if not line:

        return None

    # --------------------------------------------------------
    # Buscar posición X
    # --------------------------------------------------------

    x_match = re.search(
        r"ABS_MT_POSITION_X\s+([0-9a-fA-F]+)",
        line
    )

    if not x_match:

        x_match = re.search(
            r"ABS_X\s+([0-9a-fA-F]+)",
            line
        )

    if x_match:

        try:

            value = int(
                x_match.group(1),
                16
            )

            return (
                "x",
                value
            )

        except Exception:

            pass

    # --------------------------------------------------------
    # Buscar posición Y
    # --------------------------------------------------------

    y_match = re.search(
        r"ABS_MT_POSITION_Y\s+([0-9a-fA-F]+)",
        line
    )

    if not y_match:

        y_match = re.search(
            r"ABS_Y\s+([0-9a-fA-F]+)",
            line
        )

    if y_match:

        try:

            value = int(
                y_match.group(1),
                16
            )

            return (
                "y",
                value
            )

        except Exception:

            pass

    # --------------------------------------------------------
    # DOWN
    # --------------------------------------------------------

    if (
        "BTN_TOUCH" in line
        and (
            "DOWN" in line
            or line.endswith(" 1")
            or line.endswith("00000001")
        )
    ):

        return (
            "down",
            True
        )

    # --------------------------------------------------------
    # UP
    # --------------------------------------------------------

    if (
        "BTN_TOUCH" in line
        and (
            "UP" in line
            or line.endswith(" 0")
            or line.endswith("00000000")
        )
    ):

        return (
            "up",
            True
        )

    return None


# ============================================================
# GRABACIÓN ANDROID
# ============================================================

def record_android():

    global recording
    global last_event_time

    last_event_time = time.perf_counter()

    # --------------------------------------------------------
    # Comando getevent
    # --------------------------------------------------------

    command = [
        ADB,
        "shell",
        "getevent",
        "-lt"
    ]

    if touch_device:

        command.append(
            touch_device
        )

    try:

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            bufsize=1
        )

    except Exception as error:

        recording = False

        root.after(
            0,
            lambda: messagebox.showerror(
                "Error",
                f"No se pudo iniciar la grabación:\n\n{error}"
            )
        )

        root.after(
            0,
            update_record_button
        )

        return

    current_x = None
    current_y = None

    touch_down = False

    start_x = None
    start_y = None

    start_time = None

    last_x = None
    last_y = None

    try:

        while (
            recording
            and not stop_record_event.is_set()
        ):

            line = process.stdout.readline()

            if not line:

                if process.poll() is not None:

                    break

                time.sleep(0.005)

                continue

            parsed = parse_getevent_line(
                line
            )

            if parsed is None:

                continue

            event_type, value = parsed

            # ------------------------------------------------
            # X
            # ------------------------------------------------

            if event_type == "x":

                current_x = value

            # ------------------------------------------------
            # Y
            # ------------------------------------------------

            elif event_type == "y":

                current_y = value

            # ------------------------------------------------
            # DOWN
            # ------------------------------------------------

            elif event_type == "down":

                if (
                    current_x is None
                    or current_y is None
                ):

                    continue

                x, y = touch_to_screen(
                    current_x,
                    current_y
                )

                touch_down = True

                start_x = x
                start_y = y

                last_x = x
                last_y = y

                start_time = time.perf_counter()

            # ------------------------------------------------
            # UP
            # ------------------------------------------------

            elif event_type == "up":

                if not touch_down:

                    continue

                if (
                    current_x is None
                    or current_y is None
                ):

                    continue

                x, y = touch_to_screen(
                    current_x,
                    current_y
                )

                duration = (
                    time.perf_counter()
                    - start_time
                )

                delay = get_delay()

                distance = (
                    abs(x - start_x)
                    + abs(y - start_y)
                )

                # ------------------------------------------------
                # TAP
                # ------------------------------------------------

                if distance < 30:

                    add_event({

                        "type": "tap",

                        "x": x,
                        "y": y,

                        "duration": duration,

                        "delay": delay
                    })

                # ------------------------------------------------
                # SWIPE
                # ------------------------------------------------

                else:

                    add_event({

                        "type": "swipe",

                        "x1": start_x,
                        "y1": start_y,

                        "x2": x,
                        "y2": y,

                        "duration": duration,

                        "delay": delay
                    })

                touch_down = False

                start_x = None
                start_y = None

                last_x = None
                last_y = None

    except Exception as error:

        if recording:

            root.after(
                0,
                lambda: messagebox.showerror(
                    "Error de grabación",
                    str(error)
                )
            )

    finally:

        try:

            process.terminate()

        except Exception:

            pass


# ============================================================
# INICIAR GRABACIÓN
# ============================================================

def start_recording():

    global recording
    global record_thread
    global events
    global last_event_time

    if playing:

        messagebox.showwarning(
            "Automatizador",
            "Detén la reproducción antes de grabar."
        )

        return

    if recording:

        stop_recording()

        return

    # --------------------------------------------------------
    # Comprobar dispositivo
    # --------------------------------------------------------

    connected, result = check_adb()

    if not connected:

        messagebox.showerror(
            "Android no conectado",
            result
        )

        return

    # --------------------------------------------------------
    # Resolución
    # --------------------------------------------------------

    get_device_resolution()

    # --------------------------------------------------------
    # Touchscreen
    # --------------------------------------------------------

    find_touch_device()

    # --------------------------------------------------------
    # Limpiar
    # --------------------------------------------------------

    with events_lock:

        events = []

    stop_record_event.clear()

    last_event_time = time.perf_counter()

    recording = True

    status_var.set(
        "🔴 GRABANDO — toca la pantalla del Android"
    )

    record_button.config(
        text="⏹ Detener grabación"
    )

    record_thread = threading.Thread(
        target=record_android,
        daemon=True
    )

    record_thread.start()


# ============================================================
# ACTUALIZAR BOTÓN
# ============================================================

def update_record_button():

    if recording:

        record_button.config(
            text="⏹ Detener grabación"
        )

    else:

        record_button.config(
            text="🔴 Grabar"
        )


# ============================================================
# DETENER GRABACIÓN
# ============================================================

def stop_recording():

    global recording

    if not recording:

        return

    recording = False

    stop_record_event.set()

    with events_lock:

        count = len(events)

    status_var.set(
        f"Grabación detenida — {count} eventos"
    )

    update_record_button()

    root.after(
        0,
        refresh_event_list
    )


# ============================================================
# REPRODUCCIÓN
# ============================================================

def play_events():

    global playing

    # ========================================================
    # VELOCIDAD
    # ========================================================

    try:

        speed = float(
            speed_var.get()
        )

        if speed <= 0:

            raise ValueError

    except ValueError:

        root.after(
            0,
            lambda: messagebox.showerror(
                "Error",
                "La velocidad debe ser mayor que 0."
            )
        )

        playing = False

        return

    # ========================================================
    # REPETICIONES
    # ========================================================

    try:

        repetitions_text = (
            repetitions_var
            .get()
            .strip()
            .lower()
        )

        if repetitions_text in (
            "∞",
            "inf",
            "infinito",
            "infinity"
        ):

            repetitions = None

        else:

            repetitions = int(
                repetitions_text
            )

            if repetitions < 1:

                raise ValueError

    except ValueError:

        root.after(
            0,
            lambda: messagebox.showerror(
                "Error",
                "Repeticiones debe ser un número entero o ∞."
            )
        )

        playing = False

        return

    # ========================================================
    # PAUSA
    # ========================================================

    try:

        loop_delay = float(
            loop_delay_var.get()
        )

        if loop_delay < 0:

            raise ValueError

    except ValueError:

        root.after(
            0,
            lambda: messagebox.showerror(
                "Error",
                "La pausa entre ciclos debe ser 0 o mayor."
            )
        )

        playing = False

        return

    # ========================================================
    # EVENTOS
    # ========================================================

    with events_lock:

        playback_events = list(events)

    count = 0

    # ========================================================
    # REPRODUCCIÓN
    # ========================================================

    try:

        while (
            playing
            and not stop_play_event.is_set()
            and (
                repetitions is None
                or count < repetitions
            )
        ):

            for event in playback_events:

                if (
                    not playing
                    or stop_play_event.is_set()
                ):

                    break

                # ------------------------------------------------
                # DELAY
                # ------------------------------------------------

                delay = float(
                    event.get(
                        "delay",
                        0
                    )
                )

                delay = max(
                    0,
                    delay / speed
                )

                if not interruptible_sleep(
                    delay
                ):

                    break

                # =================================================
                # TAP
                # =================================================

                if event["type"] == "tap":

                    x = int(
                        event["x"]
                    )

                    y = int(
                        event["y"]
                    )

                    adb_command(
                        [
                            "shell",
                            "input",
                            "tap",
                            str(x),
                            str(y)
                        ],
                        timeout=5
                    )

                # =================================================
                # SWIPE
                # =================================================

                elif event["type"] == "swipe":

                    x1 = int(
                        event["x1"]
                    )

                    y1 = int(
                        event["y1"]
                    )

                    x2 = int(
                        event["x2"]
                    )

                    y2 = int(
                        event["y2"]
                    )

                    duration = int(
                        event.get(
                            "duration",
                            0.3
                        ) * 1000
                    )

                    duration = max(
                        1,
                        duration
                    )

                    # Ajustamos duración por velocidad

                    duration = int(
                        duration / speed
                    )

                    duration = max(
                        1,
                        duration
                    )

                    adb_command(
                        [
                            "shell",
                            "input",
                            "swipe",

                            str(x1),
                            str(y1),

                            str(x2),
                            str(y2),

                            str(duration)
                        ],
                        timeout=10
                    )

            count += 1

            # ----------------------------------------------------
            # PAUSA ENTRE CICLOS
            # ----------------------------------------------------

            if (
                playing
                and not stop_play_event.is_set()
                and (
                    repetitions is None
                    or count < repetitions
                )
            ):

                interruptible_sleep(
                    loop_delay
                )

    except Exception as error:

        root.after(
            0,
            lambda: messagebox.showerror(
                "Error durante reproducción",
                str(error)
            )
        )

    finally:

        playing = False

        stop_play_event.clear()

        root.after(
            0,
            update_play_button
        )

        root.after(
            0,
            lambda: status_var.set(
                f"Reproducción terminada — ciclos: {count}"
            )
        )


# ============================================================
# INICIAR REPRODUCCIÓN
# ============================================================

def start_playback():

    global playing
    global play_thread

    if recording:

        messagebox.showwarning(
            "Automatizador",
            "Detén la grabación antes de reproducir."
        )

        return

    with events_lock:

        if not events:

            messagebox.showinfo(
                "Automatizador",
                "Primero realiza una grabación."
            )

            return

    # --------------------------------------------------------
    # Comprobar teléfono
    # --------------------------------------------------------

    connected, result = check_adb()

    if not connected:

        messagebox.showerror(
            "Android no conectado",
            result
        )

        return

    if playing:

        stop_playback()

        return

    stop_play_event.clear()

    playing = True

    status_var.set(
        "▶ REPRODUCIENDO EN ANDROID"
    )

    play_button.config(
        text="⏹ Detener reproducción"
    )

    play_thread = threading.Thread(
        target=play_events,
        daemon=True
    )

    play_thread.start()


# ============================================================
# DETENER REPRODUCCIÓN
# ============================================================

def stop_playback():

    global playing

    if not playing:

        return

    playing = False

    stop_play_event.set()

    status_var.set(
        "Reproducción detenida"
    )

    update_play_button()


# ============================================================
# EMERGENCIA
# ============================================================

def emergency_stop():

    global recording
    global playing

    if recording:

        stop_recording()

    if playing:

        stop_playback()

    status_var.set(
        "🛑 DETENIDO POR EMERGENCIA"
    )


# ============================================================
# BOTÓN PLAY
# ============================================================

def update_play_button():

    if playing:

        play_button.config(
            text="⏹ Detener reproducción"
        )

    else:

        play_button.config(
            text="▶ Reproducir"
        )


# ============================================================
# BORRAR
# ============================================================

def clear_recording():

    if recording or playing:

        messagebox.showwarning(
            "Automatizador",
            "Detén la grabación/reproducción antes de borrar."
        )

        return

    with events_lock:

        events.clear()

    refresh_event_list()

    status_var.set(
        "Sin grabación"
    )


# ============================================================
# DESCRIPCIÓN
# ============================================================

def event_description(event):

    event_type = event.get(
        "type",
        "?"
    )

    if event_type == "tap":

        return (
            f"👆 TAP → "
            f"({event.get('x')}, "
            f"{event.get('y')}) "
            f"| duración: "
            f"{event.get('duration', 0):.2f}s"
        )

    if event_type == "swipe":

        return (
            f"↕️ SWIPE → "
            f"({event.get('x1')}, "
            f"{event.get('y1')}) → "
            f"({event.get('x2')}, "
            f"{event.get('y2')}) "
            f"| {event.get('duration', 0):.2f}s"
        )

    return event_type


# ============================================================
# LISTA
# ============================================================

def refresh_event_list():

    event_list.delete(
        *event_list.get_children()
    )

    with events_lock:

        current_events = list(
            events
        )

    for index, event in enumerate(
        current_events,
        start=1
    ):

        event_list.insert(
            "",
            "end",
            values=(
                index,
                event_description(event),
                f"{event.get('delay', 0):.3f} s"
            )
        )


# ============================================================
# ELIMINAR EVENTOS
# ============================================================

def delete_selected_event():

    if recording or playing:

        messagebox.showwarning(
            "Automatizador",
            "Detén la grabación/reproducción primero."
        )

        return

    selected = event_list.selection()

    if not selected:

        messagebox.showinfo(
            "Automatizador",
            "Selecciona uno o varios eventos."
        )

        return

    indexes = []

    for item in selected:

        values = event_list.item(
            item,
            "values"
        )

        indexes.append(
            int(values[0]) - 1
        )

    with events_lock:

        for index in sorted(
            indexes,
            reverse=True
        ):

            if 0 <= index < len(events):

                del events[index]

    refresh_event_list()

    status_var.set(
        f"{len(indexes)} evento(s) eliminado(s)"
    )


# ============================================================
# GUARDAR
# ============================================================

def save_recording():

    with events_lock:

        current_events = list(
            events
        )

    if not current_events:

        messagebox.showinfo(
            "Automatizador",
            "No hay ninguna grabación."
        )

        return

    path = filedialog.asksaveasfilename(
        title="Guardar macro Android",
        defaultextension=".json",
        filetypes=[
            ("Macro Android JSON", "*.json")
        ]
    )

    if not path:

        return

    try:

        data = {
            "version": 4,

            "device_width": device_width,
            "device_height": device_height,

            "events": current_events
        }

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )

        status_var.set(
            f"Guardado: {os.path.basename(path)}"
        )

    except Exception as error:

        messagebox.showerror(
            "Error",
            f"No se pudo guardar:\n\n{error}"
        )


# ============================================================
# CARGAR
# ============================================================

def load_recording():

    global events

    if recording or playing:

        messagebox.showwarning(
            "Automatizador",
            "Detén la grabación/reproducción antes de cargar."
        )

        return

    path = filedialog.askopenfilename(
        title="Cargar macro Android",
        filetypes=[
            ("Macro Android JSON", "*.json")
        ]
    )

    if not path:

        return

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            loaded = json.load(file)

        # ----------------------------------------------------
        # V4
        # ----------------------------------------------------

        if isinstance(
            loaded,
            dict
        ):

            loaded_events = loaded.get(
                "events",
                []
            )

        # ----------------------------------------------------
        # Compatibilidad con listas
        # ----------------------------------------------------

        elif isinstance(
            loaded,
            list
        ):

            loaded_events = loaded

        else:

            raise ValueError(
                "Formato de macro inválido."
            )

        if not isinstance(
            loaded_events,
            list
        ):

            raise ValueError(
                "Los eventos no son una lista."
            )

        with events_lock:

            events = loaded_events

        refresh_event_list()

        status_var.set(
            f"Cargado: {os.path.basename(path)}"
        )

    except Exception as error:

        messagebox.showerror(
            "Error",
            f"No se pudo cargar:\n\n{error}"
        )


# ============================================================
# INFORMACIÓN DEL TELÉFONO
# ============================================================

def refresh_device_info():

    connected, result = check_adb()

    if not connected:

        device_var.set(
            "📱 Android: desconectado"
        )

        resolution_var.set(
            "Resolución: —"
        )

        return

    get_device_resolution()
    find_touch_device()

    device_var.set(
        f"📱 Android conectado: {result}"
    )

    resolution_var.set(
        f"Resolución: "
        f"{device_width} × {device_height}"
    )


# ============================================================
# INTERFAZ
# ============================================================

root = tk.Tk()

root.title(
    "AutoClicker Android V4"
)

root.geometry(
    "950x720"
)

root.resizable(
    False,
    False
)


# ============================================================
# ESTILO
# ============================================================

style = ttk.Style()

try:

    style.theme_use(
        "clam"
    )

except tk.TclError:

    pass


# ============================================================
# TÍTULO
# ============================================================

ttk.Label(
    root,
    text="AUTOCLICKER ANDROID V4",
    font=(
        "Segoe UI",
        20,
        "bold"
    )
).pack(
    pady=(18, 3)
)


ttk.Label(
    root,
    text=(
        "Grabador de taps y swipes mediante ADB"
    ),
    font=(
        "Segoe UI",
        10
    )
).pack(
    pady=(0, 8)
)


# ============================================================
# ESTADO DEL DISPOSITIVO
# ============================================================

device_var = tk.StringVar(
    value="📱 Android: comprobando..."
)

resolution_var = tk.StringVar(
    value="Resolución: —"
)


device_frame = ttk.Frame(
    root
)

device_frame.pack(
    pady=5
)


ttk.Label(
    device_frame,
    textvariable=device_var,
    font=(
        "Segoe UI",
        10,
        "bold"
    )
).grid(
    row=0,
    column=0,
    padx=15
)


ttk.Label(
    device_frame,
    textvariable=resolution_var
).grid(
    row=0,
    column=1,
    padx=15
)


ttk.Button(
    device_frame,
    text="🔄 Detectar Android",
    command=refresh_device_info
).grid(
    row=0,
    column=2,
    padx=10
)


# ============================================================
# BOTONES
# ============================================================

controls = ttk.Frame(
    root
)

controls.pack(
    pady=8
)


record_button = ttk.Button(
    controls,
    text="🔴 Grabar",
    command=start_recording,
    width=20
)

record_button.grid(
    row=0,
    column=0,
    padx=5
)


play_button = ttk.Button(
    controls,
    text="▶ Reproducir",
    command=start_playback,
    width=20
)

play_button.grid(
    row=0,
    column=1,
    padx=5
)


ttk.Button(
    controls,
    text="🗑 Borrar todo",
    command=clear_recording,
    width=16
).grid(
    row=0,
    column=2,
    padx=5
)


ttk.Button(
    controls,
    text="❌ Eliminar seleccionado",
    command=delete_selected_event,
    width=24
).grid(
    row=0,
    column=3,
    padx=5
)


# ============================================================
# ARCHIVOS
# ============================================================

file_controls = ttk.Frame(
    root
)

file_controls.pack(
    pady=5
)


ttk.Button(
    file_controls,
    text="💾 Guardar macro",
    command=save_recording,
    width=20
).grid(
    row=0,
    column=0,
    padx=5
)


ttk.Button(
    file_controls,
    text="📂 Cargar macro",
    command=load_recording,
    width=20
).grid(
    row=0,
    column=1,
    padx=5
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

settings = ttk.LabelFrame(
    root,
    text="Configuración de reproducción"
)

settings.pack(
    fill="x",
    padx=25,
    pady=8
)


# ------------------------------------------------------------
# VELOCIDAD
# ------------------------------------------------------------

ttk.Label(
    settings,
    text="Velocidad:"
).grid(
    row=0,
    column=0,
    padx=(15, 5),
    pady=8
)


speed_var = tk.StringVar(
    value="1.0"
)


ttk.Entry(
    settings,
    textvariable=speed_var,
    width=10
).grid(
    row=0,
    column=1
)


ttk.Label(
    settings,
    text="1.0 normal | 2.0 doble | 0.5 mitad"
).grid(
    row=0,
    column=2,
    padx=15
)


# ------------------------------------------------------------
# REPETICIONES
# ------------------------------------------------------------

ttk.Label(
    settings,
    text="Repeticiones:"
).grid(
    row=1,
    column=0,
    padx=(15, 5),
    pady=8
)


repetitions_var = tk.StringVar(
    value="∞"
)


ttk.Entry(
    settings,
    textvariable=repetitions_var,
    width=10
).grid(
    row=1,
    column=1
)


ttk.Label(
    settings,
    text="Número de veces o ∞"
).grid(
    row=1,
    column=2,
    padx=15
)


# ------------------------------------------------------------
# PAUSA
# ------------------------------------------------------------

ttk.Label(
    settings,
    text="Pausa entre ciclos:"
).grid(
    row=2,
    column=0,
    padx=(15, 5),
    pady=8
)


loop_delay_var = tk.StringVar(
    value="0"
)


ttk.Entry(
    settings,
    textvariable=loop_delay_var,
    width=10
).grid(
    row=2,
    column=1
)


ttk.Label(
    settings,
    text="segundos"
).grid(
    row=2,
    column=2,
    padx=15
)


# ============================================================
# EVENTOS
# ============================================================

list_frame = ttk.LabelFrame(
    root,
    text="Eventos registrados"
)

list_frame.pack(
    fill="both",
    expand=True,
    padx=25,
    pady=8
)


columns = (
    "#",
    "Evento",
    "Espera"
)


event_list = ttk.Treeview(
    list_frame,
    columns=columns,
    show="headings",
    height=13,
    selectmode="extended"
)


event_list.heading(
    "#",
    text="#"
)

event_list.heading(
    "Evento",
    text="Evento"
)

event_list.heading(
    "Espera",
    text="Espera"
)


event_list.column(
    "#",
    width=45,
    anchor="center"
)

event_list.column(
    "Evento",
    width=700
)

event_list.column(
    "Espera",
    width=120,
    anchor="center"
)


scrollbar = ttk.Scrollbar(
    list_frame,
    orient="vertical",
    command=event_list.yview
)


event_list.configure(
    yscrollcommand=scrollbar.set
)


event_list.pack(
    side="left",
    fill="both",
    expand=True,
    padx=(5, 0),
    pady=5
)


scrollbar.pack(
    side="right",
    fill="y",
    padx=(0, 5),
    pady=5
)


# ============================================================
# ESTADO
# ============================================================

status_var = tk.StringVar(
    value="Sin grabación"
)


ttk.Label(
    root,
    textvariable=status_var,
    font=(
        "Segoe UI",
        10,
        "bold"
    )
).pack(
    pady=4
)


# ============================================================
# AYUDA
# ============================================================

ttk.Label(
    root,
    text=(
        "F9 = grabar/detener   |   "
        "F10 = reproducir/detener   |   "
        "F12 = emergencia   |   "
        "ESC = detener"
    ),
    font=(
        "Segoe UI",
        9
    )
).pack(
    pady=(0, 12)
)


# ============================================================
# ATAJOS GLOBALES
# ============================================================

def global_key_press(key):

    try:

        if key == keyboard.Key.f9:

            root.after(
                0,
                start_recording
            )

        elif key == keyboard.Key.f10:

            root.after(
                0,
                start_playback
            )

        elif key == keyboard.Key.f12:

            root.after(
                0,
                emergency_stop
            )

        elif key == keyboard.Key.esc:

            root.after(
                0,
                emergency_stop
            )

    except Exception:

        pass


try:

    global_keyboard_listener = keyboard.Listener(
        on_press=global_key_press
    )

    global_keyboard_listener.start()

except Exception as error:

    messagebox.showerror(
        "Error",
        "No se pudo iniciar el listener global.\n\n"
        f"{error}"
    )

    root.destroy()

    raise SystemExit


# ============================================================
# CIERRE
# ============================================================

def close_program():

    global recording
    global playing

    recording = False
    playing = False

    stop_record_event.set()
    stop_play_event.set()

    try:

        if global_keyboard_listener:

            global_keyboard_listener.stop()

    except Exception:

        pass

    root.destroy()


root.protocol(
    "WM_DELETE_WINDOW",
    close_program
)


# ============================================================
# DETECCIÓN INICIAL
# ============================================================

root.after(
    500,
    refresh_device_info
)


# ============================================================
# INICIO
# ============================================================

root.mainloop()
