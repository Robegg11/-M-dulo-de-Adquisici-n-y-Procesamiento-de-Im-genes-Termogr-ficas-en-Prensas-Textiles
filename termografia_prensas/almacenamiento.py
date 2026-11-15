"""Capa de almacenamiento del módulo termográfico en SQLite.

Define las regiones de interés (ROI) y sus estadísticas por frame. El acceso a la base
de datos está encapsulado en la clase Almacenamiento.
"""
import sqlite3
from datetime import datetime, timezone

import numpy as np

# Regiones de interés (filas, columnas) sobre el frame de 24x32. Valores de ejemplo,
# a ajustar con mediciones de campo.
ROIS = {
    "centro":     (slice(8, 16),  slice(10, 22)),
    "borde_izq":  (slice(8, 16),  slice(6, 10)),
    "borde_der":  (slice(8, 16),  slice(22, 26)),
    "borde_sup":  (slice(5, 8),   slice(10, 22)),
    "borde_inf":  (slice(16, 19), slice(10, 22)),
}


def estadisticas_roi(frame):
    """Regresa {nombre_roi: (media, maxima, minima, desviacion)} de un frame 24x32."""
    resultado = {}
    for nombre, (filas, cols) in ROIS.items():
        zona = frame[filas, cols]
        resultado[nombre] = (
            float(zona.mean()), float(zona.max()),
            float(zona.min()), float(zona.std()),
        )
    return resultado


class Almacenamiento:
    def __init__(self, ruta="termografia.db"):
        self.con = sqlite3.connect(ruta)
        self._crear_tablas()

    def _crear_tablas(self):
        self.con.executescript("""
        CREATE TABLE IF NOT EXISTS ciclos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            prensa        TEXT NOT NULL,
            inicio        TEXT NOT NULL,      -- fecha/hora ISO (UTC)
            fin           TEXT,
            presion       REAL,               -- se captura aparte (manual o sensor)
            notas         TEXT
        );
        CREATE TABLE IF NOT EXISTS lecturas (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ciclo_id      INTEGER NOT NULL REFERENCES ciclos(id),
            ts            TEXT NOT NULL,      -- fecha/hora ISO (UTC)
            roi           TEXT NOT NULL,
            temp_media    REAL,
            temp_max      REAL,
            temp_min      REAL,
            desviacion    REAL
        );
        CREATE INDEX IF NOT EXISTS idx_lecturas_ciclo ON lecturas(ciclo_id, ts);
        """)
        self.con.commit()

    @staticmethod
    def _ahora():
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    def iniciar_ciclo(self, prensa="prensa_1", presion=None, notas=None):
        cur = self.con.execute(
            "INSERT INTO ciclos (prensa, inicio, presion, notas) VALUES (?,?,?,?)",
            (prensa, self._ahora(), presion, notas))
        self.con.commit()
        return cur.lastrowid

    def cerrar_ciclo(self, ciclo_id):
        self.con.execute("UPDATE ciclos SET fin=? WHERE id=?", (self._ahora(), ciclo_id))
        self.con.commit()

    def guardar_frame(self, ciclo_id, frame):
        """Calcula las estadísticas por ROI y las guarda (una fila por ROI)."""
        ts = self._ahora()
        filas = [(ciclo_id, ts, roi, *vals) for roi, vals in estadisticas_roi(frame).items()]
        self.con.executemany(
            "INSERT INTO lecturas (ciclo_id, ts, roi, temp_media, temp_max, temp_min, desviacion)"
            " VALUES (?,?,?,?,?,?,?)", filas)
        self.con.commit()

    def lecturas_ciclo(self, ciclo_id):
        """Regresa un DataFrame de pandas con todas las lecturas de un ciclo."""
        import pandas as pd
        return pd.read_sql_query(
            "SELECT ts, roi, temp_media, temp_max, temp_min, desviacion "
            "FROM lecturas WHERE ciclo_id=? ORDER BY ts", self.con, params=(ciclo_id,))

    def cerrar(self):
        self.con.close()
