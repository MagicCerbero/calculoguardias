# -*- coding: utf-8 -*-
import pandas as pd
from datetime import datetime

def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(str(s).strip())

def calcular_importes(
    df_guardias: pd.DataFrame,
    calendario,
    tarifas,
    reglas: dict,
    anio: int,
    mes: int,
    irpf_percent: float = 0.0
):
    """
    Precios fijos por grado y tipo de día.
    - Trocea por horas.
    - Tipo de día por calendario (normal/festivo/especial).
    - Si la fila trae 'tipo_ini' y/o 'tipo_fin', sobrescribe el tipo para las horas
      que caen en esas fechas concretas (solo día de inicio/fin).
    - Devuelve:
        * detalle (bloques horarios)
        * resumen_guardias (una fila por guardia con IRPF aplicado)
    """
    detalle_rows = []
    resumen_rows = []

    has_ini = "tipo_ini" in df_guardias.columns
    has_fin = "tipo_fin" in df_guardias.columns

    irpf = float(irpf_percent or 0.0)
    if irpf < 0: irpf = 0.0
    if irpf > 100: irpf = 100.0

    for _, row in df_guardias.iterrows():
        inicio = _parse_dt(row["inicio_datetime"])
        fin = _parse_dt(row["fin_datetime"])
        municipio = row.get("municipio", "") or ""
        grado = row["grado"]
        observ = row.get("observaciones", "") or ""

        precios = tarifas.obtener(grado)  # {'normal': x, 'festivo': y, 'especial': z}

        overrides = {}
        if has_ini and str(row.get("tipo_ini","")).strip():
            overrides[inicio.date().isoformat()] = str(row["tipo_ini"]).strip()
        if has_fin and str(row.get("tipo_fin","")).strip():
            overrides[fin.date().isoformat()] = str(row["tipo_fin"]).strip()

        bruto_guardia = 0.0
        bloques = calendario.fraccionar_por_hora(inicio, fin)
        for t0, t1 in bloques:
            fecha_key = t0.date().isoformat()
            if fecha_key in overrides and overrides[fecha_key] in ("normal", "festivo", "especial"):
                tipo = overrides[fecha_key]
            else:
                tipo = calendario.tipo_en_fecha(t0, municipio)

            horas = 1.0
            eur_hora = precios.get(tipo, precios["normal"])
            importe = round(eur_hora * horas, 4)
            bruto_guardia += importe

            detalle_rows.append({
                "inicio_bloque": t0.isoformat(sep=" "),
                "fin_bloque": t1.isoformat(sep=" "),
                "municipio": municipio,
                "grado": grado,
                "tipo_dia": tipo,
                "horas": horas,
                "eur_hora": eur_hora,
                "importe": importe,
                "observaciones": observ
            })

        bruto_guardia = round(bruto_guardia, 4)
        neto_guardia = round(bruto_guardia * (1.0 - irpf / 100.0), 4)

        resumen_rows.append({
            "Rango": grado,
            "Fecha inicial + hora inicial": inicio.isoformat(sep=" "),
            "Fecha final + hora final": fin.isoformat(sep=" "),
            "Resultado": bruto_guardia,
            "% IRPF": irpf,
            "Total día": neto_guardia,
            "Municipio": municipio,
            "Observaciones": observ,
        })

    detalle = pd.DataFrame(detalle_rows)
    resumen_guardias = pd.DataFrame(resumen_rows, columns=[
        "Rango","Fecha inicial + hora inicial","Fecha final + hora final",
        "Resultado","% IRPF","Total día","Municipio","Observaciones"
    ])

    return detalle, resumen_guardias
