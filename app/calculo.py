# -*- coding: utf-8 -*-
import pandas as pd
from datetime import datetime

def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.strip())

def calcular_importes(df_guardias: pd.DataFrame, calendario, tarifas, reglas: dict, anio: int, mes: int):
    detalle_rows = []
    for _, row in df_guardias.iterrows():
        inicio = _parse_dt(row["inicio_datetime"])
        fin = _parse_dt(row["fin_datetime"])
        municipio = row.get("municipio", "") or ""
        grado = row["grado"]

        precios = tarifas.obtener(grado)  # {'normal': x, 'festivo': y, 'especial': z}

        # Se trocea por horas y se aplica el precio de cada hora según tipo de día
        bloques = calendario.fraccionar_por_hora(inicio, fin)
        for t0, t1 in bloques:
            tipo = calendario.tipo_en_fecha(t0, municipio)  # 'normal' | 'festivo' | 'especial'
            horas = 1.0  # por consigna, cada bloque se computa como 1h completa
            eur_hora = precios.get(tipo, precios["normal"])
            importe = round(eur_hora * horas, 4)
            detalle_rows.append({
                "inicio_bloque": t0.isoformat(sep=" "),
                "fin_bloque": t1.isoformat(sep=" "),
                "municipio": municipio,
                "grado": grado,
                "tipo_dia": tipo,
                "horas": horas,
                "eur_hora": eur_hora,
                "importe": importe
            })

    detalle = pd.DataFrame(detalle_rows)
    if detalle.empty:
        resumen = pd.DataFrame(columns=["grado", "total_horas", "total_importe"])
    else:
        resumen = (detalle
                   .assign(horas_real=1.0)
                   .groupby(["grado"], as_index=False)
                   .agg(total_horas=("horas_real", "sum"),
                        total_importe=("importe", "sum")))
    return detalle, resumen
