#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nettoyage silencieux des photos véhicule orphelines."""

from __future__ import annotations

import os
import re

from app_paths import VEHICLE_PHOTOS_DIR
from vehicle_repository import list_vehicles


_GARAGE_PHOTO_RE = re.compile(r"^V\d+\.png$")


def cleanup_orphan_vehicle_photos():
    """Supprime les fichiers V<ID>.png non référencés par un véhicule."""
    try:
        rows = list_vehicles()
    except Exception:
        return

    referenced = set()
    for row in rows:
        try:
            photo_file = row["photo_file"]
        except Exception:
            continue
        if photo_file is None:
            continue
        name = str(photo_file).strip()
        if not name:
            continue
        name = os.path.basename(name.replace("\\", "/"))
        if name:
            referenced.add(name)

    try:
        if not os.path.isdir(VEHICLE_PHOTOS_DIR):
            return
    except Exception:
        return

    try:
        entries = list(os.scandir(VEHICLE_PHOTOS_DIR))
    except Exception:
        return

    for entry in entries:
        try:
            if entry.is_symlink():
                continue
            if not entry.is_file(follow_symlinks=False):
                continue
            if not _GARAGE_PHOTO_RE.fullmatch(entry.name):
                continue
            if entry.name in referenced:
                continue
            os.remove(entry.path)
        except Exception:
            continue
