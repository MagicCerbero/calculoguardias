# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

def _cargar_csv_festivos(path: Path) -> pd.DataFrame:
    cols = ["fecha", "ambito", "municipio", "descripcion"]
    if not path.exists():
        return pd.DataFrame({c: pd.Series(dtype="object") for c in cols}).assign(
            fecha=pd.to_datetime(pd.Series([], dtype="datetime64[ns]"))
        )
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in cols}).assign(
            fecha=pd.to_datetime(pd.Series([], dtype="datetime64[ns]"))
        )
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["ambito"] = df["ambito"].astype(str).fillna("")
    df["municipio"] = df["municipio"].astype(str).fillna("")
    df["descripcion"] = df["descripcion"].astype(str).fillna("")
    return df

class CalendarioFestivos:
    def __init__(self, anio: int, reglas: dict, municipio_default: str = "Sevilla"):
        self.anio = anio
        self.reglas = reglas
        self.municipio_default = municipio_default
        base = Path("data")
        self.df_es = _cargar_csv_festivos(base / f"festivos_es_andalucia_{anio}.csv")
        self.df_loc = _cargar_csv_festivos(base / f"festivos_locales_sevilla_{anio}.csv")
        self._especiales = set(self.reglas.get("festivos_especiales", []))

    def tipo_en_fecha(self, dt: datetime, municipio: str) -> str:
        mmdd = dt.strftime("%m-%d")
        if mmdd in self._especiales:
            return "especial"
        if not self.df_es.empty and "fecha" in self.df_es.columns:
            if (self.df_es["fecha"].dt.date == dt.date()).any():
                return "festivo"
        muni = (municipio or self.municipio_default).strip().upper()
        if not self.df_loc.empty and "fecha" in self.df_loc.columns:
            mask_loc = (self.df_loc["fecha"].dt.date == dt.date()) & (self.df_loc["municipio"].str.upper() == muni)
            if mask_loc.any():
                return "festivo"
        return "normal"

    def fraccionar_por_hora(self, inicio: datetime, fin: datetime):
        bloques = []
        t = inicio
        while t < fin:
            corte = (t.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
            nxt = min(corte, fin)
            bloques.append((t, nxt))
            t = nxt
        return bloques
