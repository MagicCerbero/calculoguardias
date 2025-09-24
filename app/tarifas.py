# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd

class CargadorTarifas:
    def __init__(self, path_xlsx: Path):
        self.df = pd.read_excel(path_xlsx, sheet_name="tarifas")
        esperadas = {"grado", "eur_hora_normal", "eur_hora_festivo", "eur_hora_especial"}
        faltan = esperadas - set(self.df.columns)
        if faltan:
            raise ValueError(f"Faltan columnas en tarifas: {faltan}")

    def obtener(self, grado: str) -> dict:
        m = self.df[self.df["grado"] == grado]
        if m.empty:
            raise ValueError(f"Tarifa no definida para grado={grado}")
        row = m.iloc[0]
        return {
            "normal": float(row["eur_hora_normal"]),
            "festivo": float(row["eur_hora_festivo"]),
            "especial": float(row["eur_hora_especial"]),
        }
