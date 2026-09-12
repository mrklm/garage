#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accès SQLite aux types d'entretien."""

from __future__ import annotations

from database import _connect_db
from value_utils import _safe_int


def list_vehicle_types(vehicle_id: int):
    """Types d'entretien associés au véhicule + flag enabled (rappel affiché)."""
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT t.id AS type_id,
                          t.nom AS type_name,
                          t.period_km,
                          t.period_months,
                          COALESCE(vtt.enabled, 1) AS enabled
                   FROM vehicule_entretien_types vtt
                   JOIN entretien_types t ON t.id = vtt.type_id
                   WHERE vtt.vehicule_id = ?
                   ORDER BY CASE WHEN LOWER(t.nom) = 'tension batterie' THEN 0 ELSE 1 END, t.nom COLLATE NOCASE
                                      """, (vehicle_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def create_type_for_vehicle(vehicle_id: int, name: str, period_km=None, period_months=None):
    name = (name or "").strip()
    if not name:
        raise ValueError("Nom de type vide.")
    pk = _safe_int(period_km) if period_km not in ("", None) else None
    pm = _safe_int(period_months) if period_months not in ("", None) else None

    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO entretien_types(nom, owner_vehicle_id, period_km, period_months, is_active)
                   VALUES (?, ?, ?, ?, 1)""", (name, int(vehicle_id), pk, pm))
    type_id = int(cur.lastrowid)
    cur.execute("""INSERT INTO vehicule_entretien_types(vehicule_id, type_id, enabled)
                   VALUES (?, ?, 1)""", (int(vehicle_id), type_id))
    conn.commit()
    conn.close()
    return type_id


def update_type(type_id: int, name: str, period_km=None, period_months=None):
    name = (name or "").strip()
    if not name:
        raise ValueError("Nom de type vide.")
    pk = _safe_int(period_km) if period_km not in ("", None) else None
    pm = _safe_int(period_months) if period_months not in ("", None) else None

    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""UPDATE entretien_types SET nom=?, period_km=?, period_months=? WHERE id=?""",
                (name, pk, pm, int(type_id)))
    conn.commit()
    conn.close()


def delete_type_from_vehicle(vehicle_id: int, type_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM vehicule_entretien_types WHERE vehicule_id=? AND type_id=?",
                (int(vehicle_id), int(type_id)))
    cur.execute("SELECT COUNT(*) AS n FROM vehicule_entretien_types WHERE type_id=?", (int(type_id),))
    n_assign = int(cur.fetchone()["n"])
    cur.execute("SELECT COUNT(*) AS n FROM entretiens WHERE type_id=?", (int(type_id),))
    n_ref = int(cur.fetchone()["n"])
    if n_assign == 0 and n_ref == 0:
        cur.execute("DELETE FROM entretien_types WHERE id=?", (int(type_id),))
    conn.commit()
    conn.close()


def set_vehicle_type_enabled(vehicle_id: int, type_id: int, enabled: int):
    """Active/désactive l'affichage du rappel pour un type d'entretien sur un véhicule."""
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE vehicule_entretien_types SET enabled=? WHERE vehicule_id=? AND type_id=?",
        (1 if enabled else 0, int(vehicle_id), int(type_id)),
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT OR REPLACE INTO vehicule_entretien_types(vehicule_id, type_id, enabled) VALUES (?, ?, ?)",
            (int(vehicle_id), int(type_id), 1 if enabled else 0),
        )
    conn.commit()
    conn.close()
