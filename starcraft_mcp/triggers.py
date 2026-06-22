"""Bausteine fuer Trigger: Pydantic-Eingaben -> echte RichChk-Objekte.

Das ist das Herzstueck. Ein Trigger besteht aus *Bedingungen* (conditions) und
*Aktionen* (actions). Hier werden die tolerant getippten Eingaben von Claude in die
echten RichChk-Modelle uebersetzt, mit hilfreichen Fehlermeldungen.

Unterstuetzte CONDITION-Typen (Feld `type`):
  - always                 : immer wahr (Standard-Bedingung)
  - never                  : nie wahr
  - elapsed_time           : seit Spielstart sind N Sekunden vergangen
        Felder: seconds, comparator (AT_LEAST|AT_MOST|EXACTLY)
  - countdown_timer        : der Countdown-Timer vergleicht mit N Sekunden
        Felder: seconds, comparator
  - bring                  : Spieler hat N Einheiten an einer Location
        Felder: player, comparator, amount, unit, location
  - command                : Spieler kommandiert N Einheiten (ganze Karte)
        Felder: player, comparator, amount, unit
  - kill                   : Spieler hat N Einheiten eines Typs getoetet
        Felder: player, comparator, amount, unit
  - deaths                 : Spieler hat N Todesfaelle eines Einheitentyps
        Felder: player, comparator, amount, unit
  - accumulate             : Spieler hat N Ressourcen
        Felder: player, comparator, amount, resource (ORE|GAS|ORE_AND_GAS)
  - opponents              : Spieler hat N verbleibende Gegner
        Felder: player, comparator, amount

Unterstuetzte ACTION-Typen (Feld `type`):
  - display_text           : Text einblenden.  Felder: text
  - set_mission_objectives : Missionsziele setzen.  Felder: text
  - play_wav               : WAV abspielen.  Felder: wav_path (in-MPQ-Pfad), duration_ms?
  - create_unit            : Einheiten erzeugen.  Felder: player, amount, unit, location
  - kill_unit_at_location  : Einheiten toeten.  Felder: player, amount, unit, location
  - remove_unit_at_location: Einheiten entfernen. Felder: player, amount, unit, location
  - move_unit              : Einheiten bewegen.
        Felder: player, amount, unit, location (Quelle), destination (Ziel)
  - give_units             : Einheiten uebergeben.
        Felder: player (von), target_player (an), amount, unit, location
  - set_resources          : Ressourcen setzen.
        Felder: player, modifier (SET_TO|ADD|SUBTRACT), amount, resource
  - set_deaths             : Todeszaehler setzen.
        Felder: player, modifier, amount, unit
  - set_countdown_timer    : Countdown-Timer setzen.  Felder: seconds, modifier
  - pause_timer / unpause_timer : Countdown-Timer pausieren/fortsetzen
  - run_ai_script          : AI-Skript ausfuehren.  Felder: ai_script (4-Zeichen-Code)
  - run_ai_script_at_location : AI-Skript an Location.  Felder: ai_script, location
  - center_view            : Kamera zentrieren.  Felder: location
  - minimap_ping           : Minimap-Ping.  Felder: location
  - set_alliance_status    : Allianz setzen.
        Felder: player (Ziel-Gruppe), alliance_status (ENEMY|ALLY|ALLIED_VICTORY)
  - victory                : Mission gewonnen
  - defeat                 : Mission verloren

Hinweis "Transmission mit Portrait": RichChk hat (Stand dieser Version) kein
High-Level-Modell fuer die Transmission-/TalkingPortrait-Aktion. Baue einen
Funkspruch stattdessen aus `play_wav` + `display_text` (+ optional `center_view`)
zusammen. Siehe README.
"""

from __future__ import annotations

from typing import Callable, Optional

from pydantic import BaseModel, Field
from richchk.model.richchk.mrgn.rich_location import RichLocation
from richchk.model.richchk.str.rich_string import RichString
from richchk.model.richchk.trig.actions.center_view_action import CenterViewAction
from richchk.model.richchk.trig.actions.create_unit_action import CreateUnitAction
from richchk.model.richchk.trig.actions.defeat_action import DefeatAction
from richchk.model.richchk.trig.actions.display_text_message_action import (
    DisplayTextMessageAction,
)
from richchk.model.richchk.trig.actions.give_unit_action import GiveUnitAction
from richchk.model.richchk.trig.actions.kill_unit_at_location_action import (
    KillUnitAtLocationAction,
)
from richchk.model.richchk.trig.actions.minimap_ping_action import MinimapPingAction
from richchk.model.richchk.trig.actions.move_unit_action import MoveUnitAction
from richchk.model.richchk.trig.actions.pause_countdown_timer import (
    PauseCountdownTimerAction,
)
from richchk.model.richchk.trig.actions.play_wav_action import PlayWavAction
from richchk.model.richchk.trig.actions.remove_unit_at_location_action import (
    RemoveUnitAtLocationAction,
)
from richchk.model.richchk.trig.actions.run_ai_script_action import RunAiScriptAction
from richchk.model.richchk.trig.actions.run_ai_script_at_location_action import (
    RunAiScriptAtLocationAction,
)
from richchk.model.richchk.trig.actions.set_countdown_timer import (
    SetCountdownTimerAction,
)
from richchk.model.richchk.trig.actions.set_alliance_status_action import (
    SetAllianceStatusAction,
)
from richchk.model.richchk.trig.actions.set_deaths_action import SetDeathsAction
from richchk.model.richchk.trig.actions.set_mission_objectives_action import (
    SetMissionObjectivesAction,
)
from richchk.model.richchk.trig.actions.set_resources_action import SetResourcesAction
from richchk.model.richchk.trig.actions.unpause_countdown_timer import (
    UnpauseCountdownTimerAction,
)
from richchk.model.richchk.trig.actions.victory_action import VictoryAction
from richchk.model.richchk.trig.conditions.accumulate_resources_condition import (
    AccumulateResourcesCondition,
)
from richchk.model.richchk.trig.conditions.always_condition import AlwaysCondition
from richchk.model.richchk.trig.conditions.bring_condition import BringCondition
from richchk.model.richchk.trig.conditions.command_condition import CommandCondition
from richchk.model.richchk.trig.conditions.countdown_timer_condition import (
    CountdownTimerCondition,
)
from richchk.model.richchk.trig.conditions.deaths_condition import DeathsCondition
from richchk.model.richchk.trig.conditions.elapsed_time_condition import (
    ElapsedTimeCondition,
)
from richchk.model.richchk.trig.conditions.kill_condition import KillCondition
from richchk.model.richchk.trig.conditions.never_condition import NeverCondition
from richchk.model.richchk.trig.conditions.opponents_remaining_condition import (
    OpponentsRemainingCondition,
)
from richchk.model.richchk.trig.enums.ai_script import AiScript, KnownAiScript

from . import enums

# Locations werden ueber einen Resolver (Name -> RichLocation) aufgeloest, den der
# Aufrufer injiziert, weil die verfuegbaren Locations vom Workspace abhaengen.
LocationResolver = Callable[[str], RichLocation]


class Condition(BaseModel):
    """Eine einzelne Trigger-Bedingung. Pflichtfelder haengen von `type` ab."""

    type: str = Field(
        description="Bedingungstyp: always, never, elapsed_time, countdown_timer, "
        "bring, command, kill, deaths, accumulate, opponents."
    )
    player: Optional[str] = Field(
        default=None,
        description="Spieler/Gruppe, z.B. PLAYER_1, ALL_PLAYERS, FOES, CURRENT_PLAYER.",
    )
    comparator: str = Field(
        default="AT_LEAST",
        description="Vergleich: AT_LEAST, AT_MOST oder EXACTLY.",
    )
    amount: Optional[int] = Field(default=None, description="Menge/Anzahl/Ressourcen.")
    unit: Optional[str] = Field(
        default=None, description="Einheit, z.B. TERRAN_MARINE oder 'Terran Marine'."
    )
    location: Optional[str] = Field(
        default=None, description="Name einer existierenden Location."
    )
    seconds: Optional[int] = Field(default=None, description="Sekunden (Zeit-Typen).")
    resource: Optional[str] = Field(
        default=None, description="Ressource: ORE, GAS oder ORE_AND_GAS."
    )


class Action(BaseModel):
    """Eine einzelne Trigger-Aktion. Pflichtfelder haengen von `type` ab."""

    type: str = Field(
        description="Aktionstyp: display_text, set_mission_objectives, play_wav, "
        "create_unit, kill_unit_at_location, remove_unit_at_location, move_unit, "
        "give_units, set_resources, set_deaths, set_countdown_timer, pause_timer, "
        "unpause_timer, run_ai_script, run_ai_script_at_location, center_view, "
        "minimap_ping, set_alliance_status, victory, defeat."
    )
    text: Optional[str] = Field(default=None, description="Anzuzeigender Text.")
    wav_path: Optional[str] = Field(
        default=None,
        description="In-MPQ-Pfad der WAV (Rueckgabe von sc_embed_wav), z.B. "
        "'staredit\\\\wav\\\\funk1.wav'.",
    )
    duration_ms: Optional[int] = Field(
        default=None, description="Dauer der WAV in Millisekunden (optional)."
    )
    player: Optional[str] = Field(
        default=None, description="Betroffener Spieler/Gruppe (Quelle bei give_units)."
    )
    target_player: Optional[str] = Field(
        default=None, description="Zielspieler bei give_units."
    )
    amount: int = Field(
        default=1, description="Anzahl Einheiten / Menge. 0 bedeutet 'Alle'."
    )
    unit: Optional[str] = Field(default=None, description="Einheit, z.B. TERRAN_MARINE.")
    location: Optional[str] = Field(
        default=None, description="Name einer existierenden Location."
    )
    destination: Optional[str] = Field(
        default=None, description="Ziel-Location (bei move_unit)."
    )
    seconds: Optional[int] = Field(default=None, description="Sekunden (Timer).")
    modifier: str = Field(
        default="SET_TO", description="Mengen-Modifikator: SET_TO, ADD oder SUBTRACT."
    )
    resource: Optional[str] = Field(
        default=None, description="Ressource: ORE, GAS oder ORE_AND_GAS."
    )
    ai_script: Optional[str] = Field(
        default=None,
        description="AI-Skript: 4-Zeichen-Code (z.B. 'TMCx') oder bekannter Name "
        "(z.B. JUNKYARD_DOG).",
    )
    alliance_status: Optional[str] = Field(
        default=None, description="Allianz: ENEMY, ALLY oder ALLIED_VICTORY."
    )


def _require(value, field: str, action_or_cond_type: str):
    if value is None:
        raise ValueError(
            f"Feld '{field}' fehlt fuer Typ '{action_or_cond_type}'. "
            f"Bitte '{field}' angeben."
        )
    return value


def _resolve_ai_script(value: str) -> AiScript:
    """Bekannter Name (JUNKYARD_DOG) oder roher 4-Zeichen-Code."""
    key = value.strip()
    try:
        return KnownAiScript[key.upper()].value
    except KeyError:
        pass
    if len(key) == 4:
        return AiScript(key, key)
    known = ", ".join(sorted(k.name for k in KnownAiScript))
    raise ValueError(
        f"Unbekanntes AI-Skript {value!r}. Gib einen 4-Zeichen-Code an "
        f"(z.B. 'TMCx') oder einen bekannten Namen: {known}"
    )


def build_condition(cond: Condition, resolve_location: LocationResolver):
    """Uebersetze eine Condition-Eingabe in ein RichChk-Conditionobjekt."""
    t = cond.type.strip().lower()
    if t == "always":
        return AlwaysCondition()
    if t == "never":
        return NeverCondition()
    if t == "elapsed_time":
        return ElapsedTimeCondition(
            _seconds=_require(cond.seconds, "seconds", t),
            _comparator=enums.resolve_comparator(cond.comparator),
        )
    if t == "countdown_timer":
        return CountdownTimerCondition(
            _seconds=_require(cond.seconds, "seconds", t),
            _comparator=enums.resolve_comparator(cond.comparator),
        )
    if t == "bring":
        return BringCondition(
            _group=enums.resolve_player(_require(cond.player, "player", t)),
            _comparator=enums.resolve_comparator(cond.comparator),
            _amount=_require(cond.amount, "amount", t),
            _unit=enums.resolve_unit(_require(cond.unit, "unit", t)),
            _location=resolve_location(_require(cond.location, "location", t)),
        )
    if t == "command":
        return CommandCondition(
            _group=enums.resolve_player(_require(cond.player, "player", t)),
            _comparator=enums.resolve_comparator(cond.comparator),
            _amount=_require(cond.amount, "amount", t),
            _unit=enums.resolve_unit(_require(cond.unit, "unit", t)),
        )
    if t == "kill":
        return KillCondition(
            _group=enums.resolve_player(_require(cond.player, "player", t)),
            _comparator=enums.resolve_comparator(cond.comparator),
            _amount=_require(cond.amount, "amount", t),
            _unit=enums.resolve_unit(_require(cond.unit, "unit", t)),
        )
    if t == "deaths":
        return DeathsCondition(
            _group=enums.resolve_player(_require(cond.player, "player", t)),
            _comparator=enums.resolve_comparator(cond.comparator),
            _amount=_require(cond.amount, "amount", t),
            _unit=enums.resolve_unit(_require(cond.unit, "unit", t)),
        )
    if t == "accumulate":
        return AccumulateResourcesCondition(
            _group=enums.resolve_player(_require(cond.player, "player", t)),
            _comparator=enums.resolve_comparator(cond.comparator),
            _amount=_require(cond.amount, "amount", t),
            _resource=enums.resolve_resource(_require(cond.resource, "resource", t)),
        )
    if t == "opponents":
        return OpponentsRemainingCondition(
            _group=enums.resolve_player(_require(cond.player, "player", t)),
            _amount=_require(cond.amount, "amount", t),
            _comparator=enums.resolve_comparator(cond.comparator),
        )
    raise ValueError(
        f"Unbekannter Bedingungstyp: {cond.type!r}. Erlaubt: always, never, "
        "elapsed_time, countdown_timer, bring, command, kill, deaths, accumulate, "
        "opponents."
    )


def build_action(act: Action, resolve_location: LocationResolver):
    """Uebersetze eine Action-Eingabe in ein RichChk-Actionobjekt."""
    t = act.type.strip().lower()
    if t == "display_text":
        return DisplayTextMessageAction(RichString(_require(act.text, "text", t)))
    if t == "set_mission_objectives":
        return SetMissionObjectivesAction(RichString(_require(act.text, "text", t)))
    if t == "play_wav":
        return PlayWavAction(
            _path_to_wav_in_mpq=_require(act.wav_path, "wav_path", t),
            _duration_ms=act.duration_ms,
        )
    if t == "create_unit":
        return CreateUnitAction(
            enums.resolve_player(_require(act.player, "player", t)),
            act.amount,
            enums.resolve_unit(_require(act.unit, "unit", t)),
            resolve_location(_require(act.location, "location", t)),
        )
    if t == "kill_unit_at_location":
        return KillUnitAtLocationAction(
            enums.resolve_player(_require(act.player, "player", t)),
            act.amount,
            enums.resolve_unit(_require(act.unit, "unit", t)),
            resolve_location(_require(act.location, "location", t)),
        )
    if t == "remove_unit_at_location":
        return RemoveUnitAtLocationAction(
            enums.resolve_player(_require(act.player, "player", t)),
            act.amount,
            enums.resolve_unit(_require(act.unit, "unit", t)),
            resolve_location(_require(act.location, "location", t)),
        )
    if t == "move_unit":
        return MoveUnitAction(
            enums.resolve_unit(_require(act.unit, "unit", t)),
            enums.resolve_player(_require(act.player, "player", t)),
            act.amount,
            resolve_location(_require(act.location, "location", t)),
            resolve_location(_require(act.destination, "destination", t)),
        )
    if t == "give_units":
        return GiveUnitAction(
            enums.resolve_player(_require(act.player, "player", t)),
            enums.resolve_player(_require(act.target_player, "target_player", t)),
            act.amount,
            enums.resolve_unit(_require(act.unit, "unit", t)),
            resolve_location(_require(act.location, "location", t)),
        )
    if t == "set_resources":
        return SetResourcesAction(
            enums.resolve_player(_require(act.player, "player", t)),
            enums.resolve_modifier(act.modifier),
            _require(act.amount, "amount", t),
            enums.resolve_resource(_require(act.resource, "resource", t)),
        )
    if t == "set_deaths":
        return SetDeathsAction(
            enums.resolve_player(_require(act.player, "player", t)),
            enums.resolve_unit(_require(act.unit, "unit", t)),
            _require(act.amount, "amount", t),
            enums.resolve_modifier(act.modifier),
        )
    if t == "set_countdown_timer":
        return SetCountdownTimerAction(
            _require(act.seconds, "seconds", t),
            enums.resolve_modifier(act.modifier),
        )
    if t == "pause_timer":
        return PauseCountdownTimerAction()
    if t == "unpause_timer":
        return UnpauseCountdownTimerAction()
    if t == "run_ai_script":
        return RunAiScriptAction(_resolve_ai_script(_require(act.ai_script, "ai_script", t)))
    if t == "run_ai_script_at_location":
        return RunAiScriptAtLocationAction(
            _resolve_ai_script(_require(act.ai_script, "ai_script", t)),
            resolve_location(_require(act.location, "location", t)),
        )
    if t == "center_view":
        return CenterViewAction(resolve_location(_require(act.location, "location", t)))
    if t == "minimap_ping":
        return MinimapPingAction(resolve_location(_require(act.location, "location", t)))
    if t == "set_alliance_status":
        return SetAllianceStatusAction(
            enums.resolve_player(_require(act.player, "player", t)),
            enums.resolve_alliance(_require(act.alliance_status, "alliance_status", t)),
        )
    if t == "victory":
        return VictoryAction()
    if t == "defeat":
        return DefeatAction()
    raise ValueError(
        f"Unbekannter Aktionstyp: {act.type!r}. Siehe Tool-Beschreibung fuer die Liste."
    )


# --- Klartext-Zusammenfassung fuer describe_map / list_triggers ----------------


def summarize_condition(cond) -> str:
    name = type(cond).__name__.replace("Condition", "")
    parts = [name]
    for attr, label in (
        ("group", "player"),
        ("comparator", "cmp"),
        ("amount", "n"),
        ("unit", "unit"),
        ("seconds", "s"),
        ("resource", "res"),
        ("location", "loc"),
    ):
        if hasattr(cond, attr):
            val = getattr(cond, attr)
            parts.append(f"{label}={_pretty(val)}")
    return " ".join(parts)


def summarize_action(act) -> str:
    name = type(act).__name__.replace("Action", "")
    parts = [name]
    for attr, label in (
        ("group", "player"),
        ("from_group", "from"),
        ("to_group", "to"),
        ("amount", "n"),
        ("unit", "unit"),
        ("location", "loc"),
        ("destination_location", "dst"),
        ("message", "text"),
        ("path_to_wav_in_mpq", "wav"),
        ("seconds", "s"),
        ("resource", "res"),
        ("alliance_status", "ally"),
    ):
        if hasattr(act, attr):
            parts.append(f"{label}={_pretty(getattr(act, attr))}")
    return " ".join(parts)


def _pretty(val) -> str:
    if isinstance(val, RichString):
        return repr(val.value)
    if isinstance(val, RichLocation):
        return repr(val._custom_location_name.value or f"#{val.index}")
    if hasattr(val, "name"):
        try:
            return str(val.name)
        except Exception:
            pass
    return str(val)
