#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Services métier liés aux entretiens."""

from __future__ import annotations

from datetime import date

from date_utils import _add_months, _month_diff, _parse_iso_date
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


def _format_days(days: int) -> str:
    return f"{int(days)} jour" if int(days) == 1 else f"{int(days)} jours"

def compute_reminder_status(vehicle_id: int, type_id: int, period_km, period_months):
    """Calcule (is_ok, color, label) pour un rappel.

    Règle: si km et/ou mois définis, 'dû' quand AU MOINS un seuil est dépassé.
    Si aucun entretien enregistré -> dû immédiatement.
    """
    current_km = last_km_any(vehicle_id) or 0
    last_date_iso, last_km = get_last_entretien_for_type(vehicle_id, type_id)

    pk = _safe_int(period_km)
    pm = _safe_int(period_months)

    if last_date_iso is None and last_km is None:
        parts = []
        if pk:
            parts.append(f"{pk} km")
        if pm:
            parts.append(f"{pm} mois")
        extra = " / ".join(parts) if parts else ""
        return (False, "red", f"À faire (jamais fait){(' — ' + extra) if extra else ''}")

    # écarts
    km_left = None
    if pk is not None and last_km is not None:
        km_left = pk - (int(current_km) - int(last_km))

    today = date.today()
    months_left = None
    due_date = None
    if pm is not None:
        d_last = _parse_iso_date(last_date_iso)
        if d_last:
            months_left = pm - _month_diff(d_last, today)
            due_date = _add_months(d_last, pm)


    overdue = False
    if km_left is not None and km_left <= 0:
        overdue = True
    if due_date is not None:
        if due_date < today:
            overdue = True
    elif months_left is not None and months_left <= 0:
        overdue = True

    if overdue:
        parts = []
        if km_left is not None and km_left <= 0:
            parts.append(f"{abs(km_left)} km")

        if due_date is not None and due_date < today:
            days_over = (today - due_date).days
            if 0 <= days_over < 31:
                if days_over == 0:
                    parts.append("aujourd’hui")
                else:
                    parts.append(_format_days(days_over))
            else:
                months_over = _month_diff(due_date, today)
                parts.append(f"{months_over} mois")
        elif months_left is not None and months_left <= 0:
            if due_date is not None:
                days_over = (today - due_date).days
                if 0 <= days_over < 31:
                    if days_over == 0:
                        parts.append("aujourd’hui")
                    else:
                        parts.append(_format_days(days_over))
                else:
                    parts.append(f"{abs(months_left)} mois")
            else:
                parts.append(f"{abs(months_left)} mois")

        suffix = " / ".join(parts) if parts else ""
        return (False, "red", f"À faire depuis {suffix}".strip())

    else:
        parts = []
        if km_left is not None:
            parts.append(f"{km_left} km")

        if months_left is not None:
            if due_date is not None:
                days_left = (due_date - today).days
                if days_left == 0:
                    parts.append("aujourd’hui")
                elif 0 < days_left <= 31:
                    parts.append(_format_days(days_left))
                else:
                    parts.append(f"{months_left} mois")
            else:
                parts.append(f"{months_left} mois")

        suffix = " / ".join(parts) if parts else ""
        if not suffix:
            return (True, "green", "OK")

        def upcoming_label() -> str:
            if suffix == "aujourd’hui":
                return "À faire aujourd’hui"
            return f"À faire dans {suffix}".strip()

        # Pré-alerte proche : une échéance dans 5 jours ou moins passe en orange.
        if due_date is not None:
            days_left_for_alert = (due_date - today).days
            if 0 <= days_left_for_alert <= 5:
                return (True, "orange", upcoming_label())

        # Pré-alerte longue : si la fréquence est > 1 mois, orange seulement
        # pendant le dernier mois avant l'échéance.
        try:
            pm_int = int(pm) if pm is not None else None
        except Exception:
            pm_int = None
        if pm_int is not None and pm_int > 1 and due_date is not None:
            days_left_for_alert = (due_date - today).days
            if 0 <= days_left_for_alert <= 31:
                return (True, "orange", upcoming_label())
        elif pm_int is not None and pm_int > 1 and months_left is not None and 0 < months_left <= 1:
            return (True, "orange", upcoming_label())

        return (True, "green", upcoming_label())


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
        type_name = (t["type_name"] or "").strip().lower()
        if type_name.startswith("contrôle") or type_name == "tension batterie":
            continue

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
