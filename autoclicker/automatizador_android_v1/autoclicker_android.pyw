import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import time
import json
import os
import re

from pynput import keyboard


# ============================================================
# AUTOCICKER ANDROID
# OPPO A78 + ADB
#
# F9  = iniciar / detener grabación
# F10 = iniciar / detener reproducción
# F12 = emergencia
# ESC = emergencia
#
# IMPORTANTE:
# Este programa se ejecuta en la PC.
# El teléfono debe estar conectado por USB y ADB debe detectarlo.
# ============================================================


# ============================================================
# CONFIGURACIÓN ADB
# ============================================================

ADB = r"C:\Users\Administrador\Desktop\platform-tools\adb.exe"

SCREEN_W = 1080
SCREEN_H = 2400

TOUCH_X_MAX = 4319
TOUCH_Y_MAX = 9599

EVENT_DEVICE = "/dev/input/event3"


# ============================================================
# ESTADO GLOBAL
# ============================================================

recording = False
playing = False

events = []

record_thread = None
play_thread = None

adb_process = None

stop_record_event = threading.Event()
stop_play_event = threading.Event()

events_lock = threading.Lock()

global_keyboard_listener = None


# ============================================================
# ADB
# ============================================================

def adb_cmd(args, timeout=10):
    """
    Ejecuta un comando ADB.
    """

    return subprocess.run(
        [ADB] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout
    )


def check_adb(show_popup=False):
    """
    Comprueba que ADB exista y que haya un dispositivo conectado.
    """

    if not os.path.isfile(ADB):

        if show_popup:
            messagebox.showerror(
                "ADB no encontrado",
                f"No se encontró adb.exe en:\n\n{ADB}"
            )

        return False

    try:

        result = adb_cmd(
            ["devices"],
            timeout=5
        )

        if result.returncode != 0:

            if show_popup:
                messagebox.showerror(
                    "Error ADB",
                    result.stderr.strip()
                )

            return False

        for line in result.stdout.splitlines():

            line = line.strip()

            if (
                line
                and not line.startswith("List of devices")
                and "\tdevice" in line
            ):

                return True

        if show_popup:

            messagebox.showwarning(
                "Teléfono no detectado",
                "ADB funciona, pero no detecta el teléfono.\n\n"
                "Comprueba:\n"
                "• USB conectado\n"
                "• Depuración USB activada\n"
                "• Teléfono desbloqueado\n"
                "• Autorizaste la PC en el teléfono"
            )

        return False

    except Exception as error:

        if show_popup:

            messagebox.showerror(
                "Error ADB",
                str(error)
            )

        return False


# ============================================================
# COORDENADAS
# ============================================================

def touch_to_screen(x, y):

    sx = round(
        (x / TOUCH_X_MAX)
        * SCREEN_W
    )

    sy = round(
        (y / TOUCH_Y_MAX)
        * SCREEN_H
    )

    sx = max(
        0,
        min(
            SCREEN_W - 1,
            sx
        )
    )

    sy = max(
        0,
        min(
            SCREEN_H - 1,
            sy
        )
    )

    return sx, sy


# ============================================================
# PARSER GETEVENT
# ============================================================

EVENT_RE = re.compile(
    r"^\[\s*([0-9]+\.[0-9]+)\]\s+"
    r"(EV_[A-Z]+)\s+"
    r"([A-Z0-9_]+)\s+"
    r"([A-Za-z0-9_+-]+)"
)


def parse_getevent_line(line):

    match = EVENT_RE.match(
        line.strip()
    )

    if not match:
        return None

    timestamp = float(
        match.group(1)
    )

    event_type = match.group(2)

    code = match.group(3)

    value = match.group(4)

    return (
        timestamp,
        event_type,
        code,
        value
    )


def hex_or_int(value):

    try:

        if re.fullmatch(
            r"[0-9a-fA-F]{1,8}",
            value
        ):

            return int(
                value,
                16
            )

        return int(value)

    except Exception:

        return None


# ============================================================
# GRABACIÓN
# ============================================================

def start_recording():

    global recording
    global record_thread
    global adb_process
    global events

    # Si está reproduciendo, F9 no hace nada.
    if playing:
        return

    # Si ya está grabando, F9 DETIENE.
    if recording:

        stop_recording()

        return

    # Comprobar ADB sin bombardear al usuario.
    if not check_adb(
        show_popup=True
    ):

        return

    with events_lock:

        events = []

    stop_record_event.clear()

    recording = True

    status_var.set(
        "🔴 GRABANDO — toca el teléfono"
    )

    record_button.config(
        text="⏹ Detener grabación"
    )

    record_thread = threading.Thread(
        target=record_touch_events,
        daemon=True
    )

    record_thread.start()


def record_touch_events():

    global adb_process

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

            if (
                stop_record_event.is_set()
                or not recording
            ):

                break

            parsed = parse_getevent_line(
                raw_line
            )

            if not parsed:
                continue

            (
                timestamp,
                event_type,
                code,
                value
            ) = parsed

            # ==================================================
            # INICIO / FIN DEL TOUCH
            # ==================================================

            if (
                event_type == "EV_ABS"
                and code == "ABS_MT_TRACKING_ID"
            ):

                tracking = hex_or_int(
                    value
                )

                # Nuevo toque
                if (
                    tracking is not None
                    and tracking != 0xFFFFFFFF
                ):

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

                # Fin del toque
                elif tracking == 0xFFFFFFFF:

                    if current_touch is not None:

                        finish_touch(
                            current_touch,
                            timestamp
                        )

                    current_touch = None

                    last_x = None
                    last_y = None

            # ==================================================
            # X
            # ==================================================

            elif (
                event_type == "EV_ABS"
                and code == "ABS_MT_POSITION_X"
            ):

                value_int = hex_or_int(
                    value
                )

                if (
                    value_int is not None
                    and current_touch is not None
                ):

                    last_x = value_int

                    current_touch["x"] = value_int

                    if last_y is not None:

                        add_point_if_needed(

                            current_touch,

                            timestamp,

                            last_x,

                            last_y

                        )

            # ==================================================
            # Y
            # ==================================================

            elif (
                event_type == "EV_ABS"
                and code == "ABS_MT_POSITION_Y"
            ):

                value_int = hex_or_int(
                    value
                )

                if (
                    value_int is not None
                    and current_touch is not None
                ):

                    last_y = value_int

                    current_touch["y"] = value_int

                    if last_x is not None:

                        add_point_if_needed(

                            current_touch,

                            timestamp,

                            last_x,

                            last_y

                        )

        # Si quedó un toque abierto
        if (
            current_touch is not None
            and not stop_record_event.is_set()
        ):

            finish_touch(

                current_touch,

                current_touch.get(
                    "last_time",
                    current_touch["start_time"]
                )

            )

    except Exception as error:

        if recording:

            root.after(

                0,

                lambda e=error:
                show_error_recording(e)

            )

    finally:

        try:

            if (
                adb_process
                and adb_process.poll() is None
            ):

                adb_process.terminate()

        except Exception:

            pass

        adb_process = None


def show_error_recording(error):

    status_var.set(
        f"Error de grabación: {error}"
    )


def add_point_if_needed(
    touch,
    timestamp,
    x,
    y
):

    points = touch["points"]

    if points:

        px, py, _ = points[-1]

        if (
            px == x
            and py == y
        ):

            return

    points.append(
        (
            x,
            y,
            timestamp
        )
    )


def finish_touch(
    touch,
    end_time
):

    x = touch.get("x")
    y = touch.get("y")

    if x is None or y is None:
        return

    start_time = touch["start_time"]

    duration = max(
        0,
        end_time - start_time
    )

    points = touch.get(
        "points",
        []
    )

    if (
        not points
        or points[-1][0] != x
        or points[-1][1] != y
    ):

        points.append(
            (
                x,
                y,
                end_time
            )
        )

    start_x = points[0][0]
    start_y = points[0][1]

    distance = (

        (
            (x - start_x) ** 2
            +
            (y - start_y) ** 2
        ) ** 0.5

    )

    # Umbral para distinguir tap de swipe.
    SWIPE_THRESHOLD = 120

    if distance >= SWIPE_THRESHOLD:

        sx1, sy1 = touch_to_screen(
            start_x,
            start_y
        )

        sx2, sy2 = touch_to_screen(
            x,
            y
        )

        event = {

            "type": "swipe",

            "x1": sx1,
            "y1": sy1,

            "x2": sx2,
            "y2": sy2,

            "duration": duration

        }

    else:

        sx, sy = touch_to_screen(
            x,
            y
        )

        event = {

            "type": "tap",

            "x": sx,
            "y": sy,

            "duration": duration

        }

    if (
        recording
        and not stop_record_event.is_set()
    ):

        with events_lock:

            events.append(
                event
            )

        root.after(
            0,
            refresh_event_list
        )


def stop_recording():

    global recording

    if not recording:
        return

    recording = False

    stop_record_event.set()

    try:

        if (
            adb_process
            and adb_process.poll() is None
        ):

            adb_process.terminate()

    except Exception:

        pass

    with events_lock:

        count = len(events)

    record_button.config(
        text="🔴 Grabar"
    )

    status_var.set(
        f"Grabación detenida — {count} acción(es)"
    )

    root.after(
        0,
        refresh_event_list
    )


# ============================================================
# REPRODUCCIÓN
# ============================================================

def start_playback():

    global playing
    global play_thread

    # Si está grabando, no reproducir.
    if recording:
        return

    # Si ya está reproduciendo,
    # F10 DETIENE.
    if playing:

        stop_playback()

        return

    with events_lock:

        if not events:

            messagebox.showinfo(

                "Automatizador Android",

                "Primero realiza una grabación."

            )

            return

    # Velocidad
    try:

        speed = float(
            speed_var.get()
        )

        if speed <= 0:
            raise ValueError

    except ValueError:

        messagebox.showerror(

            "Error",

            "La velocidad debe ser mayor que 0."

        )

        return

    # Repeticiones
    try:

        text = (
            repetitions_var
            .get()
            .strip()
            .lower()
        )

        if text in (
            "∞",
            "inf",
            "infinito",
            "infinity"
        ):

            repetitions = None

        else:

            repetitions = int(text)

            if repetitions < 1:
                raise ValueError

    except ValueError:

        messagebox.showerror(

            "Error",

            "Repeticiones debe ser un número entero o ∞."

        )

        return

    # Pausa
    try:

        loop_delay = float(
            loop_delay_var.get()
        )

        if loop_delay < 0:
            raise ValueError

    except ValueError:

        messagebox.showerror(

            "Error",

            "La pausa debe ser 0 o mayor."

        )

        return

    if not check_adb(
        show_popup=True
    ):

        return

    stop_play_event.clear()

    playing = True

    play_button.config(
        text="⏹ Detener reproducción"
    )

    status_var.set(
        "▶ REPRODUCIENDO"
    )

    play_thread = threading.Thread(

        target=play_events,

        args=(
            speed,
            repetitions,
            loop_delay
        ),

        daemon=True

    )

    play_thread.start()


def play_events(
    speed,
    repetitions,
    loop_delay
):

    global playing

    with events_lock:

        playback_events = list(
            events
        )

    count = 0

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

                # =============================================
                # TAP
                # =============================================

                if event["type"] == "tap":

                    ok = adb_tap(

                        event["x"],

                        event["y"]

                    )

                # =============================================
                # SWIPE
                # =============================================

                elif event["type"] == "swipe":

                    duration = float(

                        event.get(
                            "duration",
                            0.2
                        )

                    )

                    duration /= speed

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
                        "ADB no pudo ejecutar la acción."
                    )

            count += 1

            # =============================================
            # PAUSA ENTRE CICLOS
            # =============================================

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

            lambda e=error:
            status_var.set(
                f"Error: {e}"
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

            lambda c=count:
            status_var.set(
                f"Reproducción terminada — ciclos: {c}"
            )

        )


def adb_tap(
    x,
    y
):

    try:

        result = adb_cmd(

            [
                "shell",
                "input",
                "tap",
                str(int(x)),
                str(int(y))
            ],

            timeout=5

        )

        return result.returncode == 0

    except Exception:

        return False


def adb_swipe(
    x1,
    y1,
    x2,
    y2,
    duration
):

    try:

        duration_ms = max(

            1,

            round(
                duration * 1000
            )

        )

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

            timeout=max(
                5,
                int(duration_ms / 1000) + 5
            )

        )

        return result.returncode == 0

    except Exception:

        return False


def interruptible_sleep(
    seconds
):

    end = (
        time.perf_counter()
        +
        max(0, seconds)
    )

    while (

        playing

        and not stop_play_event.is_set()

    ):

        remaining = (
            end
            -
            time.perf_counter()
        )

        if remaining <= 0:
            return True

        time.sleep(
            min(
                0.02,
                remaining
            )
        )

    return False


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


def emergency_stop():

    if recording:
        stop_recording()

    if playing:
        stop_playback()

    status_var.set(
        "🛑 DETENIDO"
    )


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
# LISTA DE EVENTOS
# ============================================================

def event_description(event):

    typ = event.get(
        "type"
    )

    if typ == "tap":

        return (

            f"👆 TAP → "

            f"({event.get('x')}, "
            f"{event.get('y')})"

        )

    if typ == "swipe":

        return (

            f"↗ SWIPE → "

            f"({event.get('x1')}, "
            f"{event.get('y1')}) → "

            f"({event.get('x2')}, "
            f"{event.get('y2')})"

        )

    return str(event)


def refresh_event_list():

    event_list.delete(
        *event_list.get_children()
    )

    with events_lock:

        current = list(events)

    for i, event in enumerate(
        current,
        start=1
    ):

        event_list.insert(

            "",

            "end",

            values=(

                i,

                event_description(
                    event
                ),

                f"{event.get('duration', 0):.3f} s"

            )

        )


# ============================================================
# ELIMINAR
# ============================================================

def delete_selected_event():

    if recording or playing:

        return

    selected = event_list.selection()

    if not selected:

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

            if (
                0 <= index
                < len(events)
            ):

                del events[index]

    refresh_event_list()

    status_var.set(
        f"{len(indexes)} acción(es) eliminada(s)"
    )


def clear_recording():

    if recording or playing:
        return

    with events_lock:

        events.clear()

    refresh_event_list()

    status_var.set(
        "Sin grabación"
    )


# ============================================================
# GUARDAR
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

        filetypes=[
            (
                "Macro JSON",
                "*.json"
            )
        ]

    )

    if not path:
        return

    data = {

        "device": "OPPO A78",

        "screen": [
            SCREEN_W,
            SCREEN_H
        ],

        "touch_max": [
            TOUCH_X_MAX,
            TOUCH_Y_MAX
        ],

        "events": current

    }

    try:

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

            f"Guardado: "
            f"{os.path.basename(path)}"

        )

    except Exception as error:

        messagebox.showerror(

            "Error",

            str(error)

        )


# ============================================================
# CARGAR
# ============================================================

def load_recording():

    global events

    if recording or playing:
        return

    path = filedialog.askopenfilename(

        title="Cargar macro Android",

        filetypes=[
            (
                "Macro JSON",
                "*.json"
            )
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

        if isinstance(
            loaded,
            list
        ):

            new_events = loaded

        elif (

            isinstance(
                loaded,
                dict
            )

            and isinstance(
                loaded.get("events"),
                list
            )

        ):

            new_events = loaded["events"]

        else:

            raise ValueError(
                "Formato de macro inválido."
            )

        with events_lock:

            events = new_events

        refresh_event_list()

        status_var.set(

            f"Cargado: "
            f"{os.path.basename(path)}"

        )

    except Exception as error:

        messagebox.showerror(

            "Error",

            str(error)

        )


# ============================================================
# ATAJOS GLOBALES
# ============================================================

def global_key_press(key):

    """
    Estos atajos funcionan aunque otra aplicación
    tenga el foco.
    """

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


# ============================================================
# INTERFAZ
# ============================================================

root = tk.Tk()

root.title(
    "Autoclicker Android — OPPO A78"
)

root.geometry(
    "980x720"
)

root.resizable(
    False,
    False
)


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

    text="AUTOCLICKER ANDROID",

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
        "OPPO A78 • ADB • "
        "Grabación de taps y swipes"
    ),

    font=(
        "Segoe UI",
        10
    )

).pack(
    pady=(0, 15)
)


# ============================================================
# BOTONES
# ============================================================

controls = ttk.Frame(
    root
)

controls.pack(
    pady=5
)


record_button = ttk.Button(

    controls,

    text="🔴 Grabar",

    command=start_recording,

    width=22

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

    width=22

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
    pady=8
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

    pady=10

)


# Velocidad

ttk.Label(

    settings,

    text="Velocidad:"

).grid(

    row=0,

    column=0,

    padx=(15, 5),

    pady=10

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

    text=(
        "1.0 normal | "
        "2.0 doble | "
        "0.5 mitad"
    )

).grid(

    row=0,

    column=2,

    padx=15

)


# Repeticiones

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


# Pausa

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
# LISTA DE EVENTOS
# ============================================================

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


columns = (
    "#",
    "Evento",
    "Duración"
)


event_list = ttk.Treeview(

    list_frame,

    columns=columns,

    show="headings",

    height=16,

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
    "Duración",
    text="Duración"
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

    "Duración",

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

    value="Listo — conecta tu OPPO A78"

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
    pady=5
)


# ============================================================
# AYUDA
# ============================================================

ttk.Label(

    root,

    text=(

        "F9 = Grabar / detener   |   "
        "F10 = Reproducir / detener   |   "
        "F12 / ESC = Emergencia"

    ),

    font=(
        "Segoe UI",
        9
    )

).pack(

    pady=(0, 12)

)


# ============================================================
# LISTENER GLOBAL
# ============================================================

try:

    global_keyboard_listener = keyboard.Listener(

        on_press=global_key_press

    )

    global_keyboard_listener.start()

except Exception as error:

    status_var.set(
        f"No se pudieron activar los atajos: {error}"
    )


# ============================================================
# CIERRE
# ============================================================

def close_program():

    global recording
    global playing
    global global_keyboard_listener

    recording = False
    playing = False

    stop_record_event.set()
    stop_play_event.set()

    try:

        if (
            adb_process
            and adb_process.poll() is None
        ):

            adb_process.terminate()

    except Exception:

        pass

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
# INICIO
# ============================================================

root.mainloop()