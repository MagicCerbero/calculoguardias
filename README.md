# Guardias MIR — Cálculo de importe (MVP)

## Pasos rápidos
1) Rellena `config/tarifas.xlsx` (hoja `tarifas`):
   - columnas: grado, tipo_guardia, eur_hora_base, mult_festivo, mult_festivo_especial
2) Deja tus guardias en `input/guardias_mes.csv`:
   - columnas: inicio_datetime, fin_datetime, municipio, tipo_guardia, grado, observaciones
   - formato datetime ISO: `YYYY-MM-DD HH:MM`
3) Carga festivos en `data/`:
   - `festivos_es_andalucia_YYYY.csv`: nacionales + Andalucía (fecha,ambito,municipio,descripcion)
   - `festivos_locales_sevilla_YYYY.csv`: locales por municipio (TODOS los municipios de Sevilla)
   - Los CSV deben tener columna `fecha` en formato `YYYY-MM-DD`.
4) Ejecuta:
   ```bash
   python main.py --anio 2025 --mes 9 --entrada input/guardias_mes.csv --municipio_default "Sevilla"
   ```

## Notas
- "Festivo especial": 25/12 y 31/12, todo el día, ampliable en `config/reglas.yml`.
- Sin plus de noche. Resolución por bloques de **1 hora**. Importe con **4 decimales**.
- Prioridad: especial > festivo > normal.
