import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import json
import os

import pyautogui
from pynput import mouse, keyboard


# ============================================================
# AUTOMATIZADOR DE MOUSE V3
#@hypergecko491
# F9  = iniciar/detener grabación
# F10 = iniciar/detener reproducción
# F12 = emergencia / detener todo
# ESC = detener todo
#
# Graba:
#   - Movimiento del mouse
#   - Clic izquierdo
#   - Clic derecho
#   - Clic central
#   - Rueda
#   - Teclado
#
# Dependencias:
#   python -m pip install pyautogui pynput
# ============================================================


# ============================================================
# CONFIGURACIÓN
# ============================================================

pyautogui.PAUSE = 0.01
pyautogui.FAILSAFE = True


# ============================================================
# ESTADO GLOBAL
# ============================================================

recording = False
playing = False

events = []

mouse_listener = None
record_keyboard_listener = None
global_keyboard_listener = None

last_event_time = None

events_lock = threading.Lock()

stop_play_event = threading.Event()


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def get_delay():
    """
    Devuelve el tiempo transcurrido desde el evento anterior.
    """

    global last_event_time

    now = time.perf_counter()

    if last_event_time is None:
        delay = 0
    else:
        delay = now - last_event_time

    last_event_time = now

    return delay


def add_event(event):
    """
    Agrega un evento de forma segura.
    """

    with events_lock:
        events.append(event)


def interruptible_sleep(seconds):
    """
    Espera pero permite detener la reproducción
    prácticamente inmediatamente.
    """

    if seconds <= 0:
        return True

    end_time = time.perf_counter() + seconds

    while playing and not stop_play_event.is_set():

        remaining = end_time - time.perf_counter()

        if remaining <= 0:
            return True

        time.sleep(
            min(0.01, remaining)
        )

    return False


# ============================================================
# CONVERSIÓN DE TECLAS
# ============================================================

def key_to_string(key):

    try:

        # Letras, números, símbolos, etc.
        if isinstance(key, keyboard.KeyCode):

            if key.char is not None:

                return {
                    "kind": "char",
                    "value": key.char
                }

        # Teclas especiales
        if isinstance(key, keyboard.Key):

            return {
                "kind": "special",
                "value": key.name
            }

    except Exception:
        pass

    return {
        "kind": "unknown",
        "value": str(key)
    }


def string_to_key(data):

    try:

        kind = data.get("kind")
        value = data.get("value")

        if kind == "char":

            return value

        if kind == "special":

            if hasattr(
                keyboard.Key,
                value
            ):

                return getattr(
                    keyboard.Key,
                    value
                )

    except Exception:
        pass

    return None


# ============================================================
# CONVERSIÓN DE BOTONES
# ============================================================

def button_to_string(button):

    try:
        return button.name

    except Exception:
        return str(button)


# ============================================================
# GRABACIÓN DEL MOUSE
# ============================================================

def on_mouse_move(x, y):

    if not recording:
        return

    delay = get_delay()

    add_event({

        "type": "move",

        "x": x,
        "y": y,

        "delay": delay
    })


def on_mouse_click(
    x,
    y,
    button,
    pressed
):

    if not recording:
        return

    delay = get_delay()

    add_event({

        "type": "click",

        "x": x,
        "y": y,

        "button": button_to_string(button),

        "pressed": pressed,

        "delay": delay
    })


def on_mouse_scroll(
    x,
    y,
    dx,
    dy
):

    if not recording:
        return

    delay = get_delay()

    add_event({

        "type": "scroll",

        "x": x,
        "y": y,

        "dx": dx,
        "dy": dy,

        "delay": delay
    })


# ============================================================
# GRABACIÓN DEL TECLADO
# ============================================================

def on_record_key_press(key):

    if not recording:
        return

    # --------------------------------------------------------
    # IMPORTANTE
    #
    # F9, F10 y F12 son los atajos del programa.
    # No se guardan en la macro.
    # --------------------------------------------------------

    if key in (
        keyboard.Key.f9,
        keyboard.Key.f10,
        keyboard.Key.f12
    ):

        return

    delay = get_delay()

    add_event({

        "type": "key_down",

        "key": key_to_string(key),

        "delay": delay
    })


def on_record_key_release(key):

    if not recording:
        return

    # No grabar los atajos del programa.

    if key in (
        keyboard.Key.f9,
        keyboard.Key.f10,
        keyboard.Key.f12
    ):

        return

    delay = get_delay()

    add_event({

        "type": "key_up",

        "key": key_to_string(key),

        "delay": delay
    })


# ============================================================
# ATAJOS GLOBALES
# ============================================================

def global_key_press(key):

    """
    Escucha F9/F10/F12 incluso cuando Chrome,
    Edge, un juego u otra aplicación tienen el foco.
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

    except Exception:
        pass


# ============================================================
# INICIAR GRABACIÓN
# ============================================================

def start_recording():

    global recording
    global events
    global last_event_time

    global mouse_listener
    global record_keyboard_listener

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
    # Limpiar eventos anteriores
    # --------------------------------------------------------

    with events_lock:
        events = []

    last_event_time = time.perf_counter()

    recording = True

    status_var.set(
        "🔴 GRABANDO — mouse + teclado"
    )

    record_button.config(
        text="⏹ Detener grabación"
    )

    # --------------------------------------------------------
    # Listener de mouse
    # --------------------------------------------------------

    mouse_listener = mouse.Listener(

        on_move=on_mouse_move,

        on_click=on_mouse_click,

        on_scroll=on_mouse_scroll
    )

    # --------------------------------------------------------
    # Listener de teclado
    # --------------------------------------------------------

    record_keyboard_listener = keyboard.Listener(

        on_press=on_record_key_press,

        on_release=on_record_key_release
    )

    mouse_listener.start()

    record_keyboard_listener.start()


# ============================================================
# DETENER GRABACIÓN
# ============================================================

def stop_recording():

    global recording

    global mouse_listener
    global record_keyboard_listener

    if not recording:
        return

    recording = False

    # --------------------------------------------------------
    # Detener mouse listener
    # --------------------------------------------------------

    try:

        if mouse_listener:

            mouse_listener.stop()

    except Exception:
        pass

    # --------------------------------------------------------
    # Detener teclado listener
    # --------------------------------------------------------

    try:

        if record_keyboard_listener:

            record_keyboard_listener.stop()

    except Exception:
        pass

    mouse_listener = None

    record_keyboard_listener = None

    # --------------------------------------------------------
    # Actualizar interfaz
    # --------------------------------------------------------

    with events_lock:

        count = len(events)

    status_var.set(
        f"Grabación detenida — {count} eventos"
    )

    record_button.config(
        text="🔴 Grabar"
    )

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

        root.after(
            0,
            update_play_button
        )

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

                "Repeticiones debe ser "
                "un número entero o ∞."
            )
        )

        playing = False

        root.after(
            0,
            update_play_button
        )

        return

    # ========================================================
    # PAUSA ENTRE CICLOS
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

                "La pausa entre ciclos "
                "debe ser 0 o mayor."
            )
        )

        playing = False

        root.after(
            0,
            update_play_button
        )

        return

    # ========================================================
    # COPIA DE EVENTOS
    # ========================================================

    with events_lock:

        playback_events = list(
            events
        )

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

                delay = event.get(
                    "delay",
                    0
                )

                try:

                    delay = float(
                        delay
                    )

                except Exception:

                    delay = 0

                delay = max(

                    0,

                    delay / speed
                )

                if not interruptible_sleep(
                    delay
                ):

                    break

                # =================================================
                # MOVIMIENTO
                # =================================================

                if event["type"] == "move":

                    pyautogui.moveTo(

                        int(event["x"]),

                        int(event["y"]),

                        duration=0
                    )

                # =================================================
                # CLICK
                # =================================================

                elif event["type"] == "click":

                    pyautogui.moveTo(

                        int(event["x"]),

                        int(event["y"]),

                        duration=0
                    )

                    button = event.get(
                        "button",
                        "left"
                    )

                    pressed = event.get(
                        "pressed",
                        True
                    )

                    if button == "left":

                        py_button = "left"

                    elif button == "right":

                        py_button = "right"

                    elif button == "middle":

                        py_button = "middle"

                    else:

                        py_button = "left"

                    if pressed:

                        pyautogui.mouseDown(

                            button=py_button
                        )

                    else:

                        pyautogui.mouseUp(

                            button=py_button
                        )

                # =================================================
                # SCROLL
                # =================================================

                elif event["type"] == "scroll":

                    pyautogui.moveTo(

                        int(event["x"]),

                        int(event["y"]),

                        duration=0
                    )

                    pyautogui.scroll(

                        int(event["dy"])
                    )

                # =================================================
                # TECLA PRESIONADA
                # =================================================

                elif event["type"] == "key_down":

                    key = string_to_key(

                        event["key"]
                    )

                    if key is not None:

                        pyautogui.keyDown(
                            key
                        )

                # =================================================
                # TECLA LIBERADA
                # =================================================

                elif event["type"] == "key_up":

                    key = string_to_key(

                        event["key"]
                    )

                    if key is not None:

                        pyautogui.keyUp(
                            key
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

    # ========================================================
    # FAILSAFE
    # ========================================================

    except pyautogui.FailSafeException:

        playing = False

        stop_play_event.set()

        root.after(

            0,

            lambda: messagebox.showwarning(

                "Emergencia",

                "La reproducción fue detenida.\n\n"

                "El mouse llegó a la esquina "
                "superior izquierda."
            )
        )

    # ========================================================
    # ERROR
    # ========================================================

    except Exception as error:

        playing = False

        root.after(

            0,

            lambda: messagebox.showerror(

                "Error durante la reproducción",

                f"Ocurrió un error:\n\n{error}"
            )
        )

    # ========================================================
    # FINAL
    # ========================================================

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

                f"Reproducción terminada — "
                f"ciclos: {count}"
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

    if playing:

        stop_playback()

        return

    stop_play_event.clear()

    playing = True

    status_var.set(
        "▶ REPRODUCIENDO"
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
# ACTUALIZAR BOTÓN DE REPRODUCCIÓN
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
# BORRAR TODO
# ============================================================

def clear_recording():

    if recording or playing:

        messagebox.showwarning(

            "Automatizador",

            "Detén la grabación/reproducción "
            "antes de borrar."
        )

        return

    with events_lock:

        events.clear()

    refresh_event_list()

    status_var.set(
        "Sin grabación"
    )


# ============================================================
# DESCRIPCIÓN DE EVENTOS
# ============================================================

def event_description(event):

    event_type = event.get(
        "type",
        "?"
    )

    # --------------------------------------------------------
    # Movimiento
    # --------------------------------------------------------

    if event_type == "move":

        return (

            f"🖱 Movimiento → "

            f"({event.get('x')}, "
            f"{event.get('y')})"
        )

    # --------------------------------------------------------
    # Click
    # --------------------------------------------------------

    if event_type == "click":

        action = (

            "DOWN"

            if event.get(
                "pressed",
                True
            )

            else "UP"
        )

        return (

            f"🖱 Clic "
            f"{event.get('button')} "
            f"{action} → "

            f"({event.get('x')}, "
            f"{event.get('y')})"
        )

    # --------------------------------------------------------
    # Scroll
    # --------------------------------------------------------

    if event_type == "scroll":

        return (

            f"🖱 Scroll → "

            f"({event.get('dx')}, "
            f"{event.get('dy')})"
        )

    # --------------------------------------------------------
    # Tecla
    # --------------------------------------------------------

    if event_type == "key_down":

        return (

            f"⌨ Tecla DOWN → "

            f"{event['key'].get('value')}"
        )

    if event_type == "key_up":

        return (

            f"⌨ Tecla UP → "

            f"{event['key'].get('value')}"
        )

    return event_type


# ============================================================
# ACTUALIZAR LISTA
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

                event_description(
                    event
                ),

                f"{event.get('delay', 0):.3f} s"
            )
        )


# ============================================================
# ELIMINAR EVENTO
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

            if (

                0 <= index < len(events)

            ):

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

        title="Guardar macro",

        defaultextension=".json",

        filetypes=[

            ("Macro JSON", "*.json")

        ]
    )

    if not path:
        return

    try:

        with open(

            path,

            "w",

            encoding="utf-8"

        ) as file:

            json.dump(

                current_events,

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

            "Detén la grabación/reproducción "
            "antes de cargar."
        )

        return

    path = filedialog.askopenfilename(

        title="Cargar macro",

        filetypes=[

            ("Macro JSON", "*.json")

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

        if not isinstance(

            loaded,

            list

        ):

            raise ValueError(

                "El archivo no contiene "
                "una lista de eventos."
            )

        with events_lock:

            events = loaded

        refresh_event_list()

        status_var.set(

            f"Cargado: "
            f"{os.path.basename(path)}"
        )

    except Exception as error:

        messagebox.showerror(

            "Error",

            f"No se pudo cargar:\n\n{error}"
        )


# ============================================================
# INTERFAZ
# ============================================================

root = tk.Tk()

root.title(
    "Automatizador de Mouse V2"
)

root.geometry(
    "920x680"
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

    text="AUTOMATIZADOR V2",

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
        "Mouse + teclado + rueda + tiempos exactos"
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
# LISTA DE EVENTOS
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

    height=15,

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

    width=670
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
    pady=5
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
# LISTENER GLOBAL DE ATAJOS
# ============================================================

try:

    global_keyboard_listener = keyboard.Listener(

        on_press=global_key_press
    )

    global_keyboard_listener.start()

except Exception as error:

    messagebox.showerror(

        "Error",

        "No se pudo iniciar el listener global "
        "del teclado.\n\n"

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

    stop_play_event.set()

    # --------------------------------------------------------
    # Mouse
    # --------------------------------------------------------

    try:

        if mouse_listener:

            mouse_listener.stop()

    except Exception:
        pass

    # --------------------------------------------------------
    # Teclado de grabación
    # --------------------------------------------------------

    try:

        if record_keyboard_listener:

            record_keyboard_listener.stop()

    except Exception:
        pass

    # --------------------------------------------------------
    # Teclado global
    # --------------------------------------------------------

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
