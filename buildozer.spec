[app]

title = Elvi Wallbox
package.name = elviwallbox
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 0.1

requirements = python3,kivy

orientation = portrait
fullscreen = 0

# Android-Berechtigungen: Internet/Netzwerk wird für die Socket-Verbindung
# zur Wallbox benötigt.
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE

# Ziel-API / min-API anpassen falls nötig
android.api = 34
android.minapi = 21
android.accept_sdk_license = True
p4a.branch = v2026.05.09

[buildozer]

log_level = 2
warn_on_root = 1
