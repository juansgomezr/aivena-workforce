# Metodología

Este documento explica el algoritmo paso a paso, las decisiones clave de diseño, y cómo se calcula la cifra de ahorro.

## Pipeline general

```
1. Cargar datos (demanda + empleados)
        ↓
2. Construir baseline (lo que hacen hoy con Excel)
        ↓
3. Construir optimizado (algoritmo greedy con constraints duros)
        ↓
4. Calcular delta (ahorro semanal, anual, % saving)
        ↓
5. Generar brief ejecutivo (Claude Sonnet 4.5)
```

## Construcción del baseline

El baseline modela el escenario más común en retail mexicano hoy: programación basada en promedios históricos, ejecutada en Excel, con dos turnos por día.

**Algoritmo**:

1. Para cada día, calcular promedio de demanda en turno AM (apertura → mediodía) y PM (mediodía → cierre).
2. Aplicar buffer del 18% sobre cada promedio: `staff_turno = ceil(avg × 1.18)`.
3. Asignar `staff_turno` empleados constantes durante todo el turno, rotándolos round-robin del pool disponible.
4. El pool disponible es el 85% de la plantilla (los demás están en vacaciones/incapacidades/capacitación).
5. Identificar gaps en hora pico (cuando demanda real > staff constante). Estos gaps se cubren con overtime, concentrado en el 20% más senior + supervisores (patrón observado en retail mexicano).
6. Calcular costo total: horas regulares + horas extra (multiplicador 2x).

**Resultado** (dataset demo):
- Costo: $163,780 MXN/semana
- 68 de 80 empleados >40h (infracción post-2027)
- 500 personas-hora de sobrestaffing en valles
- 35 personas-hora de gap en picos

## Construcción del optimizado

El optimizado usa un algoritmo greedy hour-by-hour con constraints duros y post-procesamiento para forzar turnos continuos.

**Algoritmo**:

```
Estado inicial:
  schedule = {} (vacío)
  weekly_hours[e] = 0 para cada empleado e
  daily_hours[e, día] = 0
  days_worked[e] = ∅
  shift_start[e, día] = None
  shift_end[e, día] = None

Para cada (día, hora) en orden cronológico:
    Demanda = N personas requeridas en este slot
    
    # Paso 1: Continuar turnos ya abiertos
    Para cada empleado que trabajó la hora anterior:
        Si elegible (no excede 40h, no excede 8h/día):
            Asignar: schedule[e, día, hora] = 1
            Actualizar contadores
    
    # Paso 2: Abrir turnos nuevos si hace falta cubrir
    Faltantes = N - asignados_en_paso_1
    Si faltantes > 0:
        Candidatos elegibles = empleados que cumplen TODOS los constraints duros
        Ordenar candidatos por (weekly_hours ASC, hourly_rate ASC)
            → distribuir carga + minimizar costo
        Asignar primeros [faltantes] candidatos
        
Post-procesamiento:
    Para cada (empleado, día) con horas asignadas:
        Si hay gaps dentro del turno (ej: 9-10 + 12-14):
            Rellenar gaps si no excede constraints
            Si no se puede rellenar, dejar como está (turno fragmentado)
```

**Constraints duros enforced**:

- `weekly_hours[e] ≤ 40` (ley)
- `daily_hours[e, día] ≤ 8` (ley)
- `len(days_worked[e]) ≤ 6` (1 día descanso obligatorio)
- Cobertura: `Σ_e schedule[e, día, hora] ≥ demanda[día, hora]`
- Continuidad: post-process intenta eliminar gaps mid-shift
- Turno mínimo: nuevos turnos requieren ≥4h disponibles (si no hay espacio, no se abre)

**Resultado** (dataset demo):
- Costo: $139,330 MXN/semana
- 0 empleados >40h
- 0 personas-hora de sobrestaffing
- 0 personas-hora de gap
- 100% cobertura

## Cálculo del ahorro

```
ahorro_semanal_mxn = costo_baseline - costo_optimizado
                   = $163,780 - $139,330
                   = $24,450 MXN/semana

ahorro_pct = ahorro_semanal_mxn / costo_baseline
           = $24,450 / $163,780
           = 14.93%

ahorro_anual_por_tienda = ahorro_semanal_mxn × 52
                        = $1,271,400 MXN/año

ahorro_anual_cadena_50_tiendas = ahorro_anual_por_tienda × 50
                                = $63,570,000 MXN/año
```

## Por qué greedy en vez de MIP

Un solver mixed-integer programming (CP-SAT de OR-Tools) garantiza el óptimo global. Lo descartamos para v0 por tres razones:

1. **Latencia**. Un MIP sobre 80 empleados × 7 días × 12 horas tarda 30-90 segundos por instancia. Greedy corre en <1 segundo. Para una demo y para Streamlit Cloud (límite Cloudflare 100s), greedy es preferible.

2. **Dependencias**. OR-Tools requiere binarios precompilados que pueden fallar en deploy según la plataforma. Greedy en pure Python tiene cero dependencias externas más allá de pandas/numpy.

3. **Margen de sub-optimalidad**. Un greedy bien diseñado captura ~85-92% del óptimo en problemas de scheduling de este tipo. Para demostrar ≥8% de ahorro, esto es más que suficiente. La diferencia entre greedy (14.9%) y MIP (~17-19% estimado) no cambia la conclusión.

**Roadmap**: si un design partner exige el óptimo verificable, el motor se sustituye por CP-SAT manteniendo la misma interfaz (`run_comparison()` en `comparator.py`). El cambio es internal, no afecta UI ni API externa.

## Sensibilidad — el rango 12-15%

La cifra de 14.9% asume demanda determinista. En la realidad, el tráfico de tienda tiene varianza. Para absorber esta varianza sin caer en sub-dotación, la operación añade un buffer del 5-8% en hora pico (sobrestaffing controlado). Esto reduce el ahorro a un rango de:

- **Buffer 0% (ideal)**: 14.9% ahorro (lo que la herramienta calcula con datos determinísticos)
- **Buffer 5%**: ~13.2% ahorro
- **Buffer 8%**: ~12.1% ahorro

Por eso el rango defendible en una conversación de venta es **12-15%**. Mencionarlo proactivamente proyecta sofisticación analítica y reduce el riesgo de objeciones.

## Generación del brief ejecutivo

El brief usa Claude Sonnet 4.5 (`claude-sonnet-4-5`) vía Anthropic API.

**Sistema**: el modelo recibe instrucciones de actuar como analista senior de Aivena, escribir en español de México, estructurar en 4 secciones (diagnóstico, impacto cuantificado, riesgo regulatorio, próximo paso), y nunca inventar cifras fuera del contexto inyectado.

**Contexto inyectado**: bloque pre-formateado con todas las métricas relevantes (costos baseline/optimizado, horas, empleados >40h, etc.).

**Fallback**: si la API key no está configurada o falla la llamada, el sistema devuelve un brief boilerplate construido con f-strings sobre las mismas métricas. La herramienta nunca falla por dependencia de API externa.

## Q&A what-if

El modo Q&A permite al usuario preguntar en lenguaje natural sobre el análisis. Claude tiene acceso al mismo contexto que el brief, más la conversación previa.

Las preguntas que el sistema responde con cálculo aproximado (sin re-correr el solver):

- "¿Qué pasa si el SMG sube X%?" → Multiplica costos proporcionalmente.
- "¿Y si la demanda crece X%?" → Calcula horas adicionales necesarias y las compara contra capacidad disponible (40h × 80 = 3,200h).
- "¿Cuánto ahorraría si solo lo aplico a 10 tiendas?" → Recalcula `ahorro_anual_chain` con num_stores nuevo.

Las preguntas que requieren re-correr el solver (cambiar tope a 38h, cambiar curva de demanda, etc.) son reconocidas explícitamente — Claude responde indicando la limitación y sugiriendo modificar parámetros en el sidebar.
