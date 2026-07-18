"""Precision of deterministic persona selection on the labeled golden set."""

from __future__ import annotations

from pathlib import Path

import yaml

from spindle_gtm.qualification.classify import classify_title
from spindle_gtm.qualification.loader import load_app_config
from spindle_gtm.qualification.schemas import Persona

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "golden_contacts.yaml"


def _contacts() -> list[dict[str, str]]:
    return list(yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))["contacts"])


def test_golden_set_coverage() -> None:
    contacts = _contacts()
    assert len(contacts) >= 20
    assert len({c["company"] for c in contacts}) >= 8


def test_persona_precision_is_high() -> None:
    personas = load_app_config().personas
    contacts = _contacts()
    predictions = correct = 0
    misses: list[str] = []
    for c in contacts:
        result = classify_title(c["title"], personas)
        if result.persona == Persona.UNKNOWN:
            continue  # abstention is not a wrong prediction
        predictions += 1
        if result.persona.value == c["expected"]:
            correct += 1
        else:
            misses.append(f"{c['title']}: got {result.persona.value}, want {c['expected']}")
    precision = correct / predictions
    assert precision >= 0.9, f"precision {precision:.2f}; misses={misses}"
    # The deterministic classifier should decide the large majority without a resolver.
    assert predictions >= 0.9 * len(contacts)


def test_visual_merchandising_is_excluded_but_product_merchandising_survives() -> None:
    # Visual/store merchandising is display/retail, not the product/buying champion.
    personas = load_app_config().personas
    for title in [
        "Visual Merchandising Manager",
        "Head of Visual Merchandising & Store Experience",
        "Vitrinista",
        "Auxiliar de Merchandising",
    ]:
        assert classify_title(title, personas).persona == Persona.EXCLUDED, title
    for title in [
        "Chief Merchandising Officer",
        "Buying and Merchandising Director",
        "SVP Merchandising, Planning and Licensing",
        "Head of Digital Merchandising",
    ]:
        assert classify_title(title, personas).persona == Persona.OPERATIONAL_CHAMPION, title
