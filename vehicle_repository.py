#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accès SQLite aux véhicules."""

from __future__ import annotations

from database import _connect_db


def list_vehicles():
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT id, nom, marque, modele, motorisation, energie, annee, immatriculation, photo_file
                   FROM vehicules
                   ORDER BY COALESCE(nom,'') COLLATE NOCASE, id""")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_vehicle(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT id, nom, marque, modele, motorisation, energie, annee, immatriculation, photo_file
                   FROM vehicules WHERE id = ?""", (int(vehicle_id),))
    r = cur.fetchone()
    conn.close()
    return r


def insert_vehicle(nom, marque, modele, motorisation, energie, annee, immatriculation, photo_file=None):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO vehicules(nom, marque, modele, motorisation, energie, annee, immatriculation, photo_file)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ((nom or "").strip() or None,
                 (marque or "").strip() or None,
                 (modele or "").strip() or None,
                 (motorisation or "").strip() or None,
                 (energie or "").strip() or None,
                 int(annee) if str(annee).strip() != "" else None,
                 (immatriculation or "").strip() or None,
                 (photo_file or "").strip() or None))
    vid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return vid


def update_vehicle(vehicle_id: int, nom, marque, modele, motorisation, energie, annee, immatriculation, photo_file=None):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""UPDATE vehicules
                   SET nom=?, marque=?, modele=?, motorisation=?, energie=?, annee=?, immatriculation=?, photo_file=?
                   WHERE id=?""",
                ((nom or "").strip() or None,
                 (marque or "").strip() or None,
                 (modele or "").strip() or None,
                 (motorisation or "").strip() or None,
                 (energie or "").strip() or None,
                 int(annee) if str(annee).strip() != "" else None,
                 (immatriculation or "").strip() or None,
                 (photo_file or "").strip() or None,
                 int(vehicle_id)))
    conn.commit()
    conn.close()


def delete_vehicle(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM vehicules WHERE id=?", (int(vehicle_id),))
    conn.commit()
    conn.close()
