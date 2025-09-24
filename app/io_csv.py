# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd

def leer_guardias(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    # normaliza tipos
    return df

def escribir_detalle(df, path: Path):
    df.to_csv(path, index=False, encoding="utf-8")

def escribir_resumen(df, path: Path):
    df.to_csv(path, index=False, encoding="utf-8")
