"""Arbeits-Session pro Basis-Karte.

MCP-Tool-Aufrufe sind einzeln, aber das Bauen einer Mission besteht aus vielen
Schritten (Location anlegen, mehrere Trigger, WAV einbetten, speichern). Diese Klasse
haelt den bearbeiteten RichChk-Zustand einer Karte im Speicher zusammen mit einer
Namens-Registry fuer Locations und den noch einzubettenden WAV-Dateien.

Workspaces leben prozessweit (Modul-Singleton-Dict), passend zum Streamable-HTTP-
Server, der ein einzelner Prozess ist.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field

from richchk.editor.richchk.rich_chk_editor import RichChkEditor
from richchk.editor.richchk.rich_mrgn_editor import RichMrgnEditor
from richchk.io.mpq.starcraft_mpq_io_helper import StarCraftMpqIoHelper
from richchk.io.richchk.query.chk_query_util import ChkQueryUtil
from richchk.model.richchk.mrgn.rich_location import RichLocation
from richchk.model.richchk.mrgn.rich_mrgn_section import RichMrgnSection
from richchk.model.richchk.rich_chk import RichChk
from richchk.model.richchk.str.rich_string import RichString
from richchk.model.richchk.trig.rich_trig_section import RichTrigSection

# Verzeichnis mit Basis-Karten, WAVs und fertigen Missionen (gemountetes Volume).
MAPS_DIR = os.environ.get("SC_MAPS_DIR", "/data/maps")

# Verzeichnis mit Terrain-Templates (vorgefertigte Basis-Karten). Aus einer Vorlage
# wird per new_from_template eine neue Arbeits-Basiskarte erzeugt. Standard: ein
# Unterordner des Karten-Verzeichnisses (liegt damit im selben gemounteten Volume).
TEMPLATES_DIR = os.environ.get(
    "SC_TEMPLATES_DIR", os.path.join(MAPS_DIR, "templates")
)

_MPQ_IO = None
_MPQ_LOCK = threading.Lock()


def get_mpq_io():
    """Lazy-Singleton fuer den (relativ teuren) StormLib-Loader."""
    global _MPQ_IO
    with _MPQ_LOCK:
        if _MPQ_IO is None:
            _MPQ_IO = StarCraftMpqIoHelper.create_mpq_io()
        return _MPQ_IO


def map_path(name: str) -> str:
    """Absoluter Pfad einer Karte/WAV im Karten-Verzeichnis (kein Ausbrechen)."""
    base = os.path.basename(name)
    return os.path.join(MAPS_DIR, base)


@dataclass
class Workspace:
    """Bearbeitbarer Zustand genau einer Basis-Karte."""

    base_name: str
    base_path: str
    chk: RichChk
    locations: dict[str, RichLocation] = field(default_factory=dict)
    # noch physisch einzubettende WAVs: (Disk-Pfad, In-MPQ-Pfad)
    pending_wavs: list[tuple[str, str]] = field(default_factory=list)

    # --- Sektion-Helfer -------------------------------------------------------

    def section(self, section_type):
        return ChkQueryUtil.find_only_rich_section_in_chk(section_type, self.chk)

    def replace(self, new_section) -> None:
        self.chk = RichChkEditor().replace_chk_section(new_section, self.chk)

    @property
    def mrgn(self) -> RichMrgnSection:
        return self.section(RichMrgnSection)

    @property
    def trig(self) -> RichTrigSection:
        return self.section(RichTrigSection)

    # --- Locations ------------------------------------------------------------

    def reload_location_registry(self) -> None:
        self.locations = {}
        for loc in self.mrgn.locations:
            name = loc._custom_location_name.value
            if name:
                self.locations[name] = loc

    def resolve_location(self, name: str) -> RichLocation:
        if name in self.locations:
            return self.locations[name]
        available = ", ".join(sorted(self.locations)) or "(keine)"
        raise ValueError(
            f"Location {name!r} existiert nicht. Verfuegbar: {available}. "
            f"Lege sie zuerst mit sc_create_location an."
        )

    def add_location(
        self,
        name: str,
        center_x: int,
        center_y: int,
        width: int,
        height: int,
    ) -> RichLocation:
        if name in self.locations:
            raise ValueError(
                f"Location {name!r} existiert bereits. Nutze sc_rename_location oder "
                f"einen anderen Namen."
            )
        half_w, half_h = max(1, width // 2), max(1, height // 2)
        loc = RichLocation(
            _left_x1=max(0, center_x - half_w),
            _top_y1=max(0, center_y - half_h),
            _right_x2=center_x + half_w,
            _bottom_y2=center_y + half_h,
            _custom_location_name=RichString(name),
        )
        new_mrgn, _ = RichMrgnEditor().add_locations([loc], self.mrgn)
        self.replace(new_mrgn)
        # Das allokierte Objekt (mit Index) aus der neuen Sektion ziehen.
        allocated = next(
            l for l in new_mrgn.locations if l._custom_location_name.value == name
        )
        self.locations[name] = allocated
        return allocated

    def rename_location(self, old_name: str, new_name: str) -> RichLocation:
        if old_name not in self.locations:
            available = ", ".join(sorted(self.locations)) or "(keine)"
            raise ValueError(
                f"Location {old_name!r} existiert nicht. Verfuegbar: {available}."
            )
        if new_name in self.locations:
            raise ValueError(f"Location {new_name!r} existiert bereits.")
        old = self.locations[old_name]
        renamed = RichLocation(
            _left_x1=old._left_x1,
            _top_y1=old._top_y1,
            _right_x2=old._right_x2,
            _bottom_y2=old._bottom_y2,
            _custom_location_name=RichString(new_name),
            _index=old._index,
            _low_elevation=old._low_elevation,
            _medium_elevation=old._medium_elevation,
            _high_elevation=old._high_elevation,
            _low_air=old._low_air,
            _medium_air=old._medium_air,
            _high_air=old._high_air,
        )
        new_locations = [
            renamed if l._index == old._index else l for l in self.mrgn.locations
        ]
        self.replace(RichMrgnSection(_locations=new_locations))
        del self.locations[old_name]
        self.locations[new_name] = renamed
        return renamed

    # --- Sounds ---------------------------------------------------------------

    def embed_wav(self, wav_disk_path: str) -> str:
        """Registriere eine WAV im WAV-Section (damit der String beim Encode bekannt
        ist) und merke die Datei zur physischen Einbettung beim Speichern vor.

        :return: der In-MPQ-Pfad, der in play_wav-Aktionen referenziert wird.
        """
        from richchk.editor.richchk.rich_wav_editor import RichWavEditor
        from richchk.model.richchk.wav.rich_wav_section import RichWavSection

        in_mpq = "staredit\\wav\\" + os.path.basename(wav_disk_path)
        wav_section = self.section(RichWavSection)
        self.replace(RichWavEditor().add_wav_files([in_mpq], wav_section))
        if not any(p[1] == in_mpq for p in self.pending_wavs):
            self.pending_wavs.append((wav_disk_path, in_mpq))
        return in_mpq

    # --- Speichern ------------------------------------------------------------

    def save_as(self, output_name: str, overwrite: bool) -> str:
        out_path = map_path(output_name)
        if not (out_path.lower().endswith(".scx") or out_path.lower().endswith(".scm")):
            out_path += ".scx"
        if os.path.exists(out_path) and not overwrite:
            raise FileExistsError(
                f"Datei existiert bereits: {os.path.basename(out_path)}. "
                f"Setze overwrite=true zum Ueberschreiben."
            )
        mpq_io = get_mpq_io()
        # CHK (inkl. aller Edits; die WAV-Eintraege wurden bei sc_embed_wav registriert)
        # in die neue MPQ schreiben.
        mpq_io.save_chk_to_mpq(
            self.chk, self.base_path, out_path, overwrite_existing=True
        )
        # Danach die physischen WAV-Dateien in die fertige MPQ kopieren.
        if self.pending_wavs:
            from richchk.model.mpq.stormlib.stormlib_archive_mode import (
                StormLibArchiveMode,
            )

            sw = mpq_io._stormlib_wrapper
            handle = sw.open_archive(out_path, StormLibArchiveMode.STORMLIB_WRITE_ONLY)
            try:
                for disk_path, in_mpq in self.pending_wavs:
                    sw.add_file(
                        handle,
                        infile=disk_path,
                        path_to_file_in_archive=in_mpq,
                        overwrite_existing=True,
                    )
                sw.compact_archive(handle)
            finally:
                sw.close_archive(handle)
        return out_path


# --- Workspace-Registry -------------------------------------------------------

_WORKSPACES: dict[str, Workspace] = {}
_WS_LOCK = threading.Lock()


def open_workspace(map_name: str, fresh: bool = False) -> Workspace:
    """Lade-oder-hole den Workspace einer Basis-Karte.

    :param map_name: Dateiname der Basis-Karte in MAPS_DIR.
    :param fresh: True erzwingt ein Neuladen von der Platte (verwirft Edits).
    """
    base = os.path.basename(map_name)
    with _WS_LOCK:
        if not fresh and base in _WORKSPACES:
            return _WORKSPACES[base]
    path = map_path(base)
    if not os.path.exists(path):
        available = ", ".join(list_maps()) or "(keine)"
        raise FileNotFoundError(
            f"Karte {base!r} nicht gefunden in {MAPS_DIR}. Verfuegbar: {available}."
        )
    chk = get_mpq_io().read_chk_from_mpq(path)
    ws = Workspace(base_name=base, base_path=path, chk=chk)
    ws.reload_location_registry()
    with _WS_LOCK:
        _WORKSPACES[base] = ws
    return ws


def discard_workspace(map_name: str) -> bool:
    base = os.path.basename(map_name)
    with _WS_LOCK:
        return _WORKSPACES.pop(base, None) is not None


def list_maps() -> list[str]:
    if not os.path.isdir(MAPS_DIR):
        return []
    return sorted(
        f
        for f in os.listdir(MAPS_DIR)
        if f.lower().endswith((".scx", ".scm"))
    )


# --- Terrain-Templates --------------------------------------------------------


def template_path(name: str) -> str:
    """Absoluter Pfad eines Templates (kein Ausbrechen aus TEMPLATES_DIR)."""
    return os.path.join(TEMPLATES_DIR, os.path.basename(name))


def list_templates() -> list[str]:
    if not os.path.isdir(TEMPLATES_DIR):
        return []
    return sorted(
        f
        for f in os.listdir(TEMPLATES_DIR)
        if f.lower().endswith((".scx", ".scm"))
    )


def read_terrain_meta(path: str) -> dict:
    """Liest Tileset + Groesse einer Karte (leichtgewichtig, ohne Workspace-Cache)."""
    from richchk.model.richchk.dim.rich_dim_section import RichDimSection
    from richchk.model.richchk.era.rich_era_section import RichEraSection

    chk = get_mpq_io().read_chk_from_mpq(path)
    dim = ChkQueryUtil.find_only_rich_section_in_chk(RichDimSection, chk)
    era = ChkQueryUtil.find_only_rich_section_in_chk(RichEraSection, chk)
    return {"tileset": era.tileset.name, "width": dim.width, "height": dim.height}


def new_from_template(template_name: str, output_name: str, overwrite: bool) -> str:
    """Kopiert ein Template als neue Arbeits-Basiskarte in MAPS_DIR.

    Reine Datei-Kopie: das Terrain (inkl. ISOM) bleibt unangetastet. Die Kopie wird
    danach wie jede Basis-Karte mit den sc_-Tools bearbeitet und per sc_save_map als
    Mission gespeichert.

    :return: absoluter Pfad der neuen Basis-Karte.
    """
    import shutil

    src = template_path(template_name)
    if not os.path.exists(src):
        available = ", ".join(list_templates()) or "(keine)"
        raise FileNotFoundError(
            f"Template {os.path.basename(template_name)!r} nicht gefunden in "
            f"{TEMPLATES_DIR}. Verfuegbar: {available}."
        )
    out_path = map_path(output_name)
    if not (out_path.lower().endswith(".scx") or out_path.lower().endswith(".scm")):
        # Endung des Templates uebernehmen, statt blind .scx anzuhaengen.
        out_path += os.path.splitext(src)[1]
    if os.path.exists(out_path) and not overwrite:
        raise FileExistsError(
            f"Datei existiert bereits: {os.path.basename(out_path)}. "
            f"Setze overwrite=true zum Ueberschreiben."
        )
    if os.path.abspath(src) == os.path.abspath(out_path):
        raise ValueError("Template und Ziel sind dieselbe Datei.")
    shutil.copyfile(src, out_path)
    # Falls eine gleichnamige Karte bereits im Speicher gecacht war: verwerfen,
    # damit der naechste Zugriff die frische Kopie laedt.
    discard_workspace(os.path.basename(out_path))
    return out_path
