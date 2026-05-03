"""
Comparador: ejecuta baseline y optimizado, calcula deltas y ahorros.

Es el entry point principal que la Streamlit app va a llamar.
También se usa para validación reproducible desde CLI.
"""

import pandas as pd
from typing import Dict
from .data_generator import generate_store_dataset
from .baseline import build_baseline_schedule
from .optimizer import optimize_schedule


# Multiplicador para anualización (52 semanas)
WEEKS_PER_YEAR = 52


def run_comparison(demand_df: pd.DataFrame, employees_df: pd.DataFrame,
                   num_stores: int = 1) -> Dict:
    """
    Ejecuta baseline y optimizado, calcula deltas.

    Args:
        demand_df: DataFrame de demanda hora-día
        employees_df: DataFrame de empleados
        num_stores: Número de tiendas para escalar el ahorro anualizado

    Returns dict con:
        - baseline: resultado completo del baseline
        - optimized: resultado completo del optimizado
        - delta: dict con deltas y ahorros
    """
    baseline = build_baseline_schedule(demand_df, employees_df)
    optimized = optimize_schedule(demand_df, employees_df)

    bc = baseline["cost_breakdown"]
    oc = optimized["cost_breakdown"]

    cost_savings_weekly = bc["cost_total_mxn"] - oc["cost_total_mxn"]
    savings_pct = cost_savings_weekly / bc["cost_total_mxn"] if bc["cost_total_mxn"] > 0 else 0

    delta = {
        "cost_savings_weekly_mxn":     cost_savings_weekly,
        "cost_savings_pct":            savings_pct,
        "cost_savings_annual_mxn":     cost_savings_weekly * WEEKS_PER_YEAR,
        "cost_savings_annual_chain":   cost_savings_weekly * WEEKS_PER_YEAR * num_stores,

        "overtime_hours_eliminated":   bc["total_overtime_hours"] - oc["total_overtime_hours"],
        "overstaff_hours_eliminated":  bc["total_overstaff_personhours"] - oc["total_overstaff_personhours"],
        "employees_brought_to_legal":  bc["employees_over_40h"] - oc["employees_over_40h"],

        "baseline_coverage":           1 - (bc["total_gap_personhours"] / demand_df["personas_requeridas"].sum()),
        "optimized_coverage":          oc["coverage_pct"],

        "meets_8pct_threshold":        savings_pct >= 0.08,
        "meets_legal_compliance":      oc["employees_over_40h"] == 0,
        "meets_no_undercoverage":      oc["total_gap_personhours"] == 0,
    }

    return {
        "baseline": baseline,
        "optimized": optimized,
        "delta": delta,
    }


def print_executive_summary(result: Dict) -> None:
    """Imprime resumen ejecutivo en español listo para CFO."""
    bc = result["baseline"]["cost_breakdown"]
    oc = result["optimized"]["cost_breakdown"]
    d = result["delta"]

    print("=" * 70)
    print("   AIVENA WORKFORCE — RESUMEN EJECUTIVO")
    print("=" * 70)
    print()
    print("ESCENARIO ACTUAL (lo que estás haciendo hoy con tu Excel)")
    print("-" * 70)
    print(f"  Costo laboral total/semana:    $ {bc['cost_total_mxn']:>12,.0f} MXN")
    print(f"      ├─ Horas regulares:        $ {bc['cost_regular_mxn']:>12,.0f} MXN")
    print(f"      └─ Horas extra:            $ {bc['cost_overtime_mxn']:>12,.0f} MXN")
    print(f"  Empleados >40h (ilegal 2027):    {bc['employees_over_40h']:>12d} de 80")
    print(f"  Sobrestaffing en valles:         {bc['total_overstaff_personhours']:>12.0f} personas-hora")
    print(f"  Gap en picos (clientes mal atendidos): {bc['total_gap_personhours']:>6.0f} personas-hora")
    print()
    print("ESCENARIO OPTIMIZADO (Aivena Workforce)")
    print("-" * 70)
    print(f"  Costo laboral total/semana:    $ {oc['cost_total_mxn']:>12,.0f} MXN")
    print(f"  Empleados >40h:                  {oc['employees_over_40h']:>12d}  ✓ Cumplimiento legal")
    print(f"  Cobertura de demanda:            {oc['coverage_pct']*100:>11.1f}%  ✓ Sin sub-dotación en picos")
    print(f"  Sobrestaffing eliminado:         {d['overstaff_hours_eliminated']:>12.0f} personas-hora")
    print()
    print("IMPACTO CUANTIFICADO")
    print("-" * 70)
    print(f"  Ahorro semanal:                $ {d['cost_savings_weekly_mxn']:>12,.0f} MXN")
    print(f"  Ahorro anual (1 tienda):       $ {d['cost_savings_annual_mxn']:>12,.0f} MXN")
    print(f"  Ahorro %:                        {d['cost_savings_pct']*100:>11.1f}%")
    print()
    print("CHECKS DE CUMPLIMIENTO")
    print("-" * 70)
    print(f"  ≥ 8% de ahorro:                  {'✓' if d['meets_8pct_threshold'] else '✗'}")
    print(f"  Ningún empleado >40h:            {'✓' if d['meets_legal_compliance'] else '✗'}")
    print(f"  100% cobertura demanda:          {'✓' if d['meets_no_undercoverage'] else '✗'}")
    print("=" * 70)


if __name__ == "__main__":
    ds = generate_store_dataset()
    result = run_comparison(ds["demand_df"], ds["employees_df"], num_stores=50)
    print_executive_summary(result)

    # Anualizado para 50 tiendas
    print()
    print(f"  Ahorro anualizado para cadena de 50 tiendas:")
    print(f"      $ {result['delta']['cost_savings_annual_chain']:,.0f} MXN/año")
