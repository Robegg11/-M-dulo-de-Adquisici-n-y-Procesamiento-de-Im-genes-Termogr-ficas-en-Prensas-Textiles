"""Convierte un frame térmico (24x32, en °C) en una imagen de falso color.

Aplica interpolación bicúbica (32x24 -> 320x240) y un mapa de color con escala fija
(20-250 °C), de modo que cada color represente siempre la misma temperatura.
"""
import base64

import cv2
import numpy as np

from almacenamiento import ROIS

# Escala de color fija (°C) y factor de ampliación (32x24 -> 320x240).
T_MIN, T_MAX = 20.0, 250.0
ESCALA = 10


def frame_a_data_uri(frame, mostrar_rois=True):
    """Regresa la imagen como texto 'data:image/jpeg;base64,...' (cabe en una celda de la BD)."""
    norm = np.clip((frame - T_MIN) / (T_MAX - T_MIN), 0, 1)
    gris = (norm * 255).astype(np.uint8)
    grande = cv2.resize(gris, (32 * ESCALA, 24 * ESCALA), interpolation=cv2.INTER_CUBIC)
    color = cv2.applyColorMap(grande, cv2.COLORMAP_INFERNO)

    if mostrar_rois:
        for filas, cols in ROIS.values():
            p1 = (cols.start * ESCALA, filas.start * ESCALA)
            p2 = (cols.stop * ESCALA - 1, filas.stop * ESCALA - 1)
            cv2.rectangle(color, p1, p2, (255, 255, 255), 1)

    lienzo = np.full((240, 400, 3), 30, np.uint8)
    lienzo[:, :320] = color
    barra = np.linspace(255, 0, 240).astype(np.uint8).reshape(-1, 1)
    barra = cv2.applyColorMap(cv2.resize(barra, (20, 240), interpolation=cv2.INTER_NEAREST),
                              cv2.COLORMAP_INFERNO)
    lienzo[:, 335:355] = barra
    fuente = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(lienzo, f"{T_MAX:.0f}C", (358, 14), fuente, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(lienzo, f"{T_MIN:.0f}C", (358, 236), fuente, 0.4, (255, 255, 255), 1, cv2.LINE_AA)

    ok, buf = cv2.imencode(".jpg", lienzo, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode()
