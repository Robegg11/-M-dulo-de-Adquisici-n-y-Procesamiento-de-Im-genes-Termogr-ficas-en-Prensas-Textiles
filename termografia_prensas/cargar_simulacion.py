"""Carga en la base de datos ciclos de prensado simulados.

  python cargar_simulacion.py            carga 6 ciclos históricos (últimas ~3 h)
  python cargar_simulacion.py --reset    vacía la base y carga los ciclos de nuevo
  python cargar_simulacion.py --vivo     simula ciclos en tiempo real (Ctrl+C para detener)

Los ciclos 2 y 5 tienen temperaturas fuera del rango ideal para activar las alertas
naranja y roja del tablero. El perfil de calentamiento es ilustrativo.
"""
import sys
import time
from datetime import datetime, timedelta, timezone

from simulador_termico import SimuladorMLX90640
from almacenamiento_pg import AlmacenamientoPG

FPS = 4
DURACION_S = 45
TEMPERATURAS = [185, 215, 178, 190, 142, 182]


def frame_con_calentamiento(sim, t):
    """Perfil de calentamiento ilustrativo: en los primeros 10 s la plancha sube de 55% a 100% de su diferencia con el ambiente."""
    factor = 0.55 + 0.45 * min(t / 10.0, 1.0)
    f = sim.generar_frame()
    return sim.temp_ambiente + (f - sim.temp_ambiente) * factor


def cargar_historico(bd):
    ahora = datetime.now(timezone.utc)
    for i, temp in enumerate(TEMPERATURAS):
        inicio = ahora - timedelta(hours=3) + timedelta(minutes=30 * i)
        zona_fria = (i == 3)
        sim = SimuladorMLX90640(temp_plancha=temp, zona_fria=zona_fria, semilla=100 + i)
        nota = "simulado con zona fría" if zona_fria else "simulado"
        ciclo = bd.iniciar_ciclo("prensa_1", presion=4.0, notas=nota, inicio=inicio)
        for k in range(FPS * DURACION_S):
            t = k / FPS
            frame = frame_con_calentamiento(sim, t)
            bd.guardar_frame(ciclo, frame, ts=inicio + timedelta(seconds=t))
        bd.guardar_imagen(ciclo, frame)
        bd.cerrar_ciclo(ciclo, fin=inicio + timedelta(seconds=DURACION_S))
        print(f"Ciclo {ciclo} cargado ({temp} °C, {nota})")


def simular_en_vivo(bd):
    i = 0
    while True:
        sim = SimuladorMLX90640(temp_plancha=180, zona_fria=(i % 4 == 3))
        ciclo = bd.iniciar_ciclo("prensa_1", presion=4.0, notas="simulado en vivo")
        print(f"Ciclo {ciclo} en curso ...")
        for k in range(FPS * DURACION_S):
            frame = frame_con_calentamiento(sim, k / FPS)
            bd.guardar_frame(ciclo, frame)
            if k % FPS == 0:
                bd.guardar_imagen(ciclo, frame)
            time.sleep(1 / FPS)
        bd.cerrar_ciclo(ciclo)
        i += 1
        time.sleep(10)


if __name__ == "__main__":
    bd = AlmacenamientoPG()
    try:
        if "--reset" in sys.argv:
            bd.limpiar()
            print("Base de datos vaciada.")
        if "--vivo" in sys.argv:
            simular_en_vivo(bd)
        else:
            cargar_historico(bd)
    except KeyboardInterrupt:
        print("\nDetenido.")
    finally:
        bd.cerrar()
