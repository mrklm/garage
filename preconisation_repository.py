#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accès SQLite aux préconisations constructeur."""

from __future__ import annotations

from datetime import datetime

from database import _connect_db


def list_preconisations(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, texte, created_at
           FROM preconisations
           WHERE vehicule_id = ?
           ORDER BY id DESC""",
        (int(vehicle_id),),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_preconisation(vehicle_id: int, texte: str):
    txt = (texte or "").strip()
    if not txt:
        raise ValueError("Texte vide.")
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO preconisations(vehicule_id, texte, created_at)
           VALUES (?, ?, ?)""",
        (int(vehicle_id), txt, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def update_preconisation(preco_id: int, texte: str):
    txt = (texte or "").strip()
    if not txt:
        raise ValueError("Texte vide.")
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE preconisations SET texte=? WHERE id=?",
        (txt, int(preco_id)),
    )
    conn.commit()
    conn.close()


def delete_preconisation(preco_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM preconisations WHERE id=?", (int(preco_id),))
    conn.commit()
    conn.close()
