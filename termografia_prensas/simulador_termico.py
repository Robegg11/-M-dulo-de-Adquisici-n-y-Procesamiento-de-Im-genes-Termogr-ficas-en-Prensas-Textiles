"""Simulador de frames térmicos con el formato del sensor MLX90640 (24x32 píxeles).

Permite desarrollar y probar el sistema sin el hardware físico; la clase puede sustituirse
por una que lea los datos reales de la cámara.
"""
import time
import numpy as np

COLUMNAS = 32
FILAS = 24


class SimuladorMLX90640:
    def __init__(self, temp_plancha=180.0, temp_ambiente=30.0,
                 ruido=0.4, zona_fria=False, semilla=None):
        """
        temp_plancha  : temperatura en el centro de la plancha (°C), rango real 150-220
        temp_ambiente : temperatura del entorno (°C)
        ruido         : desviación estándar del ruido por píxel (°C), imita el flicker
        zona_fria     : si es True, simula un defecto (esquina de la plancha más fría)
        """
        self.temp_plancha = temp_plancha
        self.temp_ambiente = temp_ambiente
        self.ruido = ruido
        self.zona_fria = zona_fria
        self.rng = np.random.default_rng(semilla)
        self.base = self._construir_base()

    def _construir_base(self):
        """Mapa de temperaturas sin ruido: plancha caliente al centro con gradiente hacia el borde y,
        si zona_fria es True, una esquina inferior derecha 25 °C más fría."""
        y, x = np.mgrid[0:FILAS, 0:COLUMNAS]
        cy, cx = (FILAS - 1) / 2, (COLUMNAS - 1) / 2

        dist = np.maximum(np.abs(y - cy) / 8.0, np.abs(x - cx) / 12.0)

        forma = np.clip(1.5 - dist, 0, 1)

        gradiente = 1.0 - 0.08 * np.clip(dist, 0, 1)

        mapa = self.temp_ambiente + (self.temp_plancha - self.temp_ambiente) * forma * gradiente

        if self.zona_fria:
            mascara = (y > 14) & (y < 20) & (x > 20) & (x < 27)
            mapa[mascara] -= 25.0
        return mapa

    def generar_frame(self):
        """Regresa una matriz de 24 filas x 32 columnas (°C), con ruido."""
        ruido = self.rng.normal(0, self.ruido, (FILAS, COLUMNAS))
        return self.base + ruido

    def generar_frame_plano(self):
        """Regresa los 768 valores en una lista, igual que la librería real de la cámara."""
        return self.generar_frame().flatten().tolist()

    def flujo(self, fps=4, cantidad=None):
        """Generador de frames a una frecuencia dada (la cámara real llega hasta 64 Hz)."""
        n = 0
        while cantidad is None or n < cantidad:
            yield self.generar_frame()
            n += 1
            time.sleep(1.0 / fps)


if __name__ == "__main__":
    sim = SimuladorMLX90640(temp_plancha=180, zona_fria=True, semilla=42)
    frame = sim.generar_frame()

    print(f"Tamaño del frame : {frame.shape} (filas x columnas)")
    print(f"Píxeles totales  : {frame.size}")
    print(f"Temp. mínima     : {frame.min():.1f} °C")
    print(f"Temp. máxima     : {frame.max():.1f} °C")
    print(f"Temp. centro     : {frame[12, 16]:.1f} °C")

    try:
        import matplotlib.pyplot as plt
        plt.imshow(frame, cmap="inferno", interpolation="nearest")
        plt.colorbar(label="°C")
        plt.title("Frame simulado 32x24 (con zona fría)")
        plt.savefig("preview_frame.png", dpi=100, bbox_inches="tight")
        plt.show()
        print("Vista previa guardada en preview_frame.png")
    except ImportError:
        print("matplotlib no está instalado; se omite la vista previa.")
