# -*- coding: utf-8 -*-
"""
Calendario de festivos para España/Andalucía y TODOS los municipios de Sevilla.
Tolera CSVs vacíos o no existentes y trata cualquier día sin coincidencia como "normal".
- Nacionales + Autonómicos: data/festivos_es_andalucia_YYYY.csv
- Locales (Sevilla):       data/festivos_locales_sevilla_YYYY.csv
"""

from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

def _cargar_csv_festivos(path: Path) -> pd.DataFrame:
    """
    Carga un CSV de festivos y asegura:
    - Columna 'fecha' en datetime (NaT permitido).
    - Columnas 'ambito', 'municipio', 'descripcion' presentes aunque el CSV esté vacío.
    Si el fichero no existe o está vacío → DataFrame válido pero vacío.
    """
    cols = ["fecha", "ambito", "municipio", "descripcion"]
    if not path.exists():
        return pd.DataFrame({c: pd.Series(dtype="object") for c in cols}).assign(
            fecha=pd.to_datetime(pd.Series([], dtype="datetime64[ns]"))
        )

    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        # Ante cualquier problema de lectura, devolvemos DF vacío "bien tipado"
        return pd.DataFrame({c: pd.Series(dtype="object") for c in cols}).assign(
            fecha=pd.to_datetime(pd.Series([], dtype="datetime64[ns]"))
        )

    # Garantizar columnas
    for c in cols:
        if c not in df.columns:
            df[c] = ""

    # Parsear fecha de forma robusta
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    # Normalizar texto
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

        # Conjuntos para consulta rápida
        # (fechas especiales van como MM-DD en reglas.yml)
        self._especiales = set(self.reglas.get("festivos_especiales", []))

    def tipo_en_fecha(self, dt: datetime, municipio: str) -> str:
        """Devuelve 'especial' | 'festivo' | 'normal' para la fecha dt (00:00–23:59)."""
        # 1) Festivo especial por MM-DD
        mmdd = dt.strftime("%m-%d")
        if mmdd in self._especiales:
            return "especial"

        # 2) Festivo nacional/autonómico (coincidencia por día)
        if not self.df_es.empty and "fecha" in self.df_es.columns:
            # Las filas con NaT en 'fecha' no coinciden
            mask_es = self.df_es["fecha"].dt.date == dt.date()
            if mask_es.any():
                return "festivo"

        # 3) Festivo local por municipio
        muni = (municipio or self.municipio_default).strip().upper()
        if not self.df_loc.empty and "fecha" in self.df_loc.columns:
            mask_loc = (self.df_loc["fecha"].dt.date == dt.date()) & (self.df_loc["municipio"].str.upper() == muni)
            if mask_loc.any():
                return "festivo"

        # 4) Normal
        return "normal"

    def fraccionar_por_hora(self, inicio: datetime, fin: datetime):
        """
        Divide el intervalo [inicio, fin) en bloques contiguos.
        Por consigna, cada bloque se paga como 1h completa aunque sea parcial.
        """
        bloques = []
        t = inicio
        while t < fin:
            # siguiente corte a la hora en punto o fin
            corte = (t.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
            nxt = min(corte, fin)
            bloques.append((t, nxt))
            t = nxt
        return bloques
