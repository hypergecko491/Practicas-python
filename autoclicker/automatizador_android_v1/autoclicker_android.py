from pathlib import Path

code = r'''import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import time
import json
import os
import re

# ============================================================
# AUTÓMATIZADOR ANDROID V4.1 - OPPO A78 / ADB
#
# Requisitos:
#   - Python 3.x
#   - ADB Platform-Tools
#   - Depuración USB activada
#
# ADB detectado en la PC del usuario:
#   C:\Users\Administrador\Desktop\platform-tools\adb.exe
#
# Funciones:
#   - Graba taps, long press y swipes mediante getevent
#   - Convierte coordenadas del touchpanel a pantalla
#   - Reproduce mediante "adb shell input"
#   - Velocidad, repeticiones y pausa entre ciclos
#   - Guardar/cargar JSON
#
# Atajos:
#   F9  = grabar/detener
#   F10 = reproducir/detener
#   F12 = emergencia
#   ESC = emergencia
# ============================================================

ADB = r"C:\Users\Administrador\Desktop\platform-tools\adb.exe"

SCREEN_W = 1080
SCREEN_H = 2400

TOUCH_X_MAX = 4319
TOUCH_Y_MAX = 9599

EVENT_DEVICE = "/dev/input/event3"

recording = False
playing = False
events = []

record_thread = None
play_thread = None
adb_process = None

stop_record_event = threading.Event()
stop_play_event = threading.Event()

events_lock = threading.Lock()


# ============================================================
# ADB
# ============================================================

def adb_cmd(args, timeout=10):
    """Ejecuta ADB y devuelve stdout."""
    return subprocess.run(
        [ADB] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout
    )


def check_adb():
    if not os.path.isfile(ADB):
        messagebox.showerror(
            "ADB no encontrado",
            "No se encontró adb.exe en:\n\n"
            f"{ADB}\n\n"
            "Revisa que Platform-Tools esté en esa carpeta."
        )
        return False

    try:
        result = adb_cmd(["devices"], timeout=5)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "ADB devolvió un error.")

        devices = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and not line.startswith("List of devices") and "\tdevice" in line:
                devices.append(line)

        if not devices:
            messagebox.showwarning(
                "Teléfono no detectado",
                "ADB funciona, pero no detectó un teléfono.\n\n"
                "Comprueba que el OPPO esté conectado, desbloqueado y "
                "que la depuración USB esté activa."
            )
            return False

        return True

    except Exception as error:
        messagebox.showerror("Error de ADB", str(error))
        return False


# ============================================================
# COORDENADAS
# ============================================================

def touch_to_screen(x, y):
    sx = round((x / TOUCH_X_MAX) * SCREEN_W)
    sy = round((y / TOUCH_Y_MAX) * SCREEN_H)

    sx = max(0, min(SCREEN_W - 1, sx))
    sy = max(0, min(SCREEN_H - 1, sy))

    return sx, sy


# ============================================================
# PARSER DE GETEVENT
# ============================================================

EVENT_RE = re.compile(
    r"^\[\s*([0-9]+\.[0-9]+)\]\s+"
    r"(EV_[A-Z]+)\s+"
    r"([A-Z0-9_]+)\s+"
    r"([A-Za-z0-9_+-]+)"
)


def parse_getevent_line(line):
    m = EVENT_RE.match(line.strip())
    if not m:
        return None

    timestamp = float(m.group(1))
    event_type = m.group(2)
    code = m.group(3)
    value = m.group(4)

    return timestamp, event_type, code, value


def hex_or_int(value):
    try:
        if re.fullmatch(r"[0-9a-fA-F]{1,8}", value):
            return int(value, 16)
        return int(value)
    except Exception:
        return None


# ============================================================
# GRABACIÓN
# ============================================================

def start_recording():
    global recording, record_thread, adb_process, events

    if playing:
        messagebox.showwarning(
            "Automatizador Android",
            "Detén la reproducción antes de grabar."
        )
        return

    if recording:
        stop_recording()
        return

    if not check_adb():
        return

    with events_lock:
        events = []

    stop_record_event.clear()
    recording = True

    status_var.set(
        "🔴 GRABANDO — toca y desliza en el teléfono"
    )
    record_button.config(text="⏹ Detener grabación")

    record_thread = threading.Thread(
        target=record_touch_events,
        daemon=True
    )
    record_thread.start()


def record_touch_events():
    global adb_process

    # getevent -lt permite obtener timestamps.
    command = [
        ADB,
        "shell",
        "getevent",
        "-lt",
        EVENT_DEVICE
    ]

    current_touch = None
    last_x = None
    last_y = None
    last_position_time = None

    try:
        adb_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1
        )

        for raw_line in adb_process.stdout:
            if stop_record_event.is_set() or not recording:
                break

            parsed = parse_getevent_line(raw_line)
            if not parsed:
                continue

            timestamp, event_type, code, value = parsed

            # Inicio del toque
            if event_type == "EV_ABS" and code == "ABS_MT_TRACKING_ID":
                tracking = hex_or_int(value)

                if tracking is not None and tracking != 0xFFFFFFFF:
                    if current_touch is None:
                        current_touch = {
                            "start_time": timestamp,
                            "last_time": timestamp,
                            "x": None,
                            "y": None,
                            "points": []
                        }
                        last_x = None
                        last_y = None
                        last_position_time = timestamp

                elif tracking == 0xFFFFFFFF:
                    if current_touch is not None:
                        finish_touch(current_touch, timestamp)

                    current_touch = None
                    last_x = None
                    last_y = None
                    last_position_time = None

            elif event_type == "EV_ABS" and code == "ABS_MT_POSITION_X":
                value_int = hex_or_int(value)

                if value_int is not None and current_touch is not None:
                    last_x = value_int
                    current_touch["x"] = value_int

                    if last_y is not None:
                        add_point_if_needed(
                            current_touch,
                            timestamp,
                            last_x,
                            last_y
                        )

            elif event_type == "EV_ABS" and code == "ABS_MT_POSITION_Y":
                value_int = hex_or_int(value)

                if value_int is not None and current_touch is not None:
                    last_y = value_int
                    current_touch["y"] = value_int

                    if last_x is not None:
                        add_point_if_needed(
                            current_touch,
                            timestamp,
                            last_x,
                            last_y
                        )

            elif event_type == "EV_SYN" and code == "SYN_REPORT":
                if current_touch is not None:
                    current_touch["last_time"] = timestamp

        # Por si el proceso terminó con un toque abierto.
        if current_touch is not None and not stop_record_event.is_set():
            finish_touch(
                current_touch,
                current_touch.get("last_time", current_touch["start_time"])
            )

    except Exception as error:
        if recording and not stop_record_event.is_set():
            root.after(
                0,
                lambda e=error: messagebox.showerror(
                    "Error de grabación",
                    f"No se pudo leer el touchscreen:\n\n{e}"
                )
            )

    finally:
        try:
            if adb_process and adb_process.poll() is None:
                adb_process.terminate()
        except Exception:
            pass

        adb_process = None


def add_point_if_needed(touch, timestamp, x, y):
    # Evita guardar duplicados exactos.
    points = touch["points"]

    if points:
        px, py, _ = points[-1]
        if px == x and py == y:
            return

    points.append((x, y, timestamp))


def finish_touch(touch, end_time):
    x = touch.get("x")
    y = touch.get("y")

    if x is None or y is None:
        return

    start_time = touch["start_time"]
    duration = max(0.0, end_time - start_time)

    points = touch.get("points", [])

    # Agregar último punto si existe.
    if not points or points[-1][0] != x or points[-1][1] != y:
        points.append((x, y, end_time))

    sx, sy = touch_to_screen(x, y)

    # Determinar si realmente hubo desplazamiento.
    start_x = x
    start_y = y

    if points:
        start_x = points[0][0]
        start_y = points[0][1]

    distance = ((x - start_x) ** 2 + (y - start_y) ** 2) ** 0.5

    # 120 unidades del touchpanel ~= 30 px de pantalla.
    SWIPE_THRESHOLD = 120

    if distance >= SWIPE_THRESHOLD:
        sx1, sy1 = touch_to_screen(start_x, start_y)
        sx2, sy2 = touch_to_screen(x, y)

        event = {
            "type": "swipe",
            "x1": sx1,
            "y1": sy1,
            "x2": sx2,
            "y2": sy2,
            "duration": duration
        }

    else:
        event = {
            "type": "tap",
            "x": sx,
            "y": sy,
            "duration": duration
        }

    # Solo grabar mientras la grabación siga activa.
    if recording and not stop_record_event.is_set():
        with events_lock:
            events.append(event)

        root.after(0, refresh_event_list)


def stop_recording():
    global recording

    if not recording:
        return

    recording = False
    stop_record_event.set()

    try:
        if adb_process and adb_process.poll() is None:
            adb_process.terminate()
    except Exception:
        pass

    with events_lock:
        count = len(events)

    record_button.config(text="🔴 Grabar")
    status_var.set(
        f"Grabación detenida — {count} acción(es)"
    )

    refresh_event_list()


# ============================================================
# REPRODUCCIÓN
# ============================================================

def start_playback():
    global playing, play_thread

    if recording:
        messagebox.showwarning(
            "Automatizador Android",
            "Detén la grabación antes de reproducir."
        )
        return

    with events_lock:
        if not events:
            messagebox.showinfo(
                "Automatizador Android",
                "Primero realiza una grabación."
            )
            return

    if playing:
        stop_playback()
        return

    try:
        speed = float(speed_var.get())
        if speed <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror(
            "Error",
            "La velocidad debe ser mayor que 0."
        )
        return

    try:
        rep_text = repetitions_var.get().strip().lower()

        if rep_text in ("∞", "inf", "infinito", "infinity"):
            repetitions = None
        else:
            repetitions = int(rep_text)
            if repetitions < 1:
                raise ValueError
    except ValueError:
        messagebox.showerror(
            "Error",
            "Repeticiones debe ser un entero o ∞."
        )
        return

    try:
        loop_delay = float(loop_delay_var.get())
        if loop_delay < 0:
            raise ValueError
    except ValueError:
        messagebox.showerror(
            "Error",
            "La pausa entre ciclos debe ser 0 o mayor."
        )
        return

    if not check_adb():
        return

    stop_play_event.clear()
    playing = True

    play_button.config(text="⏹ Detener reproducción")
    status_var.set("▶ REPRODUCIENDO")

    play_thread = threading.Thread(
        target=play_events,
        args=(speed, repetitions, loop_delay),
        daemon=True
    )
    play_thread.start()


def interruptible_sleep(seconds):
    end = time.perf_counter() + max(0, seconds)

    while playing and not stop_play_event.is_set():
        remaining = end - time.perf_counter()

        if remaining <= 0:
            return True

        time.sleep(min(0.02, remaining))

    return False


def play_events(speed, repetitions, loop_delay):
    global playing

    with events_lock:
        playback_events = list(events)

    count = 0

    try:
        while (
            playing
            and not stop_play_event.is_set()
            and (repetitions is None or count < repetitions)
        ):
            for event in playback_events:
                if not playing or stop_play_event.is_set():
                    break

                duration = float(event.get("duration", 0.1))
                duration = max(0.01, duration / speed)

                if event["type"] == "tap":
                    ok = adb_tap(
                        event["x"],
                        event["y"],
                        duration
                    )

                elif event["type"] == "swipe":
                    ok = adb_swipe(
                        event["x1"],
                        event["y1"],
                        event["x2"],
                        event["y2"],
                        duration
                    )

                else:
                    ok = True

                if not ok:
                    raise RuntimeError(
                        "ADB no pudo ejecutar una acción."
                    )

            count += 1

            if (
                playing
                and not stop_play_event.is_set()
                and (repetitions is None or count < repetitions)
            ):
                if not interruptible_sleep(loop_delay):
                    break

    except Exception as error:
        root.after(
            0,
            lambda e=error: messagebox.showerror(
                "Error durante la reproducción",
                f"Ocurrió un error:\n\n{e}"
            )
        )

    finally:
        playing = False
        stop_play_event.clear()

        root.after(0, update_play_button)
        root.after(
            0,
            lambda c=count: status_var.set(
                f"Reproducción terminada — ciclos: {c}"
            )
        )


def adb_tap(x, y, duration):
    # Android input tap no acepta una duración real.
    # Para taps normales usamos input tap.
    result = adb_cmd(
        ["shell", "input", "tap", str(int(x)), str(int(y))],
        timeout=5
    )
    return result.returncode == 0


def adb_swipe(x1, y1, x2, y2, duration):
    duration_ms = max(1, round(duration * 1000))

    result = adb_cmd(
        [
            "shell",
            "input",
            "swipe",
            str(int(x1)),
            str(int(y1)),
            str(int(x2)),
            str(int(y2)),
            str(duration_ms)
        ],
        timeout=max(5, int(duration_ms / 1000) + 5)
    )

    return result.returncode == 0


def stop_playback():
    global playing

    if not playing:
        return

    playing = False
    stop_play_event.set()

    status_var.set("Reproducción detenida")
    update_play_button()


def emergency_stop():
    global recording, playing

    if recording:
        stop_recording()

    if playing:
        stop_playback()

    status_var.set("🛑 DETENIDO POR EMERGENCIA")


def update_play_button():
    play_button.config(
        text="⏹ Detener reproducción" if playing else "▶ Reproducir"
    )


# ============================================================
# EVENTOS / LISTA
# ============================================================

def event_description(event):
    typ = event.get("type")

    if typ == "tap":
        return (
            f"👆 TAP → ({event.get('x')}, {event.get('y')}) "
            f"[{event.get('duration', 0):.3f}s]"
        )

    if typ == "swipe":
        return (
            f"↗ SWIPE → "
            f"({event.get('x1')}, {event.get('y1')}) → "
            f"({event.get('x2')}, {event.get('y2')}) "
            f"[{event.get('duration', 0):.3f}s]"
        )

    return str(event)


def refresh_event_list():
    event_list.delete(*event_list.get_children())

    with events_lock:
        current = list(events)

    for i, event in enumerate(current, start=1):
        event_list.insert(
            "",
            "end",
            values=(
                i,
                event_description(event),
                f"{event.get('duration', 0):.3f} s"
            )
        )


def delete_selected_event():
    if recording or playing:
        messagebox.showwarning(
            "Automatizador Android",
            "Detén la grabación/reproducción primero."
        )
        return

    selected = event_list.selection()

    if not selected:
        messagebox.showinfo(
            "Automatizador Android",
            "Selecciona una o varias acciones."
        )
        return

    indexes = []

    for item in selected:
        values = event_list.item(item, "values")
        indexes.append(int(values[0]) - 1)

    with events_lock:
        for index in sorted(indexes, reverse=True):
            if 0 <= index < len(events):
                del events[index]

    refresh_event_list()
    status_var.set(f"{len(indexes)} acción(es) eliminada(s)")


def clear_recording():
    if recording or playing:
        messagebox.showwarning(
            "Automatizador Android",
            "Detén la grabación/reproducción antes de borrar."
        )
        return

    with events_lock:
        events.clear()

    refresh_event_list()
    status_var.set("Sin grabación")


# ============================================================
# GUARDAR / CARGAR
# ============================================================

def save_recording():
    with events_lock:
        current = list(events)

    if not current:
        messagebox.showinfo(
            "Automatizador Android",
            "No hay ninguna grabación."
        )
        return

    path = filedialog.asksaveasfilename(
        title="Guardar macro Android",
        defaultextension=".json",
        filetypes=[("Macro JSON", "*.json")]
    )

    if not path:
        return

    data = {
        "device": "OPPO A78",
        "screen": [SCREEN_W, SCREEN_H],
        "touch_max": [TOUCH_X_MAX, TOUCH_Y_MAX],
        "events": current
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        status_var.set(
            f"Guardado: {os.path.basename(path)}"
        )

    except Exception as error:
        messagebox.showerror(
            "Error",
            f"No se pudo guardar:\n\n{error}"
        )


def load_recording():
    global events

    if recording or playing:
        messagebox.showwarning(
            "Automatizador Android",
            "Detén la grabación/reproducción antes de cargar."
        )
        return

    path = filedialog.askopenfilename(
        title="Cargar macro Android",
        filetypes=[("Macro JSON", "*.json")]
    )

    if not path:
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        # Compatibilidad con una lista JSON sencilla.
        if isinstance(loaded, list):
            new_events = loaded
        elif isinstance(loaded, dict) and isinstance(loaded.get("events"), list):
            new_events = loaded["events"]
        else:
            raise ValueError(
                "El archivo no contiene eventos válidos."
            )

        # Validación básica.
        for event in new_events:
            if event.get("type") not in ("tap", "swipe"):
                raise ValueError(
                    "El archivo contiene un tipo de evento no compatible."
                )

        with events_lock:
            events = new_events

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
# ATAJOS DE TECLADO
# ============================================================

def on_key(event):
    if event.keysym == "F9":
        start_recording()
    elif event.keysym == "F10":
        start_playback()
    elif event.keysym in ("F12", "Escape"):
        emergency_stop()


# ============================================================
# INTERFAZ
# ============================================================

root = tk.Tk()
root.title("Automatizador Android V4.1 — OPPO A78")
root.geometry("980x720")
root.resizable(False, False)

root.bind_all("<F9>", on_key)
root.bind_all("<F10>", on_key)
root.bind_all("<F12>", on_key)
root.bind_all("<Escape>", on_key)

style = ttk.Style()

try:
    style.theme_use("clam")
except tk.TclError:
    pass

ttk.Label(
    root,
    text="AUTOMATIZADOR ANDROID V4.1",
    font=("Segoe UI", 20, "bold")
).pack(pady=(18, 3))

ttk.Label(
    root,
    text="Grabación de taps y swipes mediante ADB — OPPO A78",
    font=("Segoe UI", 10)
).pack(pady=(0, 15))


# Botones principales
controls = ttk.Frame(root)
controls.pack(pady=5)

record_button = ttk.Button(
    controls,
    text="🔴 Grabar",
    command=start_recording,
    width=22
)
record_button.grid(row=0, column=0, padx=5)

play_button = ttk.Button(
    controls,
    text="▶ Reproducir",
    command=start_playback,
    width=22
)
play_button.grid(row=0, column=1, padx=5)

ttk.Button(
    controls,
    text="🗑 Borrar todo",
    command=clear_recording,
    width=16
).grid(row=0, column=2, padx=5)

ttk.Button(
    controls,
    text="❌ Eliminar seleccionado",
    command=delete_selected_event,
    width=24
).grid(row=0, column=3, padx=5)


# Archivos
file_controls = ttk.Frame(root)
file_controls.pack(pady=8)

ttk.Button(
    file_controls,
    text="💾 Guardar macro",
    command=save_recording,
    width=20
).grid(row=0, column=0, padx=5)

ttk.Button(
    file_controls,
    text="📂 Cargar macro",
    command=load_recording,
    width=20
).grid(row=0, column=1, padx=5)


# Configuración
settings = ttk.LabelFrame(
    root,
    text="Configuración de reproducción"
)
settings.pack(fill="x", padx=25, pady=10)

ttk.Label(
    settings,
    text="Velocidad:"
).grid(row=0, column=0, padx=(15, 5), pady=10)

speed_var = tk.StringVar(value="1.0")

ttk.Entry(
    settings,
    textvariable=speed_var,
    width=10
).grid(row=0, column=1)

ttk.Label(
    settings,
    text="1.0 normal | 2.0 doble | 0.5 mitad"
).grid(row=0, column=2, padx=15)


ttk.Label(
    settings,
    text="Repeticiones:"
).grid(row=1, column=0, padx=(15, 5), pady=8)

repetitions_var = tk.StringVar(value="∞")

ttk.Entry(
    settings,
    textvariable=repetitions_var,
    width=10
).grid(row=1, column=1)

ttk.Label(
    settings,
    text="Número de veces o ∞"
).grid(row=1, column=2, padx=15)


ttk.Label(
    settings,
    text="Pausa entre ciclos:"
).grid(row=2, column=0, padx=(15, 5), pady=8)

loop_delay_var = tk.StringVar(value="0")

ttk.Entry(
    settings,
    textvariable=loop_delay_var,
    width=10
).grid(row=2, column=1)

ttk.Label(
    settings,
    text="segundos"
).grid(row=2, column=2, padx=15)


# Lista
list_frame = ttk.LabelFrame(
    root,
    text="Acciones registradas"
)
list_frame.pack(
    fill="both",
    expand=True,
    padx=25,
    pady=8
)

columns = ("#", "Evento", "Duración")

event_list = ttk.Treeview(
    list_frame,
    columns=columns,
    show="headings",
    height=16,
    selectmode="extended"
)

event_list.heading("#", text="#")
event_list.heading("Evento", text="Evento")
event_list.heading("Duración", text="Duración")

event_list.column("#", width=45, anchor="center")
event_list.column("Evento", width=700)
event_list.column("Duración", width=120, anchor="center")

scrollbar = ttk.Scrollbar(
    list_frame,
    orient="vertical",
    command=event_list.yview
)

event_list.configure(yscrollcommand=scrollbar.set)

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


# Estado
status_var = tk.StringVar(value="Sin grabación")

ttk.Label(
    root,
    textvariable=status_var,
    font=("Segoe UI", 10, "bold")
).pack(pady=5)

ttk.Label(
    root,
    text=(
        "F9 = grabar/detener   |   "
        "F10 = reproducir/detener   |   "
        "F12 = emergencia   |   "
        "ESC = detener"
    ),
    font=("Segoe UI", 9)
).pack(pady=(0, 12))


# Cierre
def close_program():
    global recording, playing

    recording = False
    playing = False

    stop_record_event.set()
    stop_play_event.set()

    try:
        if adb_process and adb_process.poll() is None:
            adb_process.terminate()
    except Exception:
        pass

    root.destroy()


root.protocol("WM_DELETE_WINDOW", close_program)

root.mainloop()
'''

path = Path("/mnt/data/automatizador_android_oppo_a78_v4_1.py")
path.write_text(code, encoding="utf-8")

# Also create a small launcher .bat for convenience.
bat = r'''@echo off
title Automatizador Android V4.1 - OPPO A78
py "%~dp0automatizador_android_oppo_a78_v4_1.py"
if errorlevel 1 pause
'''
bat_path = Path("/mnt/data/INICIAR_AUTOMATIZADOR_ANDROID.bat")
bat_path.write_text(bat, encoding="utf-8")

print(path)
print(bat_path)
