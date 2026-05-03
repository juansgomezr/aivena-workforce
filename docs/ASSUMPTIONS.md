# Supuestos del modelo

Este documento enumera los supuestos que Aivena Workforce hace sobre la operación de una tienda retail mexicana. Todos son ajustables en código (`src/data_generator.py` y `src/baseline.py`); algunos serán configurables desde el UI en versiones futuras.

## Operación de la tienda

| Supuesto | Valor v0 | Justificación |
|---|---|---|
| Plantilla por tienda | 80 FTEs | Especificado en el reto técnico |
| Operación | Domingo a domingo | Especificado en el reto técnico |
| Horario lunes-sábado | 9:00 - 21:00 (12h) | Patrón estándar retail mexicano (Liverpool, Chedraui, Coppel) |
| Horario domingo | 10:00 - 20:00 (10h) | Patrón estándar retail mexicano |
| Total horas operativas/semana | 82 h | (12 × 6) + 10 |

## Mix de roles y salarios

| Rol | # empleados | Salario (MXN/h) | % plantilla |
|---|---|---|---|
| Cajero | 30 | $50 | 38% |
| Piso de venta | 25 | $55 | 31% |
| Inventario | 15 | $60 | 19% |
| Supervisor | 10 | $90 | 12% |

Salarios calibrados a SMG México 2026 (~$278.80/día zona libre frontera, ~$248.93/día general; equivalente a $31-35/h base) + premium retail típico de retención (+40-160% sobre SMG). Mix de roles refleja patrones públicos de tiendas departamentales y autoservicio.

## Curva de demanda

Factor de demanda (0-1) por hora-día calibrado a patrones observables:

- **Lunes-jueves**: pico medio en 13h (lunch ~0.7) y pico fuerte 18-19h (after-work ~0.85-0.88)
- **Viernes**: similar pero más fuerte en la tarde (18h ~0.95)
- **Sábado**: día más fuerte. Pico 13h (~1.0), tarde sostenida 17-18h (~0.85-0.9)
- **Domingo**: pico moderado 13h (~0.95), cierre temprano

Personas requeridas en piso = `round(45 × factor_demanda)`. Peak absoluto (sábado 13h) = 45 personas; valle típico (lunes 9h) ≈ 14 personas.

## Restricciones legales (post-reforma 2027)

| Restricción | Valor | Fuente |
|---|---|---|
| Jornada máxima semanal | 40 h | Reforma constitucional 2027 (transición 2027-2030) |
| Jornada máxima diaria | 8 h | Artículo 61 LFT (no cambió con reforma) |
| Día de descanso semanal | ≥1 día | Artículo 69 LFT |
| Multiplicador horas extra | 2x base | Artículo 67 LFT (primeras 9h extra/sem) |
| Turno mínimo | 4 h | Práctica de mercado (contratación) |

## Baseline (escenario "lo que hacen hoy")

| Parámetro | Valor | Justificación |
|---|---|---|
| Estructura | Dos turnos por día (AM/PM) | Patrón típico Excel-based scheduling |
| Buffer sobre staffing planeado | +18% | Sesgo conservador "no quedar corto" típico de managers de tienda |
| Pool efectivo | 85% de plantilla | Vacaciones, incapacidades, capacitación, ausentismo |
| Concentración de overtime | 20% de plantilla | Patrón observado: el OT se concentra (senior staff, supervisores), no se reparte |

## Optimizador (escenario "Aivena")

| Constraint | Valor | Tipo |
|---|---|---|
| Tope semanal | 40 h | Duro (cumplimiento legal) |
| Tope diario | 8 h | Duro |
| Turno mínimo | 4 h | Duro |
| Días trabajados máx/sem | 6 (≥1 día descanso) | Duro |
| Continuidad de turno | Sí | Duro (sin gaps mid-shift) |
| Cobertura | 100% de demanda | Duro |
| Función objetivo | Minimizar costo laboral total | Soft |

## Cálculo del costo

```
costo_total = Σ_empleado(horas_regulares × salario_h) + Σ_empleado(horas_extra × salario_h × 2.0)

donde:
  horas_regulares = min(40, horas_trabajadas)
  horas_extra     = max(0, horas_trabajadas - 40)
```

## Anualización

```
ahorro_anual_por_tienda = ahorro_semanal × 52 semanas
ahorro_anual_cadena     = ahorro_anual_por_tienda × num_tiendas
```

No descontamos por días festivos, vacaciones del empleado, ni cierre temporal por temporada — supuesto conservador de operación 52 semanas/año. Una versión refinada modelaría el calendario fiscal real del retailer.

## Lo que NO modelamos (v0)

- Cross-training real entre roles (asumimos que cualquier empleado cubre cualquier slot)
- Disponibilidad individual por empleado (estudios, turno preferido, antigüedad)
- Costos no laborales (rent, utilities, etc.) — solo se compara nómina
- Escalafones de carrera (un empleado siempre tiene el mismo salario semana a semana)
- Costo de oportunidad de la sub-dotación (lost revenue) — solo cuantificamos costo laboral evitado
- Variabilidad estocástica de demanda (asumimos determinista)
- Días feriados, eventos especiales (Buen Fin, El Buen Fin, días de pago Coppel)
