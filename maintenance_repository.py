#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accès SQLite aux entretiens."""

from __future__ import annotations

from database import _connect_db
from value_utils import _safe_float


def list_entretiens_full(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT e.id, e.date_iso, e.km,
                          COALESCE(t.nom, e.intervention) AS type_name,
                          e.kind, e.cout, e.performed_by, e.battery_voltage, e.details, e.type_id
                   FROM entretiens e
                   LEFT JOIN entretien_types t ON t.id = e.type_id
                   WHERE e.vehicule_id = ?
                   ORDER BY e.date_iso DESC, e.km DESC, e.id DESC""", (int(vehicle_id),))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_entretien(entretien_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT id, vehicule_id, type_id, intervention, date_iso, km, cout, details, kind, performed_by, battery_voltage
                   FROM entretiens WHERE id=?""", (int(entretien_id),))
    r = cur.fetchone()
    conn.close()
    return r


def insert_entretien(vehicle_id: int, date_iso: str, km: int, kind: str, type_id: int,
                    cout=None, performed_by=None, details=None, battery_voltage=None):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("SELECT nom FROM entretien_types WHERE id=?", (int(type_id),))
    rr = cur.fetchone()
    snapshot = rr["nom"] if rr else None
    cur.execute("""INSERT INTO entretiens(vehicule_id, type_id, intervention, date_iso, km, cout, details, kind, performed_by, battery_voltage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (int(vehicle_id), int(type_id), snapshot, date_iso, int(km), _safe_float(cout),
                 (details or "").strip() or None, (kind or "").strip() or None,
                 (performed_by or "").strip() or None, _safe_float(battery_voltage)))
    conn.commit()
    conn.close()


def update_entretien(entretien_id: int, vehicle_id: int, date_iso: str, km: int, kind: str, type_id: int,
                    cout=None, performed_by=None, details=None, battery_voltage=None):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("SELECT nom FROM entretien_types WHERE id=?", (int(type_id),))
    rr = cur.fetchone()
    snapshot = rr["nom"] if rr else None
    cur.execute("""UPDATE entretiens
                   SET vehicule_id=?, type_id=?, intervention=?, date_iso=?, km=?, cout=?, details=?, kind=?, performed_by=?, battery_voltage=?
                   WHERE id=?""",
                (int(vehicle_id), int(type_id), snapshot, date_iso, int(km), _safe_float(cout),
                 (details or "").strip() or None, (kind or "").strip() or None,
                 (performed_by or "").strip() or None, _safe_float(battery_voltage),
                 int(entretien_id)))
    conn.commit()
    conn.close()


def delete_entretien(entretien_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM entretiens WHERE id=?", (int(entretien_id),))
    conn.commit()
    conn.close()


def get_last_entretien_for_type(vehicle_id: int, type_id: int):
    """Retourne (date_iso, km) du dernier entretien pour ce type sur ce véhicule."""
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT date_iso, km
           FROM entretiens
           WHERE vehicule_id=? AND type_id=?
           ORDER BY date_iso DESC, km DESC, id DESC
           LIMIT 1""",
        (int(vehicle_id), int(type_id)),
    )
    r = cur.fetchone()
    conn.close()
    if not r:
        return (None, None)
    return (r["date_iso"], r["km"])


def get_last_battery_voltage(vehicle_id: int):
    """Retourne le dernier voltage batterie (float) renseigné dans les entretiens, ou None."""
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT battery_voltage
        FROM entretiens
        WHERE vehicule_id = ? AND battery_voltage IS NOT NULL
        ORDER BY date_iso DESC, km DESC, id DESC
        LIMIT 1
        """,
        (int(vehicle_id),),
    )
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    try:
        return float(r["battery_voltage"])
    except Exception:
        return None


def _recent_cost_for_type(vehicle_id: int, type_id: int):
    """Coût le plus récent (non NULL) pour un type d'entretien sur un véhicule."""
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT cout
        FROM entretiens
        WHERE vehicule_id = ? AND type_id = ? AND cout IS NOT NULL
        ORDER BY date_iso DESC, km DESC, id DESC
        LIMIT 1
        """,
        (int(vehicle_id), int(type_id)),
    )
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    try:
        return float(r["cout"])
    except Exception:
        return None
