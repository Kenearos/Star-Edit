"""Flexible Resolver fuer RichChk-Enums.

Claude (und Menschen) sollen Einheiten, Spieler, Vergleiche usw. tolerant angeben
koennen: per Bezeichner ("TERRAN_MARINE"), per Anzeigename ("Terran Marine") oder per
Zahl ("0"). Diese Helfer uebersetzen solche Eingaben in die echten RichChk-Enum-Member
und werfen bei Fehlern eine *hilfreiche* Fehlermeldung mit Beispielen.
"""

from __future__ import annotations

from typing import Type, TypeVar

from richchk.model.richchk.forc.force_id import ForceId
from richchk.model.richchk.ownr.player_type import PlayerType
from richchk.model.richchk.richchk_enum import RichChkEnum
from richchk.model.richchk.side.player_race import PlayerRace
from richchk.model.richchk.trig.conditions.comparators.numeric_comparator import (
    NumericComparator,
)
from richchk.model.richchk.trig.enums.alliance_status import AllianceStatus
from richchk.model.richchk.trig.enums.amount_modifier import AmountModifier
from richchk.model.richchk.trig.enums.resource_type import ResourceType
from richchk.model.richchk.trig.enums.switch_state import SwitchState
from richchk.model.richchk.trig.player_id import PlayerId
from richchk.model.richchk.unis.unit_id import UnitId

_E = TypeVar("_E", bound=RichChkEnum)


def _identifier(member: RichChkEnum) -> str:
    """Der Python-Bezeichner eines Members, z.B. 'TERRAN_MARINE'."""
    return member._name_  # type: ignore[attr-defined]


def _build_index(enum_cls: Type[_E]) -> dict[str, _E]:
    index: dict[str, _E] = {}
    for member in enum_cls:  # type: ignore[attr-defined]
        index[_identifier(member).upper()] = member
        index[member.name.upper()] = member  # Anzeigename ("Terran Marine")
        index[str(member.id)] = member  # numerische ID
    return index


def _examples(enum_cls: Type[_E], limit: int = 20) -> str:
    names = sorted({_identifier(m) for m in enum_cls})  # type: ignore[attr-defined]
    shown = ", ".join(names[:limit])
    if len(names) > limit:
        shown += f", … ({len(names)} insgesamt)"
    return shown


def resolve(enum_cls: Type[_E], value: str | int, what: str) -> _E:
    """Loese eine tolerante Eingabe in ein RichChk-Enum-Member auf.

    Akzeptiert Bezeichner ('TERRAN_MARINE'), Anzeigename ('Terran Marine') oder ID (0).
    """
    index = _build_index(enum_cls)
    key = str(value).strip().upper()
    if key in index:
        return index[key]
    raise ValueError(
        f"Unbekannter Wert fuer {what}: {value!r}. "
        f"Verfuegbar (Bezeichner): {_examples(enum_cls)}"
    )


# --- Convenience-Wrapper mit sprechenden Namen --------------------------------


def resolve_unit(value: str | int) -> UnitId:
    return resolve(UnitId, value, "Einheit (unit)")


def resolve_player(value: str | int) -> PlayerId:
    return resolve(PlayerId, value, "Spieler/Gruppe (player)")


def resolve_comparator(value: str | int) -> NumericComparator:
    return resolve(NumericComparator, value, "Vergleich (comparator)")


def resolve_modifier(value: str | int) -> AmountModifier:
    return resolve(AmountModifier, value, "Mengen-Modifikator (modifier)")


def resolve_resource(value: str | int) -> ResourceType:
    return resolve(ResourceType, value, "Ressource (resource)")


def resolve_alliance(value: str | int) -> AllianceStatus:
    return resolve(AllianceStatus, value, "Allianz-Status (alliance_status)")


def resolve_switch_state(value: str | int) -> SwitchState:
    return resolve(SwitchState, value, "Schalter-Zustand (switch_state)")


def resolve_player_type(value: str | int) -> PlayerType:
    return resolve(PlayerType, value, "Spieler-Typ (type)")


def resolve_race(value: str | int) -> PlayerRace:
    return resolve(PlayerRace, value, "Rasse (race)")


def resolve_force(value: str | int) -> ForceId:
    return resolve(ForceId, value, "Force/Team (force)")


def list_identifiers(enum_cls: Type[_E]) -> list[str]:
    return sorted({_identifier(m) for m in enum_cls})  # type: ignore[attr-defined]
