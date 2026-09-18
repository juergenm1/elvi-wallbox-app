"""
Behebt einen bekannten Bug in python-for-android: Beim Erstellen der
internen Build-Umgebung wird pip selbst aktualisiert ("pip install -U pip"),
was gelegentlich zu einer fehlerhaften Mischung aus zwei pip-Versionen
fuehrt (ImportError: cannot import name 'BuildDependencyInstallError').

Der offizielle Fix (kivy/python-for-android PR #3360) ist bislang in
keiner veroeffentlichten Version enthalten (weder auf "master" noch in
Release-Tags). Dieses Skript wendet denselben Fix lokal auf eine frisch
geklonte Kopie an, bevor Buildozer sie verwendet.

Usage: python patch_p4a.py <pfad-zu-python-for-android>
"""
import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python patch_p4a.py <pfad-zu-python-for-android>")
    sys.exit(1)

p4a_dir = Path(sys.argv[1])
build_py = p4a_dir / "pythonforandroid" / "build.py"

if not build_py.exists():
    print(f"FEHLER: {build_py} nicht gefunden.")
    sys.exit(1)

content = build_py.read_text()
original_content = content
changed = False

# 1) Venv beim Erstellen immer bereinigen (--clear), damit keine Reste
#    einer fehlgeschlagenen vorherigen pip-Installation liegen bleiben.
new_content, n = re.subn(
    r"venv',\s*'venv'\)",
    "venv', '--clear', 'venv')",
    content,
    count=1,
)
if n:
    content = new_content
    changed = True
    print("OK: '--clear' zur venv-Erstellung hinzugefuegt.")
else:
    print("WARNUNG: Stelle fuer '--clear' nicht gefunden (evtl. bereits gepatcht).")

# 2) Die riskante Selbst-Aktualisierung von pip innerhalb der venv entfernen.
#    Das ist die eigentliche Ursache des Bugs.
pattern = re.compile(
    r"\n[ \t]*info\(\s*['\"]Upgrade pip to latest version['\"]\s*\)\n"
    r"[ \t]*shprint\(\s*sh\.bash,\s*['\"]-c['\"],\s*\(\s*\n"
    r"[ \t]*[\"']source venv/bin/activate && pip install -U pip[\"']\s*\n"
    r"[ \t]*\),\s*_env=copy\.copy\(base_env\)\s*\)\n"
)
new_content, n = pattern.subn("\n", content)
if n:
    content = new_content
    changed = True
    print("OK: pip-Selbst-Upgrade-Schritt entfernt.")
else:
    print("WARNUNG: Stelle fuer pip-Upgrade-Entfernung nicht gefunden (evtl. bereits gepatcht).")

if changed and content != original_content:
    build_py.write_text(content)
    print(f"Patch erfolgreich auf {build_py} angewendet.")
else:
    print(
        "Kein Patch angewendet - entweder ist die Datei bereits gepatcht, "
        "oder sich die Struktur der Datei hat geaendert. Der Build laeuft "
        "mit der unveraenderten Datei weiter."
    )
