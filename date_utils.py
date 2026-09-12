#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers de manipulation de dates."""

from __future__ import annotations

import calendar
from datetime import date, datetime


def _parse_iso_date(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        s = s.split("T")[0].split(" ")[0]
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None
    return None


def _month_diff(d1: date, d2: date) -> int:
    """Nombre de mois entiers entre d1 et d2 (d2 >= d1)."""
    if not d1 or not d2:
        return 0
    m = (d2.year - d1.year) * 12 + (d2.month - d1.month)
    if d2.day < d1.day:
        m -= 1
    return max(0, m)


def _add_months(d: date, months: int) -> date:
    """Ajoute N mois à une date (gestion des fins de mois)."""
    if months is None:
        return d
    # Convertit (année, mois) en index de mois absolu, ajoute, puis reconvertit
    m0 = (d.year * 12) + (d.month - 1) + int(months)
    y = m0 // 12
    m = (m0 % 12) + 1

    last_day = calendar.monthrange(y, m)[1]
    day = min(d.day, last_day)
    return date(y, m, day)
