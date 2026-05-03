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
    """Demanda vs staffing — un panel por día (grid 2x4)."""
    bcov = result["baseline"]["coverage_df"]
    ocov = result["optimized"]["coverage_df"]

    fig = make_subplots(
        rows=2, cols=4,
        subplot_titles=DAYS,
        shared_yaxes=True,
        horizontal_spacing=0.04,
        vertical_spacing=0.22,
    )

    for i, day in enumerate(DAYS):
        row = 1 if i < 4 else 2
        col = (i % 4) + 1
        bd = bcov[bcov["dia"] == day].sort_values("hora")
        od = ocov[ocov["dia"] == day].sort_values("hora")
        x_labels = [f"{h}h" for h in bd["hora"]]

        fig.add_trace(go.Bar(
            x=x_labels, y=bd["asignado"], name="Baseline (Excel)",
            marker_color="#F0997B", opacity=0.85, showlegend=(i == 0),
        ), row=row, col=col)
        fig.add_trace(go.Bar(
            x=x_labels, y=od["asignado"], name="Optimizado (Aivena)",
            marker_color="#5DCAA5", opacity=0.9, showlegend=(i == 0),
        ), row=row, col=col)
        fig.add_trace(go.Scatter(
            x=x_labels, y=bd["requerido"], name="Demanda real",
            mode="lines+markers",
            line=dict(color="#FAFAFA", width=2),
            marker=dict(size=4, color="#FAFAFA"),
            showlegend=(i == 0),
        ), row=row, col=col)

    fig.update_layout(
        height=480, barmode="group",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E5E5", size=11),
        legend=dict(
            orientation="h", y=1.12, x=0.5, xanchor="center",
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=10, r=10, t=70, b=10),
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(size=9))
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        zerolinecolor="rgba(255,255,255,0.08)",
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
    fig.add_vline(
        x=3.5,
        line=dict(color="#E24B4A", width=1.5, dash="dash"),
        annotation_text="Tope legal 2027",
        annotation_position="top",
        annotation_font_color="#E24B4A",
    )
    fig.update_layout(
        title="Distribución de horas semanales por empleado",
        barmode="group",
        height=380,
        xaxis_title="Horas trabajadas/semana",
        yaxis_title="Empleados",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E5E5", size=12),
        legend=dict(
            orientation="h", y=1.1, x=0,
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=10, r=10, t=70, b=40),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        zerolinecolor="rgba(255,255,255,0.08)",
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
    day_order = {d: i for i, d in enumerate(DAYS)}
    cols_sorted = sorted(pivot.columns, key=lambda c: (day_order.get(c[0], 99), c[1]))
    pivot = pivot[cols_sorted]
    pivot = pivot.iloc[:max_employees]

    col_labels = [f"{d[:3]} {h}h" for d, h in pivot.columns]

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=col_labels,
        y=pivot.index.tolist(),
        colorscale=[[0, "rgba(255,255,255,0.04)"], [1, "#5DCAA5"]],
        showscale=False,
        hovertemplate="Empleado: %{y}<br>Slot: %{x}<br>Trabajando: %{z}<extra></extra>",
    ))
    fig.update_layout(
        title=f"Schedule semanal optimizado (primeros {max_employees} empleados)",
        height=520,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E5E5", size=11),
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
            f"{d['employees_brought_to_legal']} de 80",
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
    tab1, tab2, tab3, tab4 = st.tabs([
        "Resumen ejecutivo",
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

    # -------- TAB 2: Análisis visual --------
    with tab2:
        st.markdown(
            "Estas dos gráficas son la base de la conversación con un CFO. "
            "La primera muestra **dónde** se pierde dinero (sobrestaffing en valles, gap en picos). "
            "La segunda muestra **a quiénes** afecta el problema legal: 68 de 80 empleados violan el tope 40h post-2027."
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
