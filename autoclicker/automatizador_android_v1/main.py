import json
import os
import time
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner

class GestureRecorder:
    def __init__(self):
        self.recording = False
        self.events = []
        self.last_time = None
    def start(self):
        self.events = []
        self.recording = True
        self.last_time = time.perf_counter()
    def stop(self):
        self.recording = False
    def add_event(self, event):
        if not self.recording:
            return
        now = time.perf_counter()
        if self.last_time is None:
            delay = 0
        else:
            delay = now - self.last_time
        event["delay"] = delay
        self.events.append(event)
        self.last_time = now
class GestureArea(BoxLayout):
    def __init__(self, recorder, **kwargs):
        super().__init__(**kwargs)
        self.recorder = recorder
        self.active_touches = {}
        self.start_positions = {}
        self.start_times = {}
        self.touch_moved = {}
        self.orientation = "vertical"
        self.label = Label(
            text=(
                "ÁREA DE GESTOS\n\n"
                "Toca o desliza aquí para registrar\n"
                "tus gestos."
            ),
            halign="center",
            valign="middle",
            font_size=dp(20)
        )
        self.label.bind(
            size=self.update_label
        )
        self.add_widget(self.label)
    def update_label(self, instance, value):
        instance.text_size = value
    def on_touch_down(self, touch):
        if not self.collide_point(
            *touch.pos
        ):
            return super().on_touch_down(touch)
        self.active_touches[touch.uid] = touch
        self.start_positions[touch.uid] = (
            touch.x,
            touch.y
        )
        self.start_times[touch.uid] = time.perf_counter()
        self.touch_moved[touch.uid] = False
        return True
    def on_touch_move(self, touch):
        if touch.uid not in self.active_touches:
            return super().on_touch_move(touch)
        start_x, start_y = self.start_positions[
            touch.uid
        ]
        distance = (
            abs(touch.x - start_x)
            +
            abs(touch.y - start_y)
        )
        if distance > dp(10):
            self.touch_moved[touch.uid] = True
        return True
    def on_touch_up(self, touch):
        if touch.uid not in self.active_touches:
            return super().on_touch_up(touch)
        start_x, start_y = self.start_positions[
            touch.uid
        ]
        end_x = touch.x
        end_y = touch.y
        start_time = self.start_times[
            touch.uid
        ]

        duration = time.perf_counter() - start_time

        moved = self.touch_moved[
            touch.uid
        ]

        if moved:

            event = {
                "type": "swipe",
                "start_x": start_x,
                "start_y": start_y,
                "end_x": end_x,
                "end_y": end_y,
                "duration": duration
            }

        else:

            event = {
                "type": "tap",
                "x": end_x,
                "y": end_y
            }

        self.recorder.add_event(event)

        del self.active_touches[touch.uid]
        del self.start_positions[touch.uid]
        del self.start_times[touch.uid]
        del self.touch_moved[touch.uid]

        return True


class AutomatorApp(App):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.recorder = GestureRecorder()

        self.playing = False

        self.play_index = 0
        self.play_count = 0

        self.speed = 1.0
        self.repetitions = 1

        self.gesture_area = None

        self.event_list = None

        self.status_label = None

        self.speed_input = None
        self.repeat_input = None

    # ========================================================
    # INTERFAZ
    # ========================================================

    def build(self):

        root = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(8)
        )

        # ----------------------------------------------------
        # TÍTULO
        # ----------------------------------------------------

        title = Label(
            text="AUTOMATIZADOR ANDROID V1",
            size_hint_y=None,
            height=dp(45),
            font_size=dp(22),
            bold=True
        )

        root.add_widget(title)

        # ----------------------------------------------------
        # BOTONES
        # ----------------------------------------------------

        controls = GridLayout(
            cols=2,
            size_hint_y=None,
            height=dp(100),
            spacing=dp(6)
        )

        self.record_button = Button(
            text="🔴 GRABAR"
        )

        self.record_button.bind(
            on_press=self.toggle_recording
        )

        controls.add_widget(
            self.record_button
        )

        self.play_button = Button(
            text="▶ REPRODUCIR"
        )

        self.play_button.bind(
            on_press=self.toggle_playback
        )

        controls.add_widget(
            self.play_button
        )

        clear_button = Button(
            text="🗑 BORRAR"
        )

        clear_button.bind(
            on_press=self.clear_events
        )

        controls.add_widget(
            clear_button
        )

        save_button = Button(
            text="💾 GUARDAR"
        )

        save_button.bind(
            on_press=self.save_events
        )

        controls.add_widget(
            save_button
        )

        root.add_widget(
            controls
        )

        # ----------------------------------------------------
        # CONFIGURACIÓN
        # ----------------------------------------------------

        config = GridLayout(
            cols=4,
            size_hint_y=None,
            height=dp(50),
            spacing=dp(5)
        )

        config.add_widget(
            Label(
                text="Velocidad:"
            )
        )
        self.speed_input = TextInput(
            text="1.0",
            multiline=False,
            input_filter="float"
        )

        config.add_widget(
            self.speed_input
        )

        config.add_widget(
            Label(
                text="Repeticiones:"
            )
        )
        self.repeat_input = TextInput(
            text="1",
            multiline=False
        )
        config.add_widget(
            self.repeat_input
        )
        root.add_widget(
            config
        )
        # ----------------------------------------------------
        # ESTADO
        # ----------------------------------------------------
        self.status_label = Label(
            text="Sin grabación",
            size_hint_y=None,
            height=dp(35)
        )
        root.add_widget(
            self.status_label
        )
        # ----------------------------------------------------
        # ÁREA DE GESTOS
        # ----------------------------------------------------

        self.gesture_area = GestureArea(
            self.recorder
        )

        root.add_widget(
            self.gesture_area
        )

        # ----------------------------------------------------
        # LISTA DE EVENTOS
        # ----------------------------------------------------

        list_title = Label(
            text="Gestos registrados",
            size_hint_y=None,
            height=dp(35),
            bold=True
        )

        root.add_widget(
            list_title
        )

        scroll = ScrollView(
            size_hint_y=0.8
        )

        self.event_list = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(3)
        )

        self.event_list.bind(
            minimum_height=self.event_list.setter(
                "height"
            )
        )

        scroll.add_widget(
            self.event_list
        )

        root.add_widget(
            scroll
        )

        return root

    # ========================================================
    # GRABACIÓN
    # ========================================================

    def toggle_recording(self, instance):

        if self.playing:

            self.status_label.text = (
                "Detén la reproducción primero."
            )

            return

        if self.recorder.recording:

            self.recorder.stop()

            self.record_button.text = (
                "🔴 GRABAR"
            )

            self.status_label.text = (
                f"Grabación detenida — "
                f"{len(self.recorder.events)} gestos"
            )

            self.refresh_event_list()

        else:

            self.recorder.start()

            self.record_button.text = (
                "⏹ DETENER"
            )

            self.status_label.text = (
                "🔴 GRABANDO..."
            )

    # ========================================================
    # REPRODUCCIÓN
    # ========================================================

    def toggle_playback(self, instance):

        if self.recorder.recording:

            self.status_label.text = (
                "Detén la grabación primero."
            )

            return

        if not self.recorder.events:

            self.status_label.text = (
                "No hay gestos registrados."
            )

            return

        if self.playing:

            self.stop_playback()

        else:

            self.start_playback()

    def start_playback(self):

        try:

            self.speed = float(
                self.speed_input.text
            )

            if self.speed <= 0:
                raise ValueError

        except ValueError:

            self.status_label.text = (
                "Velocidad inválida."
            )

            return

        try:

            repetitions_text = (
                self.repeat_input.text
                .strip()
                .lower()
            )

            if repetitions_text in (
                "∞",
                "inf",
                "infinito"
            ):

                self.repetitions = None

            else:

                self.repetitions = int(
                    repetitions_text
                )

                if self.repetitions < 1:
                    raise ValueError

        except ValueError:

            self.status_label.text = (
                "Repeticiones inválidas."
            )

            return

        self.playing = True

        self.play_index = 0
        self.play_count = 0

        self.play_button.text = (
            "⏹ DETENER"
        )

        self.status_label.text = (
            "▶ REPRODUCIENDO"
        )

        self.play_next()

    def stop_playback(self):

        self.playing = False

        self.play_button.text = (
            "▶ REPRODUCIR"
        )

        self.status_label.text = (
            "Reproducción detenida."
        )

    # ========================================================
    # REPRODUCIR EVENTO
    # ========================================================

    def play_next(self, dt=0):

        if not self.playing:
            return

        if self.play_index >= len(
            self.recorder.events
        ):

            self.play_count += 1

            if (
                self.repetitions is not None
                and
                self.play_count >= self.repetitions
            ):

                self.stop_playback()

                return

            self.play_index = 0

        event = self.recorder.events[
            self.play_index
        ]

        self.play_index += 1

        delay = event.get(
            "delay",
            0
        )

        delay /= self.speed

        Clock.schedule_once(
            self.execute_event,
            delay
        )

    # ========================================================
    # EJECUTAR EVENTO
    # ========================================================
    def execute_event(self, dt):
        if not self.playing:
            return
        event = self.recorder.events[
            self.play_index - 1
        ]
        event_type = event.get(
            "type"
        )
        # ----------------------------------------------------
        # En esta V1 la reproducción visualiza el gesto
        # dentro del área de la aplicación.
        #
        # La reproducción sobre otras aplicaciones será
        # implementada posteriormente mediante Android
        # Accessibility Service.
        # ----------------------------------------------------
        if event_type == "tap":
            self.gesture_area.label.text = (
                f"👆 TOQUE\n\n"
                f"X: {event['x']:.0f}\n"
                f"Y: {event['y']:.0f}"
            )
        elif event_type == "swipe":
            self.gesture_area.label.text = (
                f"👉 DESLIZAMIENTO\n\n"
                f"({event['start_x']:.0f}, "
                f"{event['start_y']:.0f})\n"
                f"↓\n"
                f"({event['end_x']:.0f}, "
                f"{event['end_y']:.0f})"
            )
        self.play_next()
    # ========================================================
    # BORRAR
    # ========================================================
    def clear_events(self, instance):
        if self.recorder.recording:
            return
        if self.playing:
            self.stop_playback()
        self.recorder.events = []
        self.refresh_event_list()
        self.status_label.text = (
            "Sin grabación"
        )
    # ========================================================
    # ACTUALIZAR LISTA
    # ========================================================
    def refresh_event_list(self):
        self.event_list.clear_widgets()
        for index, event in enumerate(
            self.recorder.events,
            start=1
        ):
            event_type = event.get(
                "type"
            )
            if event_type == "tap":
                text = (
                    f"{index}. 👆 Toque — "
                    f"({event['x']:.0f}, "
                    f"{event['y']:.0f})"
                )
            elif event_type == "swipe":
                text = (
                    f"{index}. 👉 Swipe — "
                    f"({event['start_x']:.0f}, "
                    f"{event['start_y']:.0f}) → "
                    f"({event['end_x']:.0f}, "
                    f"{event['end_y']:.0f})"
                )
            else:
                text = (
                    f"{index}. {event_type}"
                )
            text += (
                f" | espera: "
                f"{event.get('delay', 0):.2f}s"
            )
            label = Label(
                text=text,
                size_hint_y=None,
                height=dp(35),
                halign="left"
            )
            label.bind(
                size=lambda obj, value: setattr(
                    obj,
                    "text_size",
                    (value[0], None)
                )
            )
            self.event_list.add_widget(
                label
            )
    # ========================================================
    # GUARDAR
    # ========================================================
    def save_events(self, instance):
        if not self.recorder.events:
            self.status_label.text = (
                "No hay gestos para guardar."
            )
            return
        path = os.path.join(
            App.get_running_app().user_data_dir,
            "macro.json"
        )
        try:
            with open(
                path,
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(
                    self.recorder.events,
                    file,
                    ensure_ascii=False,
                    indent=2
                )
            self.status_label.text = (
                "Macro guardada."
            )
        except Exception as error:
            self.status_label.text = (
                f"Error: {error}"
            )
if __name__ == "__main__":
    AutomatorApp().run()
  #copyright @hypergecko491
