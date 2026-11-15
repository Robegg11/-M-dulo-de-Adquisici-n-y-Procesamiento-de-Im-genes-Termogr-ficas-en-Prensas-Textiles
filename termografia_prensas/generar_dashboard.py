"""Genera grafana/dashboards/termografia.json, el tablero de Grafana del sistema.

Uso: python generar_dashboard.py (Grafana recarga el archivo automáticamente en ~30 s).
Los umbrales de alerta se definen al inicio del archivo.
"""
import json

# Umbrales de alerta (°C) sobre la temperatura de la ROI central. Valores de ejemplo,
# a ajustar por proceso.
ROJO_MIN, ROJO_MAX = 150, 220        # fuera de este rango: nivel rojo
NARANJA_MIN, NARANJA_MAX = 160, 210  # fuera de este rango: nivel naranja; dentro: verde

DS = {"type": "postgres", "uid": "termografia-pg"}

# Ciclo seleccionado; el valor 0 ("Último ciclo en vivo") equivale al ciclo más reciente.
CID = "(SELECT CASE WHEN $ciclo = 0 THEN MAX(id) ELSE $ciclo END FROM ciclos)"
ULTIMO = f"ts = (SELECT MAX(ts) FROM lecturas WHERE ciclo_id = {CID})"


def target(sql, fmt="table"):
    return {"datasource": DS, "editorMode": "code", "format": fmt,
            "rawQuery": True, "rawSql": sql, "refId": "A"}


def stat(id_, titulo, sql, x, y, w, h, unit="celsius", color="blue", mapeos=None, fondo=False):
    defaults = {"unit": unit, "decimals": 1,
                "color": {"mode": "fixed", "fixedColor": color},
                "thresholds": {"mode": "absolute", "steps": [{"color": color, "value": None}]}}
    if mapeos:
        defaults["mappings"] = [{"type": "value", "options": mapeos}]
    return {"id": id_, "type": "stat", "title": titulo, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "targets": [target(sql)],
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "background" if fondo else "value",
                        "graphMode": "none", "textMode": "value", "justifyMode": "center"}}


def semaforo(id_, titulo, condicion, texto, color, y):
    """Un foco del semáforo: encendido (color y mensaje) si se cumple el nivel, apagado si no."""
    sql = ("WITH u AS (SELECT temp_media AS t FROM lecturas "
           f"WHERE ciclo_id = {CID} AND roi = 'centro' ORDER BY ts DESC LIMIT 1) "
           f"SELECT CASE WHEN {condicion} THEN 1 ELSE 0 END AS \"Estado\" FROM u")
    mapeos = {"1": {"text": texto, "color": color, "index": 0},
              "0": {"text": "—", "color": "#2b2d33", "index": 1}}
    return stat(id_, titulo, sql, 19, y, 5, 8, unit="none", mapeos=mapeos, fondo=True)


EN_ROJO = f"(t < $rojo_min OR t > $rojo_max)"
EN_RANGO = f"(t >= $rojo_min AND t <= $rojo_max)"
EN_VERDE = f"(t >= $naranja_min AND t <= $naranja_max AND {EN_RANGO})"
EN_NARANJA = f"({EN_RANGO} AND NOT {EN_VERDE})"

cabecera = ("<div style='text-align:center'>"
            "<h2 style='margin:0'>TecNM &nbsp;|&nbsp; Instituto Tecnológico Superior del Sur de Guanajuato (ITSUR)</h2>"
            "<h3 style='margin:4px 0 0 0'>Sistema de Monitoreo Termográfico de Prensas Textiles</h3>"
            "</div>")

imagen_html = ("<div style='display:flex;justify-content:center;align-items:center'>"
               "{{#each data}}<img src='{{{frame}}}' "
               "style='max-height:430px;max-width:100%;object-fit:contain' alt='Frame térmico'/>{{/each}}"
               "</div>")

trend_sql = (
    'SELECT EXTRACT(EPOCH FROM (l.ts - c.inicio))::float AS "Segundos", '
    + ", ".join(f"MAX(CASE WHEN l.roi = '{r}' THEN l.temp_media END) AS \"{r}\""
                for r in ["centro", "borde_izq", "borde_der", "borde_sup", "borde_inf"])
    + f" FROM lecturas l JOIN ciclos c ON c.id = l.ciclo_id WHERE l.ciclo_id = {CID} "
    "GROUP BY l.ts, c.inicio ORDER BY l.ts")

paneles = [
    {"id": 1, "type": "text", "title": "", "transparent": True,
     "gridPos": {"x": 0, "y": 0, "w": 24, "h": 3},
     "options": {"mode": "html", "content": cabecera}},

    stat(2, "Temperatura máxima",
         f"SELECT MAX(temp_max) AS \"Máxima\" FROM lecturas WHERE ciclo_id = {CID} AND {ULTIMO}",
         0, 3, 5, 8, color="orange"),
    stat(3, "Temperatura mínima",
         f"SELECT MIN(temp_min) AS \"Mínima\" FROM lecturas WHERE ciclo_id = {CID} AND {ULTIMO}",
         0, 11, 5, 8, color="blue"),
    stat(4, "Temperatura promedio",
         f"SELECT AVG(temp_media) AS \"Promedio\" FROM lecturas WHERE ciclo_id = {CID} AND {ULTIMO}",
         0, 19, 5, 8, color="green"),

    {"id": 5, "type": "marcusolsson-dynamictext-panel", "title": "Frame térmico del ciclo",
     "datasource": DS, "gridPos": {"x": 5, "y": 3, "w": 14, "h": 16},
     "targets": [target(f"SELECT frame_img AS frame FROM ciclos WHERE id = {CID}")],
     "options": {"renderMode": "allRows", "content": imagen_html,
                 "defaultContent": "<p style='text-align:center'>Sin imagen para este ciclo</p>",
                 "styles": "", "helpers": "", "afterRender": "", "wrap": True}},
    {"id": 6, "type": "trend", "title": "Temperatura en tiempo real (segundos desde el inicio del ciclo)",
     "datasource": DS, "gridPos": {"x": 5, "y": 19, "w": 14, "h": 8},
     "targets": [target(trend_sql)],
     "fieldConfig": {"defaults": {"unit": "celsius", "custom": {"lineWidth": 1, "showPoints": "never"}},
                     "overrides": [{"matcher": {"id": "byName", "options": "Segundos"},
                                    "properties": [{"id": "unit", "value": "s"}]}]},
     "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}},

    semaforo(7, "Alerta · Verde", EN_VERDE, "SEGURO: continuar con la impresión", "green", 3),
    semaforo(8, "Alerta · Naranja", EN_NARANJA, "REVISAR la prensa", "orange", 11),
    semaforo(9, "Alerta · Rojo", EN_ROJO, "PARAR la impresión y revisar el equipo", "red", 19),
]


def constante(nombre, valor):
    return {"name": nombre, "type": "constant", "hide": 2, "query": str(valor),
            "current": {"text": str(valor), "value": str(valor)},
            "options": [{"selected": True, "text": str(valor), "value": str(valor)}]}


dash = {
    "uid": "termografia-prensa",
    "title": "Sistema de Monitoreo Termográfico de Prensas Textiles",
    "tags": ["termografia", "residencia"],
    "timezone": "browser", "schemaVersion": 39, "version": 2,
    "refresh": "5s", "time": {"from": "now-6h", "to": "now"},
    "templating": {"list": [
        {"name": "ciclo", "label": "Ciclo", "type": "query", "datasource": DS,
         "query": ("SELECT '0' AS __value, 'Último ciclo (en vivo)' AS __text "
                   "UNION ALL (SELECT id::text, 'Ciclo ' || id FROM ciclos ORDER BY id DESC LIMIT 50)"),
         "refresh": 1, "sort": 0, "includeAll": False, "multi": False,
         "current": {"text": "Último ciclo (en vivo)", "value": "0"}},
        constante("rojo_min", ROJO_MIN), constante("rojo_max", ROJO_MAX),
        constante("naranja_min", NARANJA_MIN), constante("naranja_max", NARANJA_MAX),
    ]},
    "panels": paneles,
}

json.dump(dash, open("grafana/dashboards/termografia.json", "w"), ensure_ascii=False, indent=2)
print("grafana/dashboards/termografia.json generado")
