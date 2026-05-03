"""
Capa AI: brief ejecutivo y modo Q&A what-if usando Anthropic API.

Dos funciones principales:
- generate_executive_brief(): un párrafo en español listo para CFO
- answer_question(): responde preguntas what-if con contexto de los resultados

Ambas usan Claude Sonnet como modelo base. Manejamos errores con gracia
para que la app no falle si la API tiene problemas o falta la key.
"""

import os
from typing import Dict, List, Optional

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


MODEL = "claude-sonnet-4-5"
MAX_TOKENS_BRIEF = 1500
MAX_TOKENS_QA = 1500


def _get_client():
    """
    Devuelve cliente Anthropic, o None si no hay API key configurada
    o si la librería no está instalada.
    Permite que la app degrade gracefully a modo "sin AI".
    """
    if not _ANTHROPIC_AVAILABLE:
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            pass
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def _format_results_for_prompt(result: Dict, num_stores: int = 1) -> str:
    """
    Convierte el resultado del comparador en un bloque de contexto compacto
    para inyectar al prompt. Claude usa esto como única fuente de verdad.
    """
    bc = result["baseline"]["cost_breakdown"]
    oc = result["optimized"]["cost_breakdown"]
    d = result["delta"]
    n_total = len(result["baseline"]["hours_summary"])

    return f"""DATOS DE LA TIENDA Y RESULTADOS DEL ANÁLISIS:

ESCENARIO ACTUAL (baseline con Excel):
- Costo laboral total/semana: $ {bc['cost_total_mxn']:,.0f} MXN
  - Horas regulares: $ {bc['cost_regular_mxn']:,.0f} MXN ({bc['total_regular_hours']:.0f} h)
  - Horas extra: $ {bc['cost_overtime_mxn']:,.0f} MXN ({bc['total_overtime_hours']:.0f} h)
- Empleados >40h (ilegal post-2027): {bc['employees_over_40h']} de {n_total}
- Sobrestaffing en valles: {bc['total_overstaff_personhours']:.0f} personas-hora
- Sub-dotación en picos (gap): {bc['total_gap_personhours']:.0f} personas-hora

ESCENARIO OPTIMIZADO (Aivena):
- Costo laboral total/semana: $ {oc['cost_total_mxn']:,.0f} MXN
- Empleados >40h: {oc['employees_over_40h']} (cumplimiento legal)
- Cobertura demanda: {oc['coverage_pct']*100:.1f}%
- Horas extra: {oc['total_overtime_hours']:.0f} h

IMPACTO:
- Ahorro semanal: $ {d['cost_savings_weekly_mxn']:,.0f} MXN
- Ahorro %: {d['cost_savings_pct']*100:.1f}%
- Ahorro anual (1 tienda): $ {d['cost_savings_annual_mxn']:,.0f} MXN
- Ahorro anual ({num_stores} tiendas): $ {d['cost_savings_annual_chain']:,.0f} MXN
- Empleados regularizados: {d['employees_brought_to_legal']}
- Sobrestaffing eliminado: {d['overstaff_hours_eliminated']:.0f} personas-hora"""


# ---------- BRIEF EJECUTIVO ----------

BRIEF_SYSTEM_PROMPT = """Eres el analista senior de Aivena Workforce, un producto de IA que optimiza la programación de turnos para retail mexicano post-reforma laboral 2027 (jornada de 40h).

Tu trabajo: redactar un brief ejecutivo en español de México, listo para que un CFO o Director de Operaciones lea en menos de dos minutos antes de aprobar un piloto.

REGLAS DE ESTILO:
- Tono: directo, profesional, sin jerga académica. Habla como un consultor que ha estado del lado del cliente.
- Estructura: 4 secciones cortas con encabezados breves (### en markdown).
  1. ### Diagnóstico — qué está pasando hoy en la tienda (1-2 oraciones).
  2. ### Impacto cuantificado — los números clave (cifras MXN concretas).
  3. ### Riesgo regulatorio — el problema legal post-2027 con tu plantilla actual.
  4. ### Próximo paso — qué proponemos hacer la próxima semana.
- Cifras: usa formato MXN con comas y "$". Ejemplo: $24,450 MXN.
- NO inventes datos que no estén en el contexto. Si una métrica no está, no la menciones.
- NO uses bullets ni listas. Prosa corta.
- NO uses emojis.
- Largo total: 180-280 palabras."""


def generate_executive_brief(result: Dict, num_stores: int = 1, store_name: str = "la tienda") -> str:
    """
    Genera un brief ejecutivo en español listo para CFO.
    Si no hay API key disponible, devuelve un brief boilerplate (degradación graceful).
    """
    client = _get_client()
    if client is None:
        return _fallback_brief(result, num_stores, store_name)

    context = _format_results_for_prompt(result, num_stores)
    user_prompt = f"""Tienda: {store_name}
Cadena: {num_stores} tienda(s)

{context}

Redacta el brief ejecutivo siguiendo el formato establecido."""

    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_BRIEF,
            system=BRIEF_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        return _fallback_brief(result, num_stores, store_name) + f"\n\n_(Nota: AI brief no disponible — {type(e).__name__})_"


def _fallback_brief(result: Dict, num_stores: int, store_name: str) -> str:
    """Brief boilerplate cuando la API no está disponible."""
    bc = result["baseline"]["cost_breakdown"]
    oc = result["optimized"]["cost_breakdown"]
    d = result["delta"]
    n_total = len(result["baseline"]["hours_summary"])
    pct_over = bc['employees_over_40h'] / n_total * 100 if n_total > 0 else 0
    return f"""### Diagnóstico
{store_name} opera hoy con un modelo de programación basado en promedios y staffing constante por turno. Esto genera dos patologías simultáneas: sobrestaffing en valles ({bc['total_overstaff_personhours']:.0f} personas-hora pagadas a personal ocioso) y sub-dotación en picos.

### Impacto cuantificado
El costo laboral actual es de $ {bc['cost_total_mxn']:,.0f} MXN/semana. Aivena reduce esto a $ {oc['cost_total_mxn']:,.0f} MXN/semana — un ahorro de $ {d['cost_savings_weekly_mxn']:,.0f} MXN ({d['cost_savings_pct']*100:.1f}%) sin tocar plantilla. Anualizado para {num_stores} tienda(s): $ {d['cost_savings_annual_chain']:,.0f} MXN/año.

### Riesgo regulatorio
{bc['employees_over_40h']} de {n_total} empleados ({pct_over:.0f}%) trabajan hoy más de 40 horas semanales. Bajo la reforma laboral 2027, esto es una infracción directa del Artículo 61 de la LFT. La optimización los regulariza a todos sin afectar cobertura.

### Próximo paso
Pilotear Aivena en {store_name} durante 4 semanas. Comparativo A/B contra la programación actual, con reporte semanal de costo evitado y cumplimiento. Sin compromiso anual, validación basada en tu propio P&L."""


# ---------- Q&A WHAT-IF ----------

QA_SYSTEM_PROMPT = """Eres Aivena, una asistente de IA experta en planeación de fuerza laboral para retail mexicano. Tu rol es ayudar a un CFO o Director de Operaciones a entender el plan de turnos optimizado y explorar escenarios alternativos.

REGLAS:
- Responde en español de México, tono profesional pero accesible.
- Usa los DATOS DE CONTEXTO como fuente única de verdad. No inventes cifras.
- Si te preguntan "qué pasa si X cambia", calcula el impacto aproximado:
  - Si suben los salarios un X%, el costo total optimizado sube proporcionalmente; el % de ahorro se mantiene.
  - Si la demanda sube un X%, las horas asignadas suben proporcionalmente, hasta el tope de 40h/empleado. Si la plantilla actual no alcanza, hay que contratar.
  - Si el SMG sube un X%, los salarios base suben — modela como aumento proporcional.
  - Para preguntas sobre cumplimiento legal, cita Artículo 61 de la LFT (jornada máxima) y la reforma 2027.
- Cuando hagas un cálculo aproximado, sé EXPLÍCITO: "Aproximación rápida: si X sube 10%, Y debería pasar de A a A*1.1 = B".
- Si la pregunta requiere recorrer el solver con parámetros nuevos (ej. cambiar tope a 38h), reconoce la limitación y ofrece volver a correr la herramienta con esos parámetros.
- Largo: 80-200 palabras por respuesta. Sin bullets ni listas, salvo que la pregunta lo justifique.
- Sin emojis."""


def answer_question(
    question: str,
    result: Dict,
    num_stores: int = 1,
    conversation_history: Optional[List[Dict]] = None,
) -> str:
    """
    Responde una pregunta what-if con contexto del análisis.

    Args:
        question: Pregunta del usuario (ej. "¿qué pasa si el SMG sube 12%?")
        result: Resultado del comparador
        num_stores: Para anualizaciones
        conversation_history: Lista de turnos previos [{"role": "user/assistant", "content": "..."}]

    Returns:
        Respuesta en español. Si no hay API, devuelve mensaje informativo.
    """
    client = _get_client()
    if client is None:
        return ("La capa de Q&A requiere una API key de Anthropic configurada. "
                "Por favor configura ANTHROPIC_API_KEY en los secrets de Streamlit Cloud "
                "o como variable de entorno.")

    context = _format_results_for_prompt(result, num_stores)
    history = conversation_history or []

    messages = []
    # Inyectamos el contexto en el primer mensaje del usuario
    if not history:
        messages.append({
            "role": "user",
            "content": f"{context}\n\n---\n\nPregunta: {question}"
        })
    else:
        # Si hay historial, ponemos contexto al inicio y agregamos historial
        messages.append({"role": "user", "content": f"Para tu referencia:\n{context}"})
        messages.append({"role": "assistant", "content": "Entendido. Estoy lista para responder preguntas sobre este análisis."})
        messages.extend(history)
        messages.append({"role": "user", "content": question})

    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_QA,
            system=QA_SYSTEM_PROMPT,
            messages=messages,
        )
        return msg.content[0].text
    except Exception as e:
        return f"Error consultando a Aivena: {type(e).__name__}: {str(e)}"


if __name__ == "__main__":
    # Test local: verifica que el fallback brief funciona aunque no haya API key
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.data_generator import generate_store_dataset
    from src.comparator import run_comparison

    ds = generate_store_dataset()
    result = run_comparison(ds["demand_df"], ds["employees_df"], num_stores=50)

    print("=== BRIEF (puede ser fallback si no hay API key) ===\n")
    print(generate_executive_brief(result, num_stores=50, store_name="Tienda Demo CDMX"))
    print("\n=== Q&A TEST ===\n")
    print(answer_question("¿Qué pasa si el SMG sube 12% en 2027?", result, num_stores=50))
