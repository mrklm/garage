#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Conversions de valeurs simples."""

from __future__ import annotations


def _safe_int(x):
    if x is None:
        return None
    try:
        return int(x)
    except Exception:
        return None


def _safe_float(x):
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None
