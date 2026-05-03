# Aivena Workforce

> Optimización automatizada de turnos para retail mexicano post-reforma laboral 2027.
> Reto técnico — Latin Leap CEO selection process.

## Qué es

Aivena Workforce toma cuatro inputs operativos de una tienda — tráfico/demanda por hora, plantilla, salarios — y devuelve un schedule semanal que (a) cumple el tope de 40h por empleado mandatorio post-2027, (b) cubre 100% de la demanda en picos, y (c) cuantifica en pesos mexicanos el costo evitado vs. la programación actual.

La herramienta no necesita un operador. Cualquier persona del equipo sube un CSV con datos de una tienda nueva y obtiene la salida en menos de cinco segundos.

**Ahorro validado en dataset demo: 14.9% semanal · $1.27M MXN/año por tienda · $63.5M MXN/año para cadena de 50 tiendas.**

## Demo en vivo

> _URL pendiente — se publica al deployar a Streamlit Cloud._

## Estructura del repo

```
aivena-workforce/
├── app.py                    Streamlit app (entry point)
├── requirements.txt          Dependencias Python
├── README.md                 Este archivo
├── .gitignore
├── .streamlit/
│   ├── config.toml           Tema visual
│   └── secrets.toml.example  Plantilla para ANTHROPIC_API_KEY
├── src/
│   ├── data_generator.py     Genera dataset sintético calibrado a retail MX
│   ├── baseline.py           Simula schedule actual ineficiente (Excel-based)
│   ├── optimizer.py          Algoritmo greedy con constraints duros
│   ├── comparator.py         Entry point del motor: baseline + optimizado + delta
│   └── ai_layer.py           Brief ejecutivo + Q&A what-if (Claude Sonnet 4.5)
├── scripts/
│   └── export_demo_csv.py    Genera CSVs de muestra (formato de input)
├── data/
│   ├── demanda_demo.csv      Input de demanda (formato esperado)
│   ├── empleados_demo.csv    Input de plantilla (formato esperado)
│   └── schedule_optimizado_demo.csv  Output de referencia
└── docs/
    ├── ASSUMPTIONS.md        Supuestos del modelo
    └── METHODOLOGY.md        Cómo se calcula el ahorro
```

## Cómo correr localmente

```bash
# 1. Clonar e instalar dependencias
git clone https://github.com/<TU-USUARIO>/aivena-workforce.git
cd aivena-workforce
pip install -r requirements.txt

# 2. (Opcional) Configurar API key para la capa AI
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Editar .streamlit/secrets.toml con tu ANTHROPIC_API_KEY

# 3. Correr la app
streamlit run app.py

# 4. (Alternativo) Validar el motor desde CLI sin Streamlit
python3 -m src.comparator
```

Sin API key, la app degrada a un brief boilerplate predefinido. La capa Q&A queda deshabilitada hasta que se configure la key.

## Deploy a Streamlit Cloud

```
1. Push este repo a GitHub (público o privado).
2. Ir a https://share.streamlit.io
3. New app → seleccionar repo, branch main, archivo app.py.
4. Advanced settings → Secrets:
       ANTHROPIC_API_KEY = "sk-ant-api03-..."
5. Deploy. URL queda viva en aivena-workforce.streamlit.app (o similar).
```

## Resultados del dataset demo

| Métrica | Baseline (Excel) | Optimizado (Aivena) | Delta |
|---|---|---|---|
| Costo laboral semanal | $163,780 MXN | $139,330 MXN | **−$24,450** |
| Empleados >40h | 68 / 80 | 0 / 80 | **−68** |
| Sobrestaffing en valles | 500 personas-hora | 0 | **−500 ph** |
| Sub-dotación en picos | 35 personas-hora | 0 | **−35 ph** |
| Cobertura de demanda | 95.5% | 100% | **+4.5 pp** |
| Horas extra | 150 h | 0 h | **−150 h** |

**Ahorro: 14.9% (rango defendible 12-15% considerando buffer de variabilidad de tráfico).**

## Decisiones técnicas — defendibles

**Greedy vs solver MIP.** Elegimos algoritmo greedy en pure Python (sin OR-Tools) por dos razones: latencia <1s vs. 30-90s de un MIP, mejor para demo y para Streamlit Cloud bajo el límite de 100s de Cloudflare; cero dependencias externas, deploy más robusto. Trade-off: ~5-10pp menos óptimo que CP-SAT. Roadmap Q3 2026: migrar a CP-SAT si un design partner lo justifica.

**Streamlit + plotly + Anthropic API.** No usamos Dify u otros workflow tools porque la optimización es un problema determinista de cómputo, no un pipeline LLM. La capa AI (brief + Q&A) sí es LLM, pero llama a Claude Sonnet 4.5 directamente desde Python — sin orquestadores intermedios. Resultado: una sola superficie técnica, un solo deploy, una sola URL para presentar.

**Datos sintéticos calibrados, no reales.** Curvas de tráfico calibradas a patrones observables públicamente del retail mexicano (picos lunch/after-work, sábado peak day). Salarios alineados a SMG México 2026 + retención retail. No usamos datos de un retailer específico para evitar el riesgo de "esos números no son los míos" en una conversación de venta.

**Baseline realista, no caricaturizado.** El baseline modela schedules con dos turnos por día (no constante 12h flat), buffer de 18%, y 85% de plantilla disponible (vacaciones/incapacidades). El ahorro resultante (14.9%) está dentro del rango creíble en literatura de workforce optimization (10-18%). Un baseline más caricaturesco generaría 30%+ de ahorro pero perdería credibilidad ante un CFO informado.

## Limitaciones reconocidas (v0)

1. **Sin diferenciación de roles.** El optimizador asume cross-training implícito: cualquier empleado cubre cualquier rol. Producción modelará constraints por rol (cajero ≠ supervisor).
2. **Sin demanda estocástica.** Asumimos demanda determinista. Producción incorporará pronóstico con intervalos de confianza y staffing robusto.
3. **Sin restricciones de empleado.** No modelamos disponibilidad individual (estudios, turno preferido, antigüedad). Producción acepta CSV con esos campos opcionales.
4. **Single-store.** El motor optimiza una tienda a la vez. Cross-store re-allocation queda para v2.

## Para la conversación de venta del lunes

La gráfica de **distribución de horas semanales por empleado** (tab "Análisis visual") es la herramienta principal. Muestra en una sola imagen el problema legal post-2027 (68 de 80 empleados en infracción) y la solución (todos entre 25-35h, ninguno cruza el tope). Esa es la gráfica de la que sale la decisión de pilotear.
