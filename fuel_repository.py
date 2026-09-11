#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accès SQLite aux pleins."""

from __future__ import annotations

from database import _connect_db
from value_utils import _safe_float


def list_pleins(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT id, date_iso, km, litres, prix_litre, total, lieu
                   FROM pleins WHERE vehicule_id = ?
                   ORDER BY date_iso DESC, km DESC, id DESC""", (int(vehicle_id),))
    rows = cur.fetchall()
    conn.close()
    return rows


def list_pleins_lieux(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT lieu FROM pleins
                   WHERE vehicule_id = ? AND lieu IS NOT NULL AND TRIM(lieu) <> ''
                   ORDER BY lieu COLLATE NOCASE""", (int(vehicle_id),))
    rows = [r["lieu"] for r in cur.fetchall()]
    conn.close()
    return rows


def get_plein(plein_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT id, vehicule_id, date_iso, km, litres, prix_litre, total, lieu
                   FROM pleins WHERE id=?""", (int(plein_id),))
    r = cur.fetchone()
    conn.close()
    return r


def insert_plein(vehicle_id: int, date_iso: str, km: int, litres: float, prix_litre: float, total=None, lieu=None):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO pleins(vehicule_id, date_iso, km, litres, prix_litre, total, lieu)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (int(vehicle_id), date_iso, int(km), float(litres), float(prix_litre),
                 _safe_float(total), (lieu or "").strip() or None))
    conn.commit()
    conn.close()


def update_plein(plein_id: int, vehicle_id: int, date_iso: str, km: int, litres: float, prix_litre: float, total=None, lieu=None):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""UPDATE pleins
                   SET vehicule_id=?, date_iso=?, km=?, litres=?, prix_litre=?, total=?, lieu=?
                   WHERE id=?""",
                (int(vehicle_id), date_iso, int(km), float(litres), float(prix_litre),
                 _safe_float(total), (lieu or "").strip() or None, int(plein_id)))
    conn.commit()
    conn.close()


def delete_plein(plein_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM pleins WHERE id=?", (int(plein_id),))
    conn.commit()
    conn.close()
