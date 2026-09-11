#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Initialisation et connexion SQLite de Garage."""

from __future__ import annotations

import os
import shutil
import sqlite3

from app_paths import DB_FILE, DB_TEMPLATE


def ensure_database() -> None:
    """Crée garage.db à partir du modèle si la base n'existe pas encore."""
    if not os.path.exists(DB_FILE):
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        if os.path.exists(DB_TEMPLATE):
            shutil.copy(DB_TEMPLATE, DB_FILE)
        else:
            # Secours pour les builds incomplets : _ensure_schema() créera
            # ensuite les tables minimales au démarrage de l'interface.
            sqlite3.connect(DB_FILE).close()


def _connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return {r["name"] for r in cur.fetchall()}


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,))
    return cur.fetchone() is not None


def _ensure_schema():
    """
    Crée les tables minimum si elles n'existent pas (ne détruit rien),
    puis applique des migrations légères idempotentes.
    """
    conn = _connect_db()
    cur = conn.cursor()

    # Tables minimales
    if not _table_exists(cur, "vehicules"):
        cur.execute("""
            CREATE TABLE vehicules(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT,
                marque TEXT,
                modele TEXT,
                motorisation TEXT,
                energie TEXT,
                annee INTEGER,
                immatriculation TEXT,
                photo_file TEXT
            )
        """)

    if not _table_exists(cur, "pleins"):
        cur.execute("""
            CREATE TABLE pleins(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicule_id INTEGER NOT NULL,
                date_iso TEXT,
                km INTEGER,
                litres REAL,
                prix_litre REAL,
                total REAL,
                lieu TEXT,
                FOREIGN KEY(vehicule_id) REFERENCES vehicules(id) ON DELETE CASCADE
            )
        """)

    if not _table_exists(cur, "entretien_types"):
        cur.execute("""
            CREATE TABLE entretien_types(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                owner_vehicle_id INTEGER,
                period_km INTEGER,
                period_months INTEGER,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY(owner_vehicle_id) REFERENCES vehicules(id) ON DELETE SET NULL
            )
        """)

    if not _table_exists(cur, "vehicule_entretien_types"):
        cur.execute("""
            CREATE TABLE vehicule_entretien_types(
                vehicule_id INTEGER NOT NULL,
                type_id INTEGER NOT NULL,
                enabled INTEGER DEFAULT 1,
                PRIMARY KEY(vehicule_id, type_id),
                FOREIGN KEY(vehicule_id) REFERENCES vehicules(id) ON DELETE CASCADE,
                FOREIGN KEY(type_id) REFERENCES entretien_types(id) ON DELETE CASCADE
            )
        """)

    if not _table_exists(cur, "entretiens"):
        cur.execute("""
            CREATE TABLE entretiens(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicule_id INTEGER NOT NULL,
                type_id INTEGER,
                intervention TEXT,
                date_iso TEXT,
                km INTEGER,
                cout REAL,
                details TEXT,
                kind TEXT,
                performed_by TEXT,
                battery_voltage REAL,
                FOREIGN KEY(vehicule_id) REFERENCES vehicules(id) ON DELETE CASCADE,
                FOREIGN KEY(type_id) REFERENCES entretien_types(id) ON DELETE SET NULL
            )
        """)

    # Migrations idempotentes (colonnes ajoutées si manquantes)
    try:
        cols_t = _columns(cur, "entretien_types")
        if "period_months" not in cols_t:
            cur.execute("ALTER TABLE entretien_types ADD COLUMN period_months INTEGER")
    except Exception:
        pass

    try:
        cols_e = _columns(cur, "entretiens")
        if "kind" not in cols_e:
            cur.execute("ALTER TABLE entretiens ADD COLUMN kind TEXT")
        if "performed_by" not in cols_e:
            cur.execute("ALTER TABLE entretiens ADD COLUMN performed_by TEXT")
        if "battery_voltage" not in cols_e:
            cur.execute("ALTER TABLE entretiens ADD COLUMN battery_voltage REAL")
    except Exception:
        pass

    try:
        cols_v = _columns(cur, "vehicules")
        if "photo_file" not in cols_v:
            cur.execute("ALTER TABLE vehicules ADD COLUMN photo_file TEXT")
    except Exception:
        pass

    try:
        cols_vtt = _columns(cur, "vehicule_entretien_types")
        if "enabled" not in cols_vtt:
            cur.execute("ALTER TABLE vehicule_entretien_types ADD COLUMN enabled INTEGER DEFAULT 1")
            cur.execute("UPDATE vehicule_entretien_types SET enabled=1 WHERE enabled IS NULL")
    except Exception:
        pass

    # preconisations constructeur (notes libres par véhicule)
    cur.execute("""CREATE TABLE IF NOT EXISTS preconisations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicule_id INTEGER NOT NULL,
            texte TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY(vehicule_id) REFERENCES vehicules(id) ON DELETE CASCADE
        )""")


    conn.commit()
    conn.close()
