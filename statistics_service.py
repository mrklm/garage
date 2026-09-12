#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calculs statistiques de Garage."""

from __future__ import annotations

from database import _connect_db
from value_utils import _safe_float, _safe_int


def conso_moy_l100(vehicle_id: int):
    """Conso moyenne (L/100) basée sur pleins: SUM(litres)/(max_km-min_km)*100. Nécessite >=2 pleins."""
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT MIN(km) AS kmin, MAX(km) AS kmax, SUM(litres) AS lsum, COUNT(*) AS n FROM pleins WHERE vehicule_id=?",
        (int(vehicle_id),),
    )
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    try:
        n = int(r["n"] or 0)
    except Exception:
        n = 0
    if n < 2:
        return None
    kmin = _safe_int(r["kmin"])
    kmax = _safe_int(r["kmax"])
    lsum = _safe_float(r["lsum"])
    if kmin is None or kmax is None or lsum is None:
        return None
    dist = kmax - kmin
    if dist <= 0:
        return None
    return (lsum / dist) * 100.0
