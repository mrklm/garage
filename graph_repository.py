#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accès SQLite pour les données des graphiques."""

from __future__ import annotations

from database import _connect_db


def list_fill_consumption_points(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date_iso, km, litres
        FROM pleins
        WHERE vehicule_id = ? AND km IS NOT NULL AND litres IS NOT NULL
        ORDER BY km ASC, date_iso ASC, id ASC
        """,
        (int(vehicle_id),),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def list_fuel_price_points(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date_iso, prix_litre
        FROM pleins
        WHERE vehicule_id = ? AND date_iso IS NOT NULL AND prix_litre IS NOT NULL
        ORDER BY date_iso ASC, id ASC
        """,
        (int(vehicle_id),),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def list_maintenance_cost_points(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date_iso, cout, kind, intervention, details
        FROM entretiens
        WHERE vehicule_id = ? AND date_iso IS NOT NULL AND cout IS NOT NULL
        ORDER BY date_iso ASC, id ASC
        """,
        (int(vehicle_id),),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def list_maintenance_cost_by_month(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT SUBSTR(date_iso, 1, 7) AS ym, SUM(cout) AS total
        FROM entretiens
        WHERE vehicule_id = ? AND date_iso IS NOT NULL AND cout IS NOT NULL
        GROUP BY SUBSTR(date_iso, 1, 7)
        ORDER BY ym ASC
        """,
        (int(vehicle_id),),
    )
    rows = cur.fetchall()
    conn.close()
    return rows
