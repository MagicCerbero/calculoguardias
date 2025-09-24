#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI o GUI: cálculo de importe por guardias (MIR).
- CLI: requiere --anio y --mes
- GUI: solo --gui
"""
import argparse
from pathlib import Path

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--gui', action='store_true', help='Abrir interfaz gráfica')
    p.add_argument("--anio", type=int, help="Año de cálculo (2025..2029)")
    p.add_argument("--mes", type=int, help="Mes 1..12")
    p.add_argument("--entrada", type=Path, default=Path("input/guardias_mes.csv"))
    p.add_argument("--municipio_default", type=str, default="Sevilla")
    p.add_argument("--salida_dir", type=Path, default=Path("output"))
    return p.parse_args()

def main():
    args = parse_args()
    if args.gui:
        from app.gui import launch
        launch()
        return

    if args.anio is None or args.mes is None:
        raise SystemExit("Error: en modo CLI son obligatorios --anio y --mes")

    from app.io_csv import leer_guardias, escribir_detalle, escribir_resumen
    from app.reglas import cargar_reglas
    from app.tarifas import CargadorTarifas
    from app.calendario import CalendarioFestivos
    from app.calculo import calcular_importes

    reglas = cargar_reglas(Path("config/reglas.yml"))
    tarifas = CargadorTarifas(Path("config/tarifas.xlsx"))
    cal = CalendarioFestivos(anio=args.anio, reglas=reglas, municipio_default=args.municipio_default)
    guardias = leer_guardias(args.entrada)
    detalle, resumen = calcular_importes(guardias, cal, tarifas, reglas, anio=args.anio, mes=args.mes)
    args.salida_dir.mkdir(parents=True, exist_ok=True)
    escribir_detalle(detalle, args.salida_dir / f"detalle_{args.anio:04d}-{args.mes:02d}.csv")
    escribir_resumen(resumen, args.salida_dir / f"resumen_{args.anio:04d}-{args.mes:02d}.csv")
    print("OK")

if __name__ == "__main__":
    main()
