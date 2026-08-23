import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyautogui
import threading
import time
import json
import os

# ============================================================
# AUTOMATIZADOR DE MOUSE - V1
# F6 = iniciar/detener grabación
# F8 = iniciar/detener reproducción
# ESC = detener reproducción
# ============================================================

pyautogui.PAUSE = 0.01
pyautogui.FAILSAFE = True  # Mueve el mouse a la esquina superior izquierda para emergencia.

recording = False
playing = False
events = []
record_thread = None
play_thread = None
last_position = None
last_event_time = None


def add_event(event_type, x=None, y=None, button=None, delay=0):
    events.append({
        "type": event_type,
        "x": x,
        "y": y,
        "button": button,
        "delay": delay
    })


def record_loop():
    """Registra la posición del mouse mientras F6 está activo."""
    global last_position, last_event_time

    last_position = pyautogui.position()
    last_event_time = time.perf_counter()

    # Guardamos la posición inicial.
    add_event(
        "move",
        last_position.x,
        last_position.y,
        delay=0
    )

    while recording:
        pos = pyautogui.position()
        now = time.perf_counter()

        # Solo guardamos un movimiento cuando cambió la posición.
        if pos != last_position:
            delay = now - last_event_time

            # Agrupamos pequeños movimientos para no crear miles de eventos.
            add_event("move", pos.x, pos.y, delay=delay)

            last_position = pos
            last_event_time = now

        time.sleep(0.01)


def start_recording():
    global recording, events, record_thread

    if recording:
        stop_recording()
        return

    if playing:
        messagebox.showwarning("Automatizador", "Detén la reproducción antes de grabar.")
        return

    events = []
    recording = True

    status_var.set("🔴 GRABANDO — realiza los movimientos y clics")
    record_button.config(text="⏹ Detener grabación")

    record_thread = threading.Thread(target=record_loop, daemon=True)
    record_thread.start()


def stop_recording():
    global recording

    recording = False

    status_var.set(f"Grabación detenida — {len(events)} eventos")
    record_button.config(text="🔴 Grabar")


def mouse_click_listener(x, y, button, pressed):
    """Captura clics mientras estamos grabando."""
    global last_event_time, last_position

    if not recording or not pressed:
        return

    now = time.perf_counter()
    delay = now - last_event_time

    add_event(
        "click",
        x,
        y,
        button=str(button),
        delay=delay
    )

    last_event_time = now
    last_position = pyautogui.position()


def play_events():
    global playing

    try:
        speed = float(speed_var.get())
        if speed <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("Error", "La velocidad debe ser un número mayor que 0.")
        playing = False
        return

    try:
        repetitions_text = repetitions_var.get().strip().lower()

        if repetitions_text in ("∞", "inf", "infinito"):
            repetitions = None
        else:
            repetitions = int(repetitions_text)
            if repetitions < 1:
                raise ValueError
    except ValueError:
        messagebox.showerror(
            "Error",
            "Repeticiones debe ser un número entero o ∞."
        )
        playing = False
        return

    count = 0

    try:
        while playing and (repetitions is None or count < repetitions):
            for event in events:
                if not playing:
                    break

                # El delay también se escala con la velocidad.
                delay = event.get("delay", 0) / speed

                # Espera interrumpible.
                end_time = time.perf_counter() + delay
                while playing and time.perf_counter() < end_time:
                    time.sleep(0.01)

                if not playing:
                    break

                if event["type"] == "move":
                    pyautogui.moveTo(
                        event["x"],
                        event["y"],
                        duration=0
                    )

                elif event["type"] == "click":
                    pyautogui.moveTo(
                        event["x"],
                        event["y"],
                        duration=0
                    )
                    pyautogui.click(
                        button=event["button"]
                    )

            count += 1

            # Pausa opcional entre ciclos.
            try:
                loop_delay = max(0, float(loop_delay_var.get()))
            except ValueError:
                loop_delay = 0

            if playing and (repetitions is None or count < repetitions):
                end_time = time.perf_counter() + loop_delay
                while playing and time.perf_counter() < end_time:
                    time.sleep(0.01)

    except pyautogui.FailSafeException:
        root.after(
            0,
            lambda: messagebox.showwarning(
                "Emergencia",
                "Reproducción detenida porque el mouse llegó a la esquina superior izquierda."
            )
        )

    finally:
        playing = False
        root.after(0, update_play_button)


def start_playback():
    global playing, play_thread

    if recording:
        messagebox.showwarning("Automatizador", "Detén la grabación antes de reproducir.")
        return

    if not events:
        messagebox.showinfo("Automatizador", "Primero realiza una grabación.")
        return

    if playing:
        stop_playback()
        return

    playing = True
    status_var.set("▶ REPRODUCIENDO")
    play_button.config(text="⏹ Detener reproducción")

    play_thread = threading.Thread(target=play_events, daemon=True)
    play_thread.start()


def stop_playback():
    global playing
    playing = False
    status_var.set("Reproducción detenida")
    update_play_button()


def update_play_button():
    if playing:
        play_button.config(text="⏹ Detener reproducción")
    else:
        play_button.config(text="▶ Reproducir")


def clear_recording():
    global events

    if recording or playing:
        messagebox.showwarning(
            "Automatizador",
            "Detén la grabación/reproducción antes de borrar."
        )
        return

    events = []
    status_var.set("Sin grabación")
    refresh_event_list()


def refresh_event_list():
    event_list.delete(*event_list.get_children())

    for i, event in enumerate(events, start=1):
        event_type = event["type"]

        if event_type == "move":
            description = f"Mover → ({event['x']}, {event['y']})"
        elif event_type == "click":
            description = f"Clic {event['button']} → ({event['x']}, {event['y']})"
        else:
            description = event_type

        event_list.insert(
            "",
            "end",
            values=(
                i,
                description,
                f"{event.get('delay', 0):.3f} s"
            )
        )


def save_recording():
    if not events:
        messagebox.showinfo("Automatizador", "No hay ninguna grabación.")
        return

    path = filedialog.asksaveasfilename(
        title="Guardar grabación",
        defaultextension=".json",
        filetypes=[("Grabación JSON", "*.json")]
    )

    if not path:
        return

    with open(path, "w", encoding="utf-8") as file:
        json.dump(events, file, ensure_ascii=False, indent=2)

    status_var.set(f"Grabación guardada: {os.path.basename(path)}")


def load_recording():
    global events

    if recording or playing:
        messagebox.showwarning(
            "Automatizador",
            "Detén la grabación/reproducción antes de cargar."
        )
        return

    path = filedialog.askopenfilename(
        title="Cargar grabación",
        filetypes=[("Grabación JSON", "*.json")]
    )

    if not path:
        return

    try:
        with open(path, "r", encoding="utf-8") as file:
            loaded = json.load(file)

        if not isinstance(loaded, list):
            raise ValueError

        events = loaded
        refresh_event_list()
        status_var.set(f"Grabación cargada: {os.path.basename(path)}")

    except Exception:
        messagebox.showerror(
            "Error",
            "No se pudo cargar la grabación."
        )


def on_f6(event=None):
    start_recording()


def on_f8(event=None):
    start_playback()


def on_escape(event=None):
    stop_recording()
    stop_playback()


# ============================================================
# Interfaz
# ============================================================

root = tk.Tk()
root.title("Automatizador de Mouse — V1")
root.geometry("760x560")
root.resizable(False, False)

style = ttk.Style()
try:
    style.theme_use("clam")
except tk.TclError:
    pass

title = ttk.Label(
    root,
    text="AUTOMATIZADOR DE MOUSE",
    font=("Segoe UI", 18, "bold")
)
title.pack(pady=(18, 4))

subtitle = ttk.Label(
    root,
    text="Graba tus movimientos y repítelos automáticamente",
    font=("Segoe UI", 10)
)
subtitle.pack(pady=(0, 15))

controls = ttk.Frame(root)
controls.pack(pady=5)

record_button = ttk.Button(
    controls,
    text="🔴 Grabar",
    command=start_recording,
    width=22
)
record_button.grid(row=0, column=0, padx=6)

play_button = ttk.Button(
    controls,
    text="▶ Reproducir",
    command=start_playback,
    width=22
)
play_button.grid(row=0, column=1, padx=6)

clear_button = ttk.Button(
    controls,
    text="🗑 Borrar",
    command=clear_recording,
    width=14
)
clear_button.grid(row=0, column=2, padx=6)

file_controls = ttk.Frame(root)
file_controls.pack(pady=8)

ttk.Button(
    file_controls,
    text="💾 Guardar",
    command=save_recording,
    width=18
).grid(row=0, column=0, padx=5)

ttk.Button(
    file_controls,
    text="📂 Cargar",
    command=load_recording,
    width=18
).grid(row=0, column=1, padx=5)

settings = ttk.LabelFrame(root, text="Configuración")
settings.pack(fill="x", padx=25, pady=12)

ttk.Label(settings, text="Velocidad:").grid(
    row=0, column=0, padx=(15, 5), pady=12
)

speed_var = tk.StringVar(value="1.0")
speed_entry = ttk.Entry(
    settings,
    textvariable=speed_var,
    width=10
)
speed_entry.grid(row=0, column=1, padx=5)

ttk.Label(
    settings,
    text="1.0 = normal | 2.0 = doble | 0.5 = mitad"
).grid(row=0, column=2, padx=15)

ttk.Label(settings, text="Repeticiones:").grid(
    row=1, column=0, padx=(15, 5), pady=8
)

repetitions_var = tk.StringVar(value="∞")
repetitions_entry = ttk.Entry(
    settings,
    textvariable=repetitions_var,
    width=10
)
repetitions_entry.grid(row=1, column=1, padx=5)

ttk.Label(
    settings,
    text="Usa ∞ para repetir indefinidamente"
).grid(row=1, column=2, padx=15)

ttk.Label(settings, text="Pausa entre ciclos (s):").grid(
    row=2, column=0, padx=(15, 5), pady=8
)

loop_delay_var = tk.StringVar(value="0")
loop_delay_entry = ttk.Entry(
    settings,
    textvariable=loop_delay_var,
    width=10
)
loop_delay_entry.grid(row=2, column=1, padx=5)

ttk.Label(
    settings,
    text="Tiempo de espera antes del siguiente ciclo"
).grid(row=2, column=2, padx=15)

list_frame = ttk.LabelFrame(
    root,
    text="Eventos registrados"
)
list_frame.pack(fill="both", expand=True, padx=25, pady=8)

columns = ("#", "Evento", "Espera")
event_list = ttk.Treeview(
    list_frame,
    columns=columns,
    show="headings",
    height=11
)

event_list.heading("#", text="#")
event_list.heading("Evento", text="Evento")
event_list.heading("Espera", text="Espera")

event_list.column("#", width=45, anchor="center")
event_list.column("Evento", width=500)
event_list.column("Espera", width=100, anchor="center")

scrollbar = ttk.Scrollbar(
    list_frame,
    orient="vertical",
    command=event_list.yview
)

event_list.configure(yscrollcommand=scrollbar.set)

event_list.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
scrollbar.pack(side="right", fill="y", padx=(0, 5), pady=5)

status_var = tk.StringVar(value="Sin grabación")

status = ttk.Label(
    root,
    textvariable=status_var,
    font=("Segoe UI", 10, "bold")
)
status.pack(pady=5)

help_text = ttk.Label(
    root,
    text="F6 = grabar/detener   |   F8 = reproducir/detener   |   ESC = emergencia",
    font=("Segoe UI", 9)
)
help_text.pack(pady=(0, 12))


# ============================================================
# Listener global de clics
# ============================================================
# Se usa pynput para poder detectar los clics mientras la
# ventana del programa no tiene el foco.
# ============================================================

try:
    from pynput import mouse

    mouse_listener = mouse.Listener(
        on_click=mouse_click_listener
    )
    mouse_listener.start()

except ImportError:
    messagebox.showerror(
        "Dependencia faltante",
        "Falta instalar pynput.\n\n"
        "Ejecuta:\n"
        "pip install pyautogui pynput"
    )
    root.destroy()
    raise SystemExit


root.bind_all("<F6>", on_f6)
root.bind_all("<F8>", on_f8)
root.bind_all("<Escape>", on_escape)


def close_program():
    global recording, playing

    recording = False
    playing = False

    try:
        mouse_listener.stop()
    except Exception:
        pass

    root.destroy()


root.protocol("WM_DELETE_WINDOW", close_program)

root.mainloop()
