\
# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd

class CargadorTarifas:
    def __init__(self, path_xlsx: Path):
        self.df = pd.read_excel(path_xlsx, sheet_name="tarifas")
        # Validaciones mínimas
        esperadas = {"grado", "tipo_guardia", "eur_hora_base", "mult_festivo", "mult_festivo_especial"}
        faltan = esperadas - set(self.df.columns)
        if faltan:
            raise ValueError(f"Faltan columnas en tarifas: {faltan}")

    def obtener(self, grado: str, tipo_guardia: str) -> dict:
        m = self.df[(self.df["grado"]==grado) & (self.df["tipo_guardia"]==tipo_guardia)]
        if m.empty:
            raise ValueError(f"Tarifa no definida para grado={grado}, tipo_guardia={tipo_guardia}")
        row = m.iloc[0]
        return {
            "eur_hora_base": float(row["eur_hora_base"]),
            "mult_festivo": float(row["mult_festivo"]),
            "mult_festivo_especial": float(row["mult_festivo_especial"]),
        }
