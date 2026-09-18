# Elvi Wallbox – Android App

Portierung des ursprünglichen Konsolenskripts nach Kivy, damit daraus eine
Android-APK gebaut werden kann. Die Protokoll-Logik (Checksum, Befehlsaufbau,
Auswertung der Antwort) ist unverändert aus dem Original übernommen.

## Was wurde geändert?

- **UI statt `input()`/`print()`**: Ladeleistung wird über ein Eingabefeld
  gesetzt, Statusmeldungen erscheinen live in der App.
- **Hintergrund-Thread**: Der Netzwerk-Code (inkl. der 25-Sekunden-Pause)
  läuft in einem separaten Thread, damit die Oberfläche währenddessen nicht
  einfriert.
- **IP/Port editierbar**: Host und Port der Wallbox lassen sich in der App
  anpassen, falls sich die Netzwerkkonfiguration ändert.
- **Retry-Limit**: Die Endlos-Schleife beim Verbindungsaufbau wurde auf
  5 Versuche begrenzt (im Original lief sie unbegrenzt weiter).

## APK selbst bauen (Buildozer)

Buildozer läuft nur unter Linux (bzw. WSL unter Windows). Am einfachsten in
einer Ubuntu-Umgebung:

```bash
# Voraussetzungen installieren
sudo apt update
sudo apt install -y python3-pip build-essential git python3-dev \
    ffmpeg libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev zlib1g-dev \
    openjdk-17-jdk unzip

pip3 install --user buildozer cython

# In den Projektordner wechseln (die Dateien main.py und buildozer.spec
# müssen im selben Verzeichnis liegen)
cd ElviWallboxApp

# Debug-APK bauen (lädt beim ersten Mal Android SDK/NDK herunter, dauert)
buildozer -v android debug
```

Die fertige APK liegt danach unter `bin/elviwallbox-0.1-debug.apk` und kann
auf ein Android-Gerät übertragen und installiert werden (dort ggf.
"Installation aus unbekannten Quellen" erlauben).

## Alternative ohne eigenen Linux-Rechner

Falls kein Linux/WSL zur Verfügung steht, kann der Build auch über eine
**GitHub Actions Pipeline** (z. B. mit der Action
`ArtemSBulgakov/buildozer-action`) automatisiert laufen: Repository mit
`main.py` und `buildozer.spec` anlegen, Workflow einrichten, Push löst den
Build aus, die APK erscheint als Artefakt zum Download.

## Wichtiger Hinweis

Die App braucht Zugriff auf dasselbe lokale Netzwerk wie die Wallbox
(WLAN-zu-RS485-Gateway unter der eingestellten IP). Das Smartphone muss also
im gleichen WLAN sein wie das Gateway, damit die Verbindung funktioniert.
