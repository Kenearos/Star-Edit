"""StarCraft-Kampagnen-MCP-Server ("Missions-Baumeister").

Ein MCP-Server, der StarCraft-Brood-War-Karten (.scm/.scx) liest und schreibt,
damit Claude aus einer Kreativ-Vorlage echte, spielbare Missionsdateien baut.
Die Karten-Manipulation laeuft komplett ueber die Bibliothek RichChk.
"""

import os as _os

# RichChk loggt sonst sehr ausfuehrlich (INFO/WARNING) nach stderr. Wir setzen das
# Log-Level per RichChk-Config-Datei auf CRITICAL, BEVOR irgendein RichChk-Logger
# erzeugt wird (RichChk liest die Datei beim ersten get_logger). Das haelt die Ausgabe
# sauber; unsere Tools melden Fehler ohnehin als Exceptions.
_os.environ.setdefault(
    "io.sethmachine.richchk.config",
    _os.path.join(_os.path.dirname(__file__), "richchk_logging.yaml"),
)

__all__ = ["__version__"]

__version__ = "0.1.0"
