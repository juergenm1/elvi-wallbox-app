# -*- coding: utf-8 -*-
"""
Elvi Wallbox Steuerung – Android App (Kivy)

Portierung des ursprünglichen Konsolen-Python-Skripts.
Die komplette Protokoll-Logik (Checksum, Befehlsaufbau, Socket-Kommunikation)
ist unverändert übernommen. Neu ist die grafische Oberfläche sowie das
Ausführen der Netzwerkkommunikation in einem Hintergrund-Thread, damit die
App während des Wartens (u. a. 25 Sekunden Pause) nicht einfriert.
"""

import socket
import threading
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from kivy.core.window import Window
Window.clearcolor = (0.05, 0.08, 0.12, 1)


# ---------------------------------------------------------------------------
# Original Wallbox-Logik (unverändert aus dem Konsolenskript übernommen)
# ---------------------------------------------------------------------------

def checksum_elvi(command):
    # Calculates the Fletcher-8 checksum (sum modulo 256) and the XOR-checksum of
    # the command string. The characters of the command string are Ascii characters
    # interpreted as hex numbers.
    ck_a = 0
    ck_b = 0

    for b in command:
        ck_a += b
        ck_a %= 0x100
        ck_b ^= b

    ck_a_out = hex(ck_a).rstrip("L").lstrip("0x") or "0"
    ck_a_out = ck_a_out.upper()
    if len(ck_a_out) < 2:
        ck_a_out = "0" + ck_a_out

    ck_b_out = hex(ck_b).rstrip("L").lstrip("0x") or "0"
    ck_b_out = ck_b_out.upper()
    if len(ck_b_out) < 2:
        ck_b_out = "0" + ck_b_out
    checksum = ck_a_out + ck_b_out
    return checksum


def build_charge_current_string(charge_current):
    current_hex = hex(int(charge_current * 10))
    if len(current_hex) == 5:
        charge_current_str = "0" + current_hex.upper()[2:]
    else:
        charge_current_str = "00" + current_hex.upper()[2:]
    return charge_current_str


def build_wallbox_send_str(charge_current_str):
    start = b"\x02"
    dest_address = "80"
    source_address = "A0"
    command = "69"
    max_phase_current = charge_current_str
    timeout = "003C"  # 60 seconds
    max_phase_current_after_timeout = charge_current_str
    stop = b"\x03"
    addr_cmd_data_str = (
        dest_address + source_address + command +
        max_phase_current + max_phase_current + max_phase_current + timeout +
        max_phase_current_after_timeout + max_phase_current_after_timeout +
        max_phase_current_after_timeout
    )
    addr_cmd_data_bytes = bytes(addr_cmd_data_str, 'utf-8')
    checksum = checksum_elvi(addr_cmd_data_bytes)
    command_bytes = start + bytes(addr_cmd_data_str + checksum, 'utf-8') + stop
    return command_bytes, charge_current_str


def send_charge_command(command_byt, host, port, log, max_retries=5):
    # Sends the command (bytes) to the Elvi and analyzes the response.
    # Im Gegensatz zum Originalskript gibt es hier ein Retry-Limit, damit die
    # App bei dauerhaftem Verbindungsfehler nicht endlos blockiert.
    data = {}
    attempts = 0
    while data == {} and attempts < max_retries:
        attempts += 1
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.settimeout(10)
                s.connect((host, port))
                s.sendall(command_byt)
                data = s.recv(1024)
            except Exception as e:
                log("Fehler beim Senden an %s:%d: %s" % (host, port, e))
                time.sleep(1)
            finally:
                s.close()
    return data


def analyze_charge_command_answer(data, charge_current, log):
    wb_data = {}
    data_corrupted = False
    current_time = time.strftime("%H:%M:%S", time.localtime())
    wb_data['Time'] = current_time
    try:
        wb_data['Current_L1'] = int(data[21:25], base=16) / 10
        wb_data['Charge_current'] = round(wb_data['Current_L1'], 1)
    except Exception:
        data_corrupted = True
        log("Konnte Strom L1 nicht auslesen: %s" % data)
        wb_data['Current_L1'] = 0
        wb_data['Charge_current'] = charge_current

    if not data_corrupted:
        try:
            wb_data['Current_L2'] = int(data[25:29], base=16) / 10
        except Exception:
            data_corrupted = True
            log("Konnte Strom L2 nicht auslesen: %s" % data)
            wb_data['Current_L2'] = 0

    if not data_corrupted:
        try:
            wb_data['Current_L3'] = int(data[29:33], base=16) / 10
        except Exception:
            log("Konnte Strom L3 nicht auslesen: %s" % data)
            wb_data['Current_L3'] = 0

    if not data_corrupted:
        line_voltage = 230
        wb_data['Charging_power'] = round(
            line_voltage / 1000 * (wb_data['Current_L1'] + wb_data['Current_L2'] + wb_data['Current_L3']), 1
        )
        wb_data['Power_lines'] = 0
        if wb_data['Charging_power'] > 1 and wb_data['Current_L2'] > 1:
            wb_data['Power_lines'] = 3
        elif wb_data['Charging_power'] > 1 and wb_data['Current_L2'] < 1:
            wb_data['Power_lines'] = 1
        else:
            log("Laden noch nicht gestartet. Nach dem Start ggf. Leistung nochmal senden.")

        try:
            wb_data['Total'] = int(data[45:53], base=16) / 1000
        except Exception:
            log("Konnte Zählerstand nicht auslesen: %s" % data)
            wb_data['Total'] = 0
            wb_data['Session_charge'] = 0

        log("Aktuell: L1=%s A, L2=%s A, L3=%s A, Ladeleistung=%s kW" % (
            wb_data['Current_L1'], wb_data['Current_L2'], wb_data['Current_L3'], wb_data['Charging_power']))
        log("Zählerstand Wallbox: %s kWh" % wb_data.get('Total', 0))

    return wb_data


def get_wb_data(charge_current, host, port, log, wait_seconds=25):
    charge_current_str = build_charge_current_string(charge_current)
    command = build_wallbox_send_str(charge_current_str)[0]
    send_charge_command(command, host, port, log)
    log("Neuen Ladestrom gesendet: %s A. Warte %s s auf Kontrolle..." % (charge_current, wait_seconds))

    time.sleep(wait_seconds)
    data = send_charge_command(command, host, port, log)
    log("Kontrolle Ladestrom, Sollwert: %s A" % charge_current)
    wb_data = {}
    if data:
        wb_data = analyze_charge_command_answer(data, charge_current, log)
    return wb_data


# ---------------------------------------------------------------------------
# Kivy Oberfläche
# ---------------------------------------------------------------------------

class WallboxLayout(BoxLayout):
    pass


class ElviWallboxApp(App):
    def build(self):

    self.title = "Elvi Wallbox"

    root = BoxLayout(
        orientation='vertical',
        padding=dp(20),
        spacing=dp(15)
    )

    title = Label(
        text="⚡ ELVI WALLBOX",
        font_size="30sp",
        bold=True,
        color=(0.1, 0.85, 0.65, 1),
        size_hint_y=None,
        height=dp(60)
    )
    root.add_widget(title)

    subtitle = Label(
        text="Ladesteuerung",
        font_size="16sp",
        color=(0.8, 0.9, 1, 1),
        size_hint_y=None,
        height=dp(25)
    )
    root.add_widget(subtitle)

    root.add_widget(Label(
        text="Verbindung",
        color=(0.6, 0.85, 1, 1),
        font_size="18sp",
        size_hint_y=None,
        height=dp(30)
    ))

    conn_row = BoxLayout(
        orientation='horizontal',
        size_hint_y=None,
        height=dp(55),
        spacing=dp(10)
    )

    self.host_input = TextInput(
        text="60.60.60.26",
        hint_text="IP-Adresse",
        multiline=False,
        background_color=(0.15, 0.18, 0.22, 1),
        foreground_color=(1, 1, 1, 1)
    )

    self.port_input = TextInput(
        text="8898",
        hint_text="Port",
        multiline=False,
        size_hint_x=0.35,
        background_color=(0.15, 0.18, 0.22, 1),
        foreground_color=(1, 1, 1, 1)
    )

    conn_row.add_widget(self.host_input)
    conn_row.add_widget(self.port_input)

    root.add_widget(conn_row)

    root.add_widget(Label(
        text="Ladeleistung",
        color=(0.6, 0.85, 1, 1),
        font_size="18sp",
        size_hint_y=None,
        height=dp(30)
    ))

    power_row = BoxLayout(
        orientation='horizontal',
        size_hint_y=None,
        height=dp(55),
        spacing=dp(10)
    )

    power_row.add_widget(Label(
        text="4.14 - 11.04 kW",
        size_hint_x=0.6,
        color=(1, 1, 1, 1)
    ))

    self.power_input = TextInput(
        text="11.04",
        multiline=False,
        input_filter='float',
        size_hint_x=0.4,
        background_color=(0.15, 0.18, 0.22, 1),
        foreground_color=(1, 1, 1, 1)
    )

    power_row.add_widget(self.power_input)

    root.add_widget(power_row)

    self.send_button = Button(
        text="⚡ Ladeleistung senden",
        size_hint_y=None,
        height=dp(65),
        background_normal='',
        background_color=(0.10, 0.75, 0.55, 1),
        color=(1, 1, 1, 1),
        font_size='18sp',
        bold=True
    )

    self.send_button.bind(on_press=self.on_send_pressed)

    root.add_widget(self.send_button)

    self.status_label = Label(
        text="✅ Bereit",
        size_hint_y=None,
        height=dp(40),
        color=(0.6, 1, 0.6, 1),
        font_size='18sp'
    )

    root.add_widget(self.status_label)

    root.add_widget(Label(
        text="Protokoll",
        font_size='18sp',
        color=(0.6, 0.85, 1, 1),
        size_hint_y=None,
        height=dp(30)
    ))

    self.log_label = Label(
        text="",
        size_hint_y=None,
        valign='top',
        halign='left',
        color=(0.95, 0.98, 1, 1),
        font_size='16sp'
    )

    self.log_label.bind(
        width=lambda inst, w:
        setattr(inst, 'text_size', (w, None))
    )

    self.log_label.bind(
        texture_size=lambda inst, ts:
        setattr(inst, 'height', ts[1])
    )

    scroll = ScrollView()
    scroll.add_widget(self.log_label)

    root.add_widget(scroll)

    return root

    # -- Logging Hilfsfunktion (thread-sicher über Clock) --------------------
    def log(self, message):
        def _update(dt):
            self.log_label.text += message + "\n"
        Clock.schedule_once(_update, 0)

    def set_status(self, text):
        def _update(dt):
            self.status_label.text = text
        Clock.schedule_once(_update, 0)

    # -- Button-Handler --------------------------------------------------
    def on_send_pressed(self, instance):
        try:
            charge_power = round(float(self.power_input.text.replace(',', '.')), 2)
        except ValueError:
            self.set_status("Bitte eine gültige Zahl eingeben.")
            return

        if charge_power < 4.14:
            charge_power = 4.14
        elif charge_power > 11.04:
            charge_power = 11.04
        self.power_input.text = str(charge_power)

        host = self.host_input.text.strip()
        try:
            port = int(self.port_input.text.strip())
        except ValueError:
            self.set_status("Ungültiger Port.")
            return

        self.send_button.disabled = True
        self.set_status("Sende Ladeleistung %s kW..." % charge_power)

        thread = threading.Thread(
            target=self._run_charge_sequence,
            args=(charge_power, host, port),
            daemon=True,
        )
        thread.start()

    # -- Hintergrund-Thread: eigentliche Netzwerklogik --------------------
    def _run_charge_sequence(self, charge_power, host, port):
        self.log("")
        self.log("Neue Ladeleistung: %s kW" % charge_power)
        charge_current = round(charge_power * 1000 / 3 / 230, 1)
        self.log("Neuer Ladestrom: %s A" % charge_current)

        wb_data = get_wb_data(charge_current, host, port, self.log)

        if wb_data.get('Power_lines') == 1:
            self.log("")
            self.log("Nur eine Phase aktiv, Ladestrom wird maximal erhöht...")
            charge_current = 16.0
            self.log("Neuer Ladestrom: %s A" % charge_current)
            wb_data = get_wb_data(charge_current, host, port, self.log)

        self.set_status("Fertig.")

        def _reenable(dt):
            self.send_button.disabled = False
        Clock.schedule_once(_reenable, 0)


if __name__ == "__main__":
    ElviWallboxApp().run()
