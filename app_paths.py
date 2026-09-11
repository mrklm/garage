#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Résolution des chemins de Garage."""

from __future__ import annotations

import os
import sys


def _app_dir() -> str:
    """Dossier de l'app (dev) ou de l'exécutable (PyInstaller)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _resource_path(*parts: str) -> str:
    """Chemin vers une ressource embarquée (PyInstaller) ou repo (dev)."""
    base = getattr(sys, "_MEIPASS", _app_dir())
    return os.path.join(base, *parts)


def resource_path(relative_path: str) -> str:
    """Alias rétro-compatible pour les anciens appels."""
    return _resource_path(relative_path)


def _user_data_dir(app_name: str = "Garage") -> str:
    """Dossier des données utilisateur (écriture fiable cross-platform)."""
    # macOS
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
        return os.path.join(base, app_name)

    # Linux (XDG)
    if sys.platform.startswith("linux"):
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        return os.path.join(base, app_name)

    # Windows
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, app_name)

    # fallback ultime
    return _app_dir()


# Où lire les ressources (assets, template db)
BASE_DIR = _app_dir()

# Où écrire les données utilisateur (DB réelle)
USER_DIR = _user_data_dir("Garage")

DB_FILE = os.path.join(USER_DIR, "garage.db")

# Base modèle embarquée (PyInstaller) ou présente en dev
DB_TEMPLATE = _resource_path("data", "garage_empty.db")

ASSETS_DIR = resource_path("assets")
VEHICLE_PHOTOS_DIR = os.path.join(USER_DIR, "vehicle_photos")  # photos utilisateurs (hors assets packagés)
