# -*- coding: utf-8 -*-
import pandas as pd
from datetime import datetime
from collections import defaultdict

def _parse_dt(s):
    # Espera ISO o 'YYYY-MM-DD HH:MM'
    return datetime.fromisoformat(s.strip())

def calcular_importes(df_guardias: pd.DataFrame, calendario, tarifas, reglas: dict, anio: int, mes: int):
    detalle_rows = []
    for _, row in df_guardias.iterrows():
        inicio = _parse_dt(row["inicio_datetime"])
        fin = _parse_dt(row["fin_datetime"])
        municipio = row.get("municipio","") or ""
        tipo_guardia = row["tipo_guardia"]
        grado = row["grado"]

        tinfo = tarifas.obtener(grado, tipo_guardia)
        eur_base = tinfo["eur_hora_base"]
        mult_festivo = tinfo["mult_festivo"]
        mult_especial = tinfo["mult_festivo_especial"]

        bloques = calendario.fraccionar_por_hora(inicio, fin)
        for t0, t1 in bloques:
            tipo = calendario.tipo_en_fecha(t0, municipio)
            horas = (t1 - t0).total_seconds() / 3600.0
            if abs(horas - 1.0) > 1e-9:
                # Por consigna: contemplamos 1h exacta por bloque;
                # si hay bloques parciales, se pagan igualmente como 1h completa.
                horas = 1.0
            mult = 1.0
            if tipo == "especial":
                mult = mult_especial
            elif tipo == "festivo":
                mult = mult_festivo
            importe = round(eur_base * mult * horas, 4)  # 4 decimales
            detalle_rows.append({
                "inicio_bloque": t0.isoformat(sep=" "),
                "fin_bloque": t1.isoformat(sep=" "),
                "municipio": municipio,
                "grado": grado,
                "tipo_guardia": tipo_guardia,
                "tipo_dia": tipo,
                "horas": horas,
                "eur_hora_base": eur_base,
                "multiplicador": mult,
                "importe": importe
            })
    detalle = pd.DataFrame(detalle_rows)
    if detalle.empty:
        resumen = pd.DataFrame(columns=["grado","tipo_guardia","total_horas","total_importe"])
    else:
        resumen = (detalle
                    .assign(horas_real=1.0)  # cada bloque cuenta 1h
                    .groupby(["grado","tipo_guardia"], as_index=False)
                    .agg(total_horas=("horas_real","sum"),
                        total_importe=("importe","sum")))
    return detalle, resumen
