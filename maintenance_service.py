#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Services métier liés aux entretiens."""

from __future__ import annotations

from datetime import date

from date_utils import _add_months, _parse_iso_date
from database import _connect_db
from maintenance_repository import _recent_cost_for_type, get_last_entretien_for_type
from maintenance_type_repository import list_vehicle_types
from value_utils import _safe_int


def last_km_any(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("SELECT MAX(km) AS m FROM pleins WHERE vehicule_id=?", (int(vehicle_id),))
    m1 = _safe_int(cur.fetchone()["m"])
    cur.execute("SELECT MAX(km) AS m FROM entretiens WHERE vehicule_id=?", (int(vehicle_id),))
    m2 = _safe_int(cur.fetchone()["m"])
    conn.close()
    if m1 is None:
        return m2
    if m2 is None:
        return m1
    return max(m1, m2)


def estimate_maintenance_cost_next_months(vehicle_id: int, horizon_months: int = 6):
    """Estimation des coûts à prévoir sur les prochains mois.

    Pour chaque type cochée (enabled=1) :
    - Si period_months > 0 :
        on regarde la dernière date d'entretien de ce type.
        On calcule dans combien de mois il est dû.
        On compte les occurrences qui tombent dans la fenêtre [0, horizon_months].
    - On utilise le coût le plus récent connu pour ce type.
    """
    total = 0.0
    any_included = False

    for t in list_vehicle_types(vehicle_id):
        enabled = 1
        try:
            enabled = int(t["enabled"]) if t["enabled"] is not None else 1
        except Exception:
            enabled = 1
        if enabled != 1:
            continue

        pm = t["period_months"]
        try:
            pm = int(pm) if pm is not None else 0
        except Exception:
            pm = 0
        if pm <= 0:
            continue

        today = date.today()
        window_end = _add_months(today, horizon_months)
        last_date_iso, _last_km = get_last_entretien_for_type(vehicle_id, int(t["type_id"]))
        if not last_date_iso:
            due_date = today
        else:
            last_d = _parse_iso_date(last_date_iso)
            due_date = today if not last_d else _add_months(last_d, pm)

        if due_date > window_end:
            expected = 0
        else:
            next_due = today if due_date <= today else due_date
            expected = 0
            while next_due <= window_end:
                expected += 1
                next_due = _add_months(next_due, pm)

        if expected <= 0:
            continue

        cost = _recent_cost_for_type(vehicle_id, int(t["type_id"]))
        if cost is None or cost <= 0:
            continue

        total += cost * expected
        any_included = True

    return total if any_included else None
