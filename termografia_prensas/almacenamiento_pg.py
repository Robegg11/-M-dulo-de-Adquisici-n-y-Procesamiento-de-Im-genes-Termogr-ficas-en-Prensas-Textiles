"""Capa de almacenamiento en PostgreSQL/TimescaleDB.

Ofrece los mismos métodos que Almacenamiento (SQLite). Si la extensión TimescaleDB
no está disponible, opera como PostgreSQL normal.
"""
import os
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values

from almacenamiento import estadisticas_roi


def _config():
    return dict(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE", "termografia"),
        user=os.getenv("PGUSER", "termo"),
        password=os.getenv("PGPASSWORD", "termo_pass"),
    )


class AlmacenamientoPG:
    def __init__(self):
        self.con = psycopg2.connect(**_config())
        self._crear_tablas()

    def _crear_tablas(self):
        with self.con, self.con.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS ciclos (
                id      BIGSERIAL PRIMARY KEY,
                prensa  TEXT NOT NULL,
                inicio  TIMESTAMPTZ NOT NULL,
                fin     TIMESTAMPTZ,
                presion REAL,
                notas   TEXT
            );
            CREATE TABLE IF NOT EXISTS lecturas (
                ciclo_id   BIGINT NOT NULL REFERENCES ciclos(id),
                ts         TIMESTAMPTZ NOT NULL,
                roi        TEXT NOT NULL,
                temp_media REAL,
                temp_max   REAL,
                temp_min   REAL,
                desviacion REAL
            );
            CREATE INDEX IF NOT EXISTS idx_lecturas_ciclo ON lecturas (ciclo_id, ts);
            ALTER TABLE ciclos ADD COLUMN IF NOT EXISTS frame_img TEXT;
            """)
        # Convierte lecturas en tabla de series de tiempo si TimescaleDB está disponible.
        try:
            with self.con, self.con.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
                cur.execute("SELECT create_hypertable('lecturas', 'ts', if_not_exists => TRUE);")
        except psycopg2.Error:
            self.con.rollback()

    @staticmethod
    def _ahora():
        return datetime.now(timezone.utc)

    def iniciar_ciclo(self, prensa="prensa_1", presion=None, notas=None, inicio=None):
        with self.con, self.con.cursor() as cur:
            cur.execute(
                "INSERT INTO ciclos (prensa, inicio, presion, notas) VALUES (%s,%s,%s,%s) RETURNING id",
                (prensa, inicio or self._ahora(), presion, notas))
            return cur.fetchone()[0]

    def cerrar_ciclo(self, ciclo_id, fin=None):
        with self.con, self.con.cursor() as cur:
            cur.execute("UPDATE ciclos SET fin=%s WHERE id=%s", (fin or self._ahora(), ciclo_id))

    def guardar_frame(self, ciclo_id, frame, ts=None):
        ts = ts or self._ahora()
        filas = [(ciclo_id, ts, roi, *vals) for roi, vals in estadisticas_roi(frame).items()]
        with self.con, self.con.cursor() as cur:
            execute_values(
                cur,
                "INSERT INTO lecturas (ciclo_id, ts, roi, temp_media, temp_max, temp_min, desviacion) VALUES %s",
                filas)

    def guardar_imagen(self, ciclo_id, frame):
        """Guarda (reemplaza) la imagen térmica de falso color del ciclo, para el dashboard."""
        from visualizacion import frame_a_data_uri
        with self.con, self.con.cursor() as cur:
            cur.execute("UPDATE ciclos SET frame_img=%s WHERE id=%s",
                        (frame_a_data_uri(frame), ciclo_id))

    def limpiar(self):
        """Borra todos los ciclos y lecturas (deja la base vacía)."""
        with self.con, self.con.cursor() as cur:
            cur.execute("TRUNCATE lecturas, ciclos RESTART IDENTITY")

    def lecturas_ciclo(self, ciclo_id):
        import pandas as pd
        return pd.read_sql_query(
            "SELECT ts, roi, temp_media, temp_max, temp_min, desviacion "
            "FROM lecturas WHERE ciclo_id=%(c)s ORDER BY ts",
            self.con, params={"c": ciclo_id})

    def cerrar(self):
        self.con.close()
