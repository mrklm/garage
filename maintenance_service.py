#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Services métier liés aux entretiens."""

from __future__ import annotations

from database import _connect_db
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
