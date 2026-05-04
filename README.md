# Aivena Workforce

Optimización automatizada de turnos para retail mexicano post-reforma laboral 2027.

## El producto

Aivena Workforce toma los datos operativos de una tienda — demanda por hora, plantilla de empleados, salarios por rol — y genera un schedule semanal que cumple tres condiciones simultáneamente: tope estricto de 40 horas por empleado (mandatorio post-2027), cobertura del 100% de la demanda en horas pico, y cuantificación en pesos mexicanos del costo evitado frente a la programación actual.

La herramienta es completamente autónoma. Cualquier persona sube dos CSVs con datos de una tienda nueva y obtiene el análisis completo en menos de cinco segundos, sin intervención manual.

**→ App en vivo: [aivena-workforce.streamlit.app](https://aivena-workforce.streamlit.app)**

## Resultados

Validado con dos datasets sintéticos independientes que representan perfiles distintos de operación:

| | Tienda CDMX (80 emp, 9–21h) | Tienda Monterrey (110 emp, 10–22h) |
|---|---|---|
| Ahorro semanal | $24,450 MXN (14.9%) | $28,564 MXN (11.8%) |
| Empleados regularizados (>40h → ≤40h) | 68 de 80 | 77 de 110 |
| Cobertura de demanda | 100% | 100% |
| Horas extra eliminadas | 150 h | 81 h |
| Sobrestaffing eliminado | 500 personas-hora | 625 personas-hora |

Rango de ahorro defendible: **12–15%**, considerando un buffer del 5–8% para variabilidad de tráfico no modelada en v0. Ambos datasets superan el umbral del 8% requerido.

## Qué ve el usuario

La app tiene cinco pestañas:

**Resumen ejecutivo.** Brief generado por AI (Claude Sonnet 4.5) en español, estructurado para un CFO: diagnóstico, impacto cuantificado, riesgo regulatorio y próximo paso. Incluye checks de cumplimiento y comparación lado a lado baseline vs. optimizado.

**Análisis detallado.** Tres lentes sobre el mismo resultado: vista financiera (desglose del ahorro, tabla de sensibilidad a salarios), vista operativa (empleados afectados, horas por día, recomendaciones de rollout) y vista metodológica (supuestos del modelo, justificación del algoritmo, validación del rango de ahorro).

**Análisis visual.** Dos gráficas diseñadas para abrir una conversación de venta: demanda vs. staffing por hora (7 paneles, uno por día) y distribución de horas semanales por empleado con el tope legal 2027 marcado.

**Schedule semanal.** Heatmap interactivo del schedule generado (ajustable de 10 a 80 empleados), descarga en CSV (formato largo y matriz), y tabla resumen con horas y costo por empleado.

**Pregúntale a Aivena.** Chat conversacional que responde preguntas what-if sobre el análisis ("¿qué pasa si el SMG sube 12%?", "¿cuál es el riesgo legal específico?") usando Claude Sonnet 4.5 con el contexto completo del resultado inyectado.

## Decisiones técnicas

**Greedy en lugar de solver MIP.** El optimizador usa un algoritmo greedy en Python puro (sin OR-Tools ni dependencias de solver externo). Razones: latencia <1s frente a 30–90s de un MIP, deploy más robusto sin binarios precompilados, y el ahorro resultante ya supera el 8% mandatorio con margen. La sub-optimalidad estimada frente a CP-SAT es de ~5–10 puntos porcentuales, que no cambia la conclusión. Si un design partner requiere el óptimo verificable, la migración es interna — la interfaz (`run_comparison()`) no cambia.

**Streamlit + Plotly + Anthropic API.** La optimización de turnos es un problema determinista de cómputo, no un pipeline LLM. Usar un orquestador de agentes para esto añadiría complejidad sin payoff. La capa AI (brief ejecutivo + Q&A) sí es LLM, pero llama a Claude directamente desde Python. Resultado: una sola superficie técnica, un solo deploy, una sola URL.

**Datos sintéticos calibrados.** Curvas de tráfico alineadas a patrones observables del retail mexicano (picos lunch/after-work, sábado como día más fuerte). Salarios calibrados a SMG México 2026 + premium de retención retail. Sintéticos por diseño, no por falta de datos reales — evitan el riesgo de "esos números no son los míos" en una conversación de venta temprana.

**Baseline realista.** El baseline modela scheduling con dos turnos por día (AM/PM), buffer del 18% sobre demanda planeada, 85% de plantilla disponible (vacaciones/incapacidades/ausentismo), y overtime concentrado en el 20% más senior. El ahorro de 12–15% está dentro del rango documentado en literatura de workforce optimization (10–18%). Un baseline más caricaturesco produciría 30%+ de ahorro pero perdería credibilidad ante un CFO informado.

## Limitaciones de v0

El optimizador asume cross-training implícito (cualquier empleado cubre cualquier rol), demanda determinista (sin pronóstico estocástico), y no modela disponibilidad individual por empleado (turno preferido, estudios, antigüedad). Optimiza una tienda a la vez — cross-store re-allocation queda para v2. Cada una de estas limitaciones tiene un path claro de resolución que no cambia la arquitectura.

## Arquitectura

```
aivena-workforce/
├── app.py                    Streamlit app (entry point, 5 tabs)
├── requirements.txt          Dependencias Python
├── src/
│   ├── data_generator.py     Dataset sintético calibrado a retail MX
│   ├── baseline.py           Schedule baseline (simula Excel-based scheduling)
│   ├── optimizer.py          Algoritmo greedy con constraints duros
│   ├── comparator.py         Ejecuta baseline + optimizado + calcula deltas
│   └── ai_layer.py           Brief ejecutivo + Q&A what-if (Claude Sonnet 4.5)
├── data/
│   ├── demanda_demo.csv      Input de demanda (formato esperado)
│   └── empleados_demo.csv    Input de plantilla (formato esperado)
├── scripts/
│   └── export_demo_csv.py    Regenera CSVs de muestra
└── docs/
    ├── ASSUMPTIONS.md        Supuestos del modelo (completos)
    ├── METHODOLOGY.md        Cómo se calcula el ahorro (paso a paso)
    └── DEPLOY.md             Guía de deploy a Streamlit Cloud
```

## Cómo correr localmente

```bash
git clone https://github.com/juansgomezr/aivena-workforce.git
cd aivena-workforce
pip install -r requirements.txt
streamlit run app.py
```

Para habilitar la capa AI (brief + Q&A), configurar `ANTHROPIC_API_KEY` en `.streamlit/secrets.toml`. Sin la key, la app funciona completa con un brief boilerplate predefinido.

## Stack

Python · Streamlit · Plotly · Anthropic API (Claude Sonnet 4.5) · Pandas · NumPy
