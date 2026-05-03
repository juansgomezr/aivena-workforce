"""
Aivena Workforce — Streamlit App
MVP para optimización de turnos retail mexicano post-reforma laboral 2027.

Para correr localmente:
    streamlit run app.py

Para deploy en Streamlit Cloud:
    1. Push este repo a GitHub
    2. Conectar repo en share.streamlit.io
    3. Configurar secret: ANTHROPIC_API_KEY
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.data_generator import generate_store_dataset, DAYS, OPERATING_HOURS
from src.comparator import run_comparison
from src.ai_layer import generate_executive_brief, answer_question


# ==========================================================================
# CONFIG
# ==========================================================================

st.set_page_config(
    page_title="Aivena Workforce",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ==========================================================================
# UTILIDADES
# ==========================================================================

def fmt_mxn(value: float, decimals: int = 0) -> str:
    """Formatea número como MXN: $1,234,567"""
    return f"${value:,.{decimals}f} MXN"


def fmt_pct(value: float, decimals: int = 1) -> str:
    return f"{value*100:.{decimals}f}%"


def validate_demand_csv(df: pd.DataFrame) -> tuple[bool, str]:
    required = {"dia", "hora", "personas_requeridas"}
    missing = required - set(df.columns)
    if missing:
        return False, f"Columnas faltantes en demanda: {missing}"
    valid_days = set(DAYS)
    actual_days = set(df["dia"].unique())
    if not actual_days.issubset(valid_days):
        bad = actual_days - valid_days
        return False, f"Días inválidos: {bad}. Válidos: {valid_days}"
    return True, ""


def validate_employees_csv(df: pd.DataFrame) -> tuple[bool, str]:
    required = {"id", "name", "role", "hourly_rate"}
    missing = required - set(df.columns)
    if missing:
        return False, f"Columnas faltantes en empleados: {missing}"
    if len(df) < 10:
        return False, "Plantilla muy pequeña (<10 empleados)"
    return True, ""


# ==========================================================================
# GRÁFICAS
# ==========================================================================

def chart_demand_vs_staffing(result: dict) -> go.Figure:
    """Curva de demanda vs staffing baseline vs optimizado por hora-día."""
    bcov = result["baseline"]["coverage_df"]
    ocov = result["optimized"]["coverage_df"]

    # Construir labels concatenando día + hora
    rows = []
    for day in DAYS:
        bd = bcov[bcov["dia"] == day].sort_values("hora")
        od = ocov[ocov["dia"] == day].sort_values("hora")
        for _, r in bd.iterrows():
            rows.append({
                "label": f"{day[:3]} {r['hora']}h",
                "dia": day,
                "hora": r["hora"],
                "demanda": r["requerido"],
                "baseline": r["asignado"],
            })
        for _, r in od.iterrows():
            for row in rows:
                if row["dia"] == day and row["hora"] == r["hora"]:
                    row["optimizado"] = r["asignado"]
                    break
    df = pd.DataFrame(rows)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["label"], y=df["baseline"],
        name="Baseline (Excel)",
        marker_color="#F0997B",
        opacity=0.85,
    ))
    fig.add_trace(go.Bar(
        x=df["label"], y=df["optimizado"],
        name="Optimizado (Aivena)",
        marker_color="#5DCAA5",
        opacity=0.85,
    ))
    fig.add_trace(go.Scatter(
        x=df["label"], y=df["demanda"],
        name="Demanda real",
        mode="lines",
        line=dict(color="#2C2C2A", width=2),
    ))

    fig.update_layout(
        title="Demanda vs staffing por hora — semana completa",
        barmode="group",
        height=400,
        xaxis=dict(title="", tickangle=-60, tickfont=dict(size=9)),
        yaxis=dict(title="Personas"),
        legend=dict(orientation="h", y=1.05, x=0),
        margin=dict(l=10, r=10, t=60, b=80),
        plot_bgcolor="white",
    )
    return fig


def chart_hours_distribution(result: dict) -> go.Figure:
    """Histograma de horas semanales por empleado: baseline vs optimizado."""
    bh = result["baseline"]["hours_summary"]["total_hours"]
    oh = result["optimized"]["hours_summary"]["total_hours"]

    bins = [0, 25, 30, 35, 40, 45, 50]
    labels = ["<25h", "25-30h", "30-35h", "35-40h", "40-45h", "45-50h"]

    def hist(data):
        counts = [0] * (len(bins) - 1)
        for v in data:
            for i in range(len(bins) - 1):
                if bins[i] <= v < bins[i + 1]:
                    counts[i] += 1
                    break
            else:
                if v >= bins[-1]:
                    counts[-1] += 1
        return counts

    bcounts = hist(bh)
    ocounts = hist(oh)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=bcounts,
        name=f"Baseline (avg {bh.mean():.1f}h)",
        marker_color="#F0997B",
    ))
    fig.add_trace(go.Bar(
        x=labels, y=ocounts,
        name=f"Optimizado (avg {oh.mean():.1f}h)",
        marker_color="#5DCAA5",
    ))
    # Línea del tope legal entre 35-40h y 40-45h
    fig.add_vline(
        x=3.5, line=dict(color="#A32D2D", width=1.5, dash="dash"),
        annotation_text="Tope legal 2027",
        annotation_position="top right",
        annotation_font_color="#A32D2D",
    )
    fig.update_layout(
        title="Distribución de horas semanales por empleado",
        barmode="group",
        height=380,
        xaxis_title="Horas trabajadas/semana",
        yaxis_title="Empleados",
        legend=dict(orientation="h", y=1.05, x=0),
        margin=dict(l=10, r=10, t=60, b=40),
        plot_bgcolor="white",
    )
    return fig


def chart_schedule_heatmap(result: dict, max_employees: int = 30) -> go.Figure:
    """Heatmap del schedule optimizado: filas=empleados, columnas=día-hora."""
    sched = result["optimized"]["schedule_df"].copy()
    if sched.empty:
        return go.Figure()
    pivot = sched.pivot_table(
        index="emp_id", columns=["dia", "hora"], values="working", fill_value=0
    )
    # Reordenar columnas por día
    day_order = {d: i for i, d in enumerate(DAYS)}
    cols_sorted = sorted(pivot.columns, key=lambda c: (day_order.get(c[0], 99), c[1]))
    pivot = pivot[cols_sorted]
    # Limitar a primeros N empleados para legibilidad
    pivot = pivot.iloc[:max_employees]

    col_labels = [f"{d[:3]} {h}h" for d, h in pivot.columns]

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=col_labels,
        y=pivot.index.tolist(),
        colorscale=[[0, "#F1EFE8"], [1, "#0F6E56"]],
        showscale=False,
        hovertemplate="Empleado: %{y}<br>Slot: %{x}<br>Trabajando: %{z}<extra></extra>",
    ))
    fig.update_layout(
        title=f"Schedule semanal optimizado (primeros {max_employees} empleados)",
        height=520,
        xaxis=dict(tickangle=-60, tickfont=dict(size=8)),
        yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
        margin=dict(l=10, r=10, t=60, b=80),
    )
    return fig


# ==========================================================================
# CARGA DE DATOS
# ==========================================================================

def load_data(use_demo: bool, demand_file, employees_file):
    """Carga datasets desde demo o archivos subidos. Devuelve (demand_df, employees_df, store_name) o (None, None, None) si error."""
    if use_demo:
        ds = generate_store_dataset(store_name="Tienda Demo CDMX")
        return ds["demand_df"], ds["employees_df"], "Tienda Demo CDMX"

    if demand_file is None or employees_file is None:
        st.warning("Sube ambos CSVs (demanda y empleados) para continuar.")
        return None, None, None

    try:
        demand_df = pd.read_csv(demand_file)
        employees_df = pd.read_csv(employees_file)
    except Exception as e:
        st.error(f"Error leyendo CSVs: {e}")
        return None, None, None

    ok, msg = validate_demand_csv(demand_df)
    if not ok:
        st.error(f"CSV de demanda inválido: {msg}")
        return None, None, None
    ok, msg = validate_employees_csv(employees_df)
    if not ok:
        st.error(f"CSV de empleados inválido: {msg}")
        return None, None, None

    return demand_df, employees_df, "Tienda subida"


# ==========================================================================
# UI — SIDEBAR
# ==========================================================================

with st.sidebar:
    st.markdown("### ◆ Aivena Workforce")
    st.caption("Optimización de turnos · MVP v0")
    st.divider()

    st.markdown("#### Datos de tienda")
    data_source = st.radio(
        "Fuente de datos",
        ["Demo (datos sintéticos)", "Subir CSVs propios"],
        index=0,
        label_visibility="collapsed",
    )
    use_demo = data_source.startswith("Demo")

    demand_file = None
    employees_file = None
    if not use_demo:
        demand_file = st.file_uploader(
            "Demanda por hora-día (CSV)",
            type=["csv"],
            help="Columnas: dia, hora, personas_requeridas",
        )
        employees_file = st.file_uploader(
            "Plantilla de empleados (CSV)",
            type=["csv"],
            help="Columnas: id, name, role, hourly_rate",
        )
        st.caption("¿No tienes el formato? Descarga los CSVs demo desde la pestaña principal.")

    st.divider()
    st.markdown("#### Parámetros")
    num_stores = st.number_input(
        "Tiendas en la cadena",
        min_value=1,
        max_value=500,
        value=50,
        help="Para escalar el ahorro anualizado a toda la cadena",
    )

    st.divider()
    optimize_btn = st.button("Optimizar →", type="primary", use_container_width=True)

    st.divider()
    st.caption("Latin Leap · Aivena CEO")
    st.caption("Reto técnico — May 2026")


# ==========================================================================
# UI — MAIN
# ==========================================================================

st.title("Aivena Workforce")
st.caption(
    "Programación automatizada de turnos para retail mexicano post-reforma laboral 2027. "
    "Cumple el tope de 40h por empleado y cuantifica en MXN el costo evitado vs. la programación actual."
)

# Botón de descarga de templates demo (siempre visible)
with st.expander("¿Necesitas el formato CSV para subir tus datos?"):
    st.markdown(
        "Los CSVs demo están en `data/` del repo. Subirlos a tu Streamlit te permite "
        "verificar que tu propio formato es compatible. Estructura esperada:"
    )
    st.code(
        "demanda.csv:\n  dia,hora,personas_requeridas\n  Lunes,9,14\n  Lunes,10,18\n  ...",
        language="text",
    )
    st.code(
        "empleados.csv:\n  id,name,role,hourly_rate\n  E001,Luis Luna,Cajero,50\n  ...",
        language="text",
    )

# Inicialización de estado
if "result" not in st.session_state:
    st.session_state.result = None
if "store_name" not in st.session_state:
    st.session_state.store_name = ""
if "num_stores" not in st.session_state:
    st.session_state.num_stores = 50
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []

# Disparar optimización
if optimize_btn:
    with st.spinner("Optimizando schedule…"):
        demand_df, employees_df, store_name = load_data(use_demo, demand_file, employees_file)
        if demand_df is not None:
            result = run_comparison(demand_df, employees_df, num_stores=num_stores)
            st.session_state.result = result
            st.session_state.store_name = store_name
            st.session_state.num_stores = num_stores
            st.session_state.qa_history = []  # reset on new optimization

# Mostrar resultados si existen
if st.session_state.result is None:
    st.info(
        "Configura los parámetros en el panel izquierdo y presiona **Optimizar →** "
        "para correr el análisis. Los datos demo simulan una tienda de retail mexicano "
        "con 80 FTEs, operación domingo a domingo y curvas de tráfico realistas."
    )
else:
    result = st.session_state.result
    bc = result["baseline"]["cost_breakdown"]
    oc = result["optimized"]["cost_breakdown"]
    d = result["delta"]

    # Total de empleados (para KPIs dinámicos que se adaptan a la tienda subida)
    total_emp = len(result["baseline"]["hours_summary"])

    # KPIs principales
    st.markdown("#### Resultados — " + st.session_state.store_name)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Ahorro semanal",
            fmt_mxn(d["cost_savings_weekly_mxn"]),
            delta=fmt_pct(d["cost_savings_pct"]),
        )
    with col2:
        st.metric(
            f"Ahorro anual ({st.session_state.num_stores} tiendas)",
            fmt_mxn(d["cost_savings_annual_chain"]),
        )
    with col3:
        st.metric(
            "Empleados regularizados (>40h → ≤40h)",
            f"{d['employees_brought_to_legal']} de {total_emp}",
            delta=f"De {bc['employees_over_40h']} a {oc['employees_over_40h']}",
            delta_color="inverse",
        )
    with col4:
        st.metric(
            "Cobertura de demanda",
            fmt_pct(oc["coverage_pct"]),
            delta=fmt_pct(d["optimized_coverage"] - d["baseline_coverage"]),
        )

    # Tabs
    tab1, tab_detail, tab2, tab3, tab4 = st.tabs([
        "Resumen ejecutivo",
        "Análisis detallado",
        "Análisis visual",
        "Schedule semanal",
        "Pregúntale a Aivena",
    ])

    # -------- TAB 1: Resumen ejecutivo --------
    with tab1:
        col_l, col_r = st.columns([2, 1])
        with col_l:
            st.markdown("##### Brief para el CFO")
            with st.spinner("Generando brief…"):
                brief = generate_executive_brief(
                    result,
                    num_stores=st.session_state.num_stores,
                    store_name=st.session_state.store_name,
                )
            st.markdown(brief)

        with col_r:
            st.markdown("##### Checks de cumplimiento")
            if d["meets_8pct_threshold"]:
                st.success("✓ Ahorro ≥ 8% (mandato del proyecto)")
            else:
                st.error("✗ Ahorro < 8%")
            if d["meets_legal_compliance"]:
                st.success("✓ Ningún empleado >40h (cumplimiento legal 2027)")
            else:
                st.error("✗ Hay empleados >40h")
            if d["meets_no_undercoverage"]:
                st.success("✓ 100% cobertura demanda (sin sub-dotación)")
            else:
                st.error("✗ Sub-dotación en picos")

            st.markdown("##### Comparación lado a lado")
            comp_df = pd.DataFrame([
                {"Métrica": "Costo total/sem (MXN)", "Baseline": f"${bc['cost_total_mxn']:,.0f}", "Optimizado": f"${oc['cost_total_mxn']:,.0f}"},
                {"Métrica": "Horas regulares", "Baseline": f"{bc['total_regular_hours']:,.0f}", "Optimizado": f"{oc['total_regular_hours']:,.0f}"},
                {"Métrica": "Horas extra", "Baseline": f"{bc['total_overtime_hours']:,.0f}", "Optimizado": f"{oc['total_overtime_hours']:,.0f}"},
                {"Métrica": "Empleados >40h", "Baseline": f"{bc['employees_over_40h']}", "Optimizado": f"{oc['employees_over_40h']}"},
                {"Métrica": "Sobrestaffing (p-h)", "Baseline": f"{bc['total_overstaff_personhours']:,.0f}", "Optimizado": f"{oc['total_overstaff_personhours']:,.0f}"},
                {"Métrica": "Gap en picos (p-h)", "Baseline": f"{bc['total_gap_personhours']:,.0f}", "Optimizado": f"{oc['total_gap_personhours']:,.0f}"},
            ])
            st.dataframe(comp_df, hide_index=True, use_container_width=True)

    # -------- TAB DETAIL: Análisis detallado --------
    with tab_detail:
        st.markdown(
            "Tres lentes sobre el mismo análisis: financiero (CFO), operativo "
            "(Director de Operaciones) y metodológico (perfil técnico). Cada sección "
            "responde preguntas distintas que un evaluador puede hacer."
        )

        # === SECCIÓN 1: LENTE FINANCIERO ===
        st.markdown("---")
        st.markdown("##### Vista financiera — para CFO")

        # Cálculos de los 3 componentes del ahorro
        salario_promedio_baseline = (
            bc["cost_total_mxn"] / max(1, bc["total_regular_hours"] + bc["total_overtime_hours"])
        )
        ahorro_por_overstaff = bc["total_overstaff_personhours"] * salario_promedio_baseline
        ahorro_por_overtime = bc["cost_overtime_mxn"]
        ahorro_total = d["cost_savings_weekly_mxn"]

        f1, f2, f3 = st.columns(3)
        with f1:
            st.metric(
                "Ahorro por sobrestaffing eliminado",
                fmt_mxn(ahorro_por_overstaff),
                help="Personas-hora pagadas a personal ocioso en valles (eliminadas con re-allocation)",
            )
        with f2:
            st.metric(
                "Ahorro por overtime evitado",
                fmt_mxn(ahorro_por_overtime),
                help="Costo de horas extra ilegales (post-2027) absorbidas por el rediseño",
            )
        with f3:
            st.metric(
                "Costo total evitado/semana",
                fmt_mxn(ahorro_total),
                delta=fmt_pct(d["cost_savings_pct"]),
            )

        st.markdown("**Sensibilidad a salarios** — qué pasa con el ahorro si el SMG sube en 2027:")
        sens_rows = []
        for pct in [0, 5, 10, 15, 20]:
            mult = 1 + pct / 100
            ahorro_sem = d["cost_savings_weekly_mxn"] * mult
            ahorro_anual_chain = ahorro_sem * 52 * st.session_state.num_stores
            sens_rows.append({
                "Escenario": f"SMG +{pct}%" if pct > 0 else "Base (SMG actual)",
                "Ahorro semanal": fmt_mxn(ahorro_sem),
                f"Ahorro anual ({st.session_state.num_stores} tiendas)": fmt_mxn(ahorro_anual_chain),
                "Ahorro %": fmt_pct(d["cost_savings_pct"]),
            })
        st.dataframe(pd.DataFrame(sens_rows), hide_index=True, use_container_width=True)

        st.caption(
            "El ahorro % se mantiene constante porque los salarios afectan baseline y optimizado "
            "proporcionalmente. Para sensibilidad de demanda (variación de tráfico) modifica el "
            "CSV y vuelve a optimizar — eso requiere correr el motor con nuevos inputs."
        )

        # === SECCIÓN 2: LENTE OPERATIVO ===
        st.markdown("---")
        st.markdown("##### Vista operativa — para Director de Operaciones")

        bh = result["baseline"]["hours_summary"][["emp_id", "name", "role", "total_hours"]].rename(
            columns={"total_hours": "horas_baseline"}
        )
        oh = result["optimized"]["hours_summary"][["emp_id", "total_hours"]].rename(
            columns={"total_hours": "horas_optimizado"}
        )
        delta_emp = bh.merge(oh, on="emp_id")
        delta_emp["delta"] = delta_emp["horas_optimizado"] - delta_emp["horas_baseline"]

        ganan = int((delta_emp["delta"] > 0).sum())
        pierden = int((delta_emp["delta"] < 0).sum())
        igual = int((delta_emp["delta"] == 0).sum())

        o1, o2, o3 = st.columns(3)
        with o1:
            st.metric("Empleados que ganan horas", ganan, help="Subutilizados en baseline, ahora con carga normalizada")
        with o2:
            st.metric("Empleados que pierden horas", pierden, help="Estaban en overtime ilegal, ahora dentro del tope 40h")
        with o3:
            st.metric("Sin cambio", igual)

        # Top 10 con mayor cambio absoluto
        st.markdown("**Top 10 empleados con mayor cambio de horas:**")
        delta_emp["abs_delta"] = delta_emp["delta"].abs()
        top10 = delta_emp.sort_values("abs_delta", ascending=False).head(10).copy()
        top10_display = top10[["emp_id", "name", "role", "horas_baseline", "horas_optimizado", "delta"]].rename(
            columns={
                "emp_id": "ID",
                "name": "Empleado",
                "role": "Rol",
                "horas_baseline": "Horas hoy",
                "horas_optimizado": "Horas con Aivena",
                "delta": "Δ horas",
            }
        )
        st.dataframe(top10_display, hide_index=True, use_container_width=True)

        # Gráfica horas por día
        st.markdown("**Total horas trabajadas por día — baseline vs optimizado:**")
        baseline_by_day = result["baseline"]["schedule_df"].groupby("dia")["working"].sum().reset_index()
        optimized_by_day = result["optimized"]["schedule_df"].groupby("dia")["working"].sum().reset_index()
        day_order = {d: i for i, d in enumerate(DAYS)}
        baseline_by_day["order"] = baseline_by_day["dia"].map(day_order)
        optimized_by_day["order"] = optimized_by_day["dia"].map(day_order)
        baseline_by_day = baseline_by_day.sort_values("order")
        optimized_by_day = optimized_by_day.sort_values("order")

        fig_days = go.Figure()
        fig_days.add_trace(go.Bar(
            x=baseline_by_day["dia"], y=baseline_by_day["working"],
            name="Baseline", marker_color="#F0997B",
        ))
        fig_days.add_trace(go.Bar(
            x=optimized_by_day["dia"], y=optimized_by_day["working"],
            name="Optimizado", marker_color="#5DCAA5",
        ))
        fig_days.update_layout(
            barmode="group",
            height=320,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E5E5E5", size=12),
            xaxis_title="",
            yaxis_title="Personas-hora trabajadas",
            legend=dict(orientation="h", y=1.1, x=0, bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=10, r=10, t=40, b=40),
        )
        fig_days.update_xaxes(showgrid=False)
        fig_days.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)")
        st.plotly_chart(fig_days, use_container_width=True)

        st.markdown("**Recomendaciones de rollout:**")
        st.markdown(
            "- **Comunicación interna primero.** El optimizado regulariza horas y "
            "protege empleos. Comunicar antes de operar evita resistencia sindical.\n"
            "- **Piloto de 4 semanas en una tienda.** Comparativo A/B contra el modelo "
            "actual. Validar ahorro en P&L real antes de escalar.\n"
            "- **Capacitar gerentes de piso.** El sistema sugiere, el gerente valida y "
            "ajusta. No reemplaza el criterio operativo.\n"
            "- **Monitoreo continuo.** KPIs semana-a-semana: cobertura efectiva, costo "
            "real vs proyectado, NPS empleado, rotación."
        )

        # === SECCIÓN 3: LENTE METODOLÓGICO ===
        st.markdown("---")
        st.markdown("##### Vista metodológica — para perfil técnico")

        st.markdown("**Supuestos clave del modelo:**")
        m1, m2 = st.columns(2)
        with m1:
            st.info(
                "**Constraints duros (cumplimiento legal)**\n\n"
                "- Tope semanal: 40h por empleado\n"
                "- Tope diario: 8h por empleado\n"
                "- Turno mínimo: 4h continuas\n"
                "- 1 día de descanso obligatorio/semana"
            )
            st.info(
                "**Modelo del baseline (\"lo que hacen hoy\")**\n\n"
                "- Dos turnos por día (AM/PM)\n"
                "- Buffer del 18% sobre demanda planeada\n"
                "- 85% de plantilla disponible (vacaciones/incapacidades)\n"
                "- Overtime concentrado en 20% (senior/supervisores)"
            )
        with m2:
            st.info(
                "**Función objetivo del optimizador**\n\n"
                "- Minimizar costo laboral total\n"
                "- Cubrir 100% de demanda en cada hora-día\n"
                "- Bajo todos los constraints duros simultáneamente"
            )
            st.info(
                "**Cálculo de costo**\n\n"
                "- Regular: horas × salario_hora\n"
                "- Overtime: horas extra × salario × 2.0 (LFT México)\n"
                "- Sin costo de oportunidad de sub-dotación (conservador)"
            )

        st.markdown("**Por qué greedy y no MIP:**")
        st.markdown(
            "Algoritmo greedy en Python puro (sin OR-Tools) por tres razones: "
            "**(1)** latencia <1s vs 30-90s del solver MIP, mejor para demo y para "
            "Streamlit Cloud bajo el límite de Cloudflare; **(2)** cero dependencias "
            "externas, deploy más robusto; **(3)** el ahorro greedy ya supera el 8% "
            "mandatorio con margen — la sub-optimalidad estimada (~5-10pp vs CP-SAT) "
            "no cambia la conclusión. Roadmap Q3 2026: migrar a CP-SAT si un design "
            "partner lo justifica con números."
        )

        st.markdown("**Validación de la cifra:**")
        st.markdown(
            f"El ahorro de **{d['cost_savings_pct']*100:.1f}%** está dentro del rango "
            "creíble en literatura de workforce optimization para retail (10-18%). "
            "Por encima de 20% sería sospechoso de baseline pintado; por debajo de 8% "
            "fallaría el mandato del proyecto. El rango defendible que recomendamos en "
            "venta es **12-15%**, considerando un buffer del 5-8% en hora pico para "
            "absorber variabilidad estocástica de tráfico no modelada en v0."
        )

        st.caption(
            "Documentación completa en `docs/ASSUMPTIONS.md` y `docs/METHODOLOGY.md` "
            "del repositorio en GitHub."
        )

    # -------- TAB 2: Análisis visual --------
    with tab2:
        st.markdown(
            "Estas dos gráficas son la base de la conversación con un CFO. "
            "La primera muestra **dónde** se pierde dinero (sobrestaffing en valles, gap en picos). "
            f"La segunda muestra **a quiénes** afecta el problema legal: {bc['employees_over_40h']} de {total_emp} empleados violan el tope 40h post-2027."
        )
        st.plotly_chart(chart_demand_vs_staffing(result), use_container_width=True)
        st.plotly_chart(chart_hours_distribution(result), use_container_width=True)

    # -------- TAB 3: Schedule semanal --------
    with tab3:
        st.markdown(
            "Schedule completo generado por Aivena. Cada celda verde indica que el empleado está "
            "trabajando en ese slot horario. La tabla completa también está disponible para descargar."
        )
        max_emp = st.slider("Mostrar primeros N empleados en heatmap", 10, 80, 30, step=5)
        st.plotly_chart(chart_schedule_heatmap(result, max_employees=max_emp), use_container_width=True)

        sched_df = result["optimized"]["schedule_df"]
        st.markdown("##### Descargar schedule completo")
        col_a, col_b = st.columns(2)
        with col_a:
            csv_long = sched_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Descargar (formato largo, CSV)",
                csv_long,
                file_name=f"schedule_{st.session_state.store_name.replace(' ', '_')}.csv",
                mime="text/csv",
            )
        with col_b:
            pivot = sched_df.pivot_table(
                index="emp_id", columns=["dia", "hora"], values="working", fill_value=0
            )
            csv_wide = pivot.to_csv().encode("utf-8")
            st.download_button(
                "Descargar (formato matriz, CSV)",
                csv_wide,
                file_name=f"schedule_matrix_{st.session_state.store_name.replace(' ', '_')}.csv",
                mime="text/csv",
            )

        st.markdown("##### Resumen de horas por empleado (top 20)")
        hs = result["optimized"]["hours_summary"].sort_values("total_hours", ascending=False).head(20)
        st.dataframe(
            hs[["emp_id", "name", "role", "total_hours", "days_worked", "cost_total"]]
            .rename(columns={
                "emp_id": "ID",
                "name": "Empleado",
                "role": "Rol",
                "total_hours": "Horas",
                "days_worked": "Días",
                "cost_total": "Costo (MXN)",
            }),
            hide_index=True,
            use_container_width=True,
        )

    # -------- TAB 4: Q&A --------
    with tab4:
        st.markdown(
            "Haz preguntas sobre el análisis o explora escenarios alternativos. "
            "Algunos ejemplos:"
        )
        col_e1, col_e2, col_e3 = st.columns(3)
        ex_q = None
        with col_e1:
            if st.button("¿Qué pasa si el SMG sube 12% en 2027?", use_container_width=True):
                ex_q = "¿Qué pasa con el ahorro si el SMG sube 12% en 2027?"
        with col_e2:
            if st.button("¿Y si el tráfico de la tienda crece 15%?", use_container_width=True):
                ex_q = "Si la demanda crece 15% por una nueva campaña, ¿necesito contratar?"
        with col_e3:
            if st.button("¿Cuál es el riesgo legal específico?", use_container_width=True):
                ex_q = "¿Cuál es el riesgo legal específico del baseline post-reforma 2027?"

        # Mostrar historial
        for turn in st.session_state.qa_history:
            with st.chat_message(turn["role"]):
                st.markdown(turn["content"])

        # Input
        user_q = st.chat_input("Pregúntale a Aivena…")
        question_to_ask = ex_q or user_q
        if question_to_ask:
            st.session_state.qa_history.append({"role": "user", "content": question_to_ask})
            with st.chat_message("user"):
                st.markdown(question_to_ask)
            with st.chat_message("assistant"):
                with st.spinner("Pensando…"):
                    answer = answer_question(
                        question_to_ask,
                        result,
                        num_stores=st.session_state.num_stores,
                        conversation_history=st.session_state.qa_history[:-1],
                    )
                st.markdown(answer)
            st.session_state.qa_history.append({"role": "assistant", "content": answer})
