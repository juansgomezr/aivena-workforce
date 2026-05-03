"""
Baseline: simula el schedule actual de la tienda usando Excel y promedios históricos.

Lógica del baseline:
1. La tienda calcula el promedio diario de personas requeridas y le añade 10% de buffer
2. Asigna ese número fijo de personas durante TODO el horario operativo (staffing constante)
3. Cuando la demanda real excede ese fijo en hora pico → personal trabaja overtime forzado
4. Cuando la demanda real es menor → sobrestaffing pagado completo

Resultado:
- Sub-dotación en picos (gap entre demanda real y staffing constante)
- Sobrestaffing en valles (personal pagado ocioso)
- Overtime forzado (algunos empleados >40h/semana)
- Costo inflado vs. lo necesario
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from .data_generator import (
    DAYS, OPERATING_HOURS, OVERTIME_MULTIPLIER, operating_hours_for
)

BUFFER_PCT = 0.18  # buffer del 18% sobre staffing planeado (sesgo conservador típico)
OT_CONCENTRATION_PCT = 0.20  # cuando hay gap, el overtime se concentra en este % de la plantilla
EFFECTIVE_POOL_PCT = 0.85   # solo el 85% de la plantilla está disponible cualquier semana
                             # (vacaciones, incapacidades, baja médica, capacitación, ausentismo).
                             # Patrón observado: retail mexicano opera con ~12-18% de plantilla
                             # no-disponible en cualquier momento dado.


def _staffing_per_shift(demand_df: pd.DataFrame) -> Dict[str, Dict[str, Tuple[int, int, int]]]:
    """
    Calcula el staffing para dos turnos por día (matutino y vespertino).
    Cada turno tiene staffing constante alineado al promedio de demanda en ese bloque
    + buffer del 15%. Esto modela el patrón observado de retail mexicano:
    el manager planea por turno (no hora-por-hora), basado en históricos, con sesgo
    conservador para "no quedar corto".

    Las horas operativas se infieren del propio demand_df (no son hardcoded),
    para que la herramienta funcione con cualquier tienda independiente de su horario.

    Returns: dict[day] -> {"AM": (start_h, end_h, staff), "PM": (start_h, end_h, staff)}
    """
    shifts = {}
    for day in DAYS:
        day_demand = demand_df[demand_df["dia"] == day]
        if day_demand.empty:
            continue
        op_start = int(day_demand["hora"].min())
        op_end = int(day_demand["hora"].max()) + 1  # exclusive
        mid = (op_start + op_end) // 2

        am_demand = day_demand[(day_demand["hora"] >= op_start) & (day_demand["hora"] < mid)]
        am_avg = am_demand["personas_requeridas"].mean() if not am_demand.empty else 0
        am_staff = int(np.ceil(am_avg * (1 + BUFFER_PCT)))

        pm_demand = day_demand[(day_demand["hora"] >= mid) & (day_demand["hora"] < op_end)]
        pm_avg = pm_demand["personas_requeridas"].mean() if not pm_demand.empty else 0
        pm_staff = int(np.ceil(pm_avg * (1 + BUFFER_PCT)))

        shifts[day] = {
            "AM": (op_start, mid, am_staff),
            "PM": (mid, op_end, pm_staff),
        }
    return shifts


def build_baseline_schedule(demand_df: pd.DataFrame, employees_df: pd.DataFrame) -> Dict:
    """
    Construye el schedule baseline: dos turnos constantes por día (AM y PM).

    Asume rotación equitativa: cada turno se cubre con un pool fijo rotando entre
    toda la plantilla. Algunos empleados terminan con >40h por la rotación + overtime
    forzado para cubrir picos donde el staffing constante no alcanza.

    Devuelve:
        - schedule_df: DataFrame con (emp_id, dia, hora, working=1/0)
        - hours_summary: horas semanales por empleado y desglose regular/overtime
        - cost_breakdown: dict con costos detallados
        - coverage_df: DataFrame con (dia, hora, requerido, asignado, gap, overstaff)
    """
    shifts_per_day = _staffing_per_shift(demand_df)
    employees = employees_df.to_dict("records")
    n_employees = len(employees)

    # Pool efectivamente disponible esta semana (vacaciones, incapacidades, etc.)
    n_available = max(1, int(np.ceil(n_employees * EFFECTIVE_POOL_PCT)))
    available_employees = employees[:n_available]  # los primeros N están disponibles

    schedule_rows = []
    coverage_rows = []
    weekly_hours = {e["id"]: 0.0 for e in employees}  # tracker para TODA la plantilla

    # Rotación independiente para AM y PM (ofrece variedad en asignación)
    rotation_idx = 0

    for day in DAYS:
        for shift_name in ["AM", "PM"]:
            start_h, end_h, staff = shifts_per_day[day][shift_name]
            # Asignar `staff` empleados rotando del pool DISPONIBLE (no toda la plantilla)
            emp_indices = [(rotation_idx + k) % n_available for k in range(staff)]
            rotation_idx = (rotation_idx + staff) % n_available
            emp_ids_shift = [available_employees[i]["id"] for i in emp_indices]

            for h in range(start_h, end_h):
                day_demand = demand_df[(demand_df["dia"] == day) & (demand_df["hora"] == h)]
                requerido = int(day_demand["personas_requeridas"].iloc[0])
                asignado = staff

                gap = max(0, requerido - asignado)
                overstaff = max(0, asignado - requerido)
                coverage_rows.append({
                    "dia": day, "hora": h, "requerido": requerido,
                    "asignado": asignado, "gap": gap, "overstaff": overstaff,
                })

                for emp_id in emp_ids_shift:
                    schedule_rows.append({
                        "emp_id": emp_id, "dia": day, "hora": h, "working": 1,
                    })
                    weekly_hours[emp_id] += 1

    coverage_df = pd.DataFrame(coverage_rows)
    total_gap_hours = coverage_df["gap"].sum()

    # Concentrar overtime en sub-grupo (~20%): supervisores y senior staff
    ot_pool_size = max(1, int(np.ceil(n_employees * OT_CONCENTRATION_PCT)))
    employees_for_ot = sorted(
        employees,
        key=lambda e: (0 if e["role"] == "Supervisor" else 1, e["id"])
    )[:ot_pool_size]
    ot_emp_ids = [e["id"] for e in employees_for_ot]

    overtime_added = {emp_id: 0.0 for emp_id in weekly_hours}
    rr_idx = 0
    gap_remaining = total_gap_hours
    while gap_remaining > 0 and ot_emp_ids:
        emp_id = ot_emp_ids[rr_idx % len(ot_emp_ids)]
        overtime_added[emp_id] += 1
        weekly_hours[emp_id] += 1
        gap_remaining -= 1
        rr_idx += 1
        if rr_idx > total_gap_hours * 3:
            break

    schedule_df = pd.DataFrame(schedule_rows)

    # Construir resumen de horas por empleado: regular (≤40h) + overtime (>40h)
    hours_rows = []
    for emp in employees:
        emp_id = emp["id"]
        total_h = weekly_hours[emp_id]
        regular_h = min(40.0, total_h)
        overtime_h = max(0.0, total_h - 40.0)
        hours_rows.append({
            "emp_id": emp_id,
            "name": emp["name"],
            "role": emp["role"],
            "hourly_rate": emp["hourly_rate"],
            "total_hours": total_h,
            "regular_hours": regular_h,
            "overtime_hours": overtime_h,
            "exceeds_legal_cap": overtime_h > 0,  # >40h ilegal post-reforma 2027
        })
    hours_summary = pd.DataFrame(hours_rows)

    # Costos
    hours_summary["cost_regular"] = hours_summary["regular_hours"] * hours_summary["hourly_rate"]
    hours_summary["cost_overtime"] = (
        hours_summary["overtime_hours"] * hours_summary["hourly_rate"] * OVERTIME_MULTIPLIER
    )
    hours_summary["cost_total"] = hours_summary["cost_regular"] + hours_summary["cost_overtime"]

    cost_breakdown = {
        "total_regular_hours":  float(hours_summary["regular_hours"].sum()),
        "total_overtime_hours": float(hours_summary["overtime_hours"].sum()),
        "cost_regular_mxn":     float(hours_summary["cost_regular"].sum()),
        "cost_overtime_mxn":    float(hours_summary["cost_overtime"].sum()),
        "cost_total_mxn":       float(hours_summary["cost_total"].sum()),
        "employees_over_40h":   int(hours_summary["exceeds_legal_cap"].sum()),
        "total_gap_personhours":     float(coverage_df["gap"].sum()),
        "total_overstaff_personhours": float(coverage_df["overstaff"].sum()),
    }

    return {
        "schedule_df": schedule_df,
        "hours_summary": hours_summary,
        "cost_breakdown": cost_breakdown,
        "coverage_df": coverage_df,
        "shifts_per_day": shifts_per_day,
    }


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.data_generator import generate_store_dataset

    ds = generate_store_dataset()
    baseline = build_baseline_schedule(ds["demand_df"], ds["employees_df"])

    print("=== STAFFING POR TURNO (baseline Excel/promedios) ===")
    for day, shifts in baseline["shifts_per_day"].items():
        am = shifts["AM"]
        pm = shifts["PM"]
        print(f"  {day:10s}: AM {am[0]:02d}-{am[1]:02d}h ({am[2]} personas) | PM {pm[0]:02d}-{pm[1]:02d}h ({pm[2]} personas)")

    print("\n=== DESGLOSE DE COSTOS BASELINE ===")
    cb = baseline["cost_breakdown"]
    print(f"  Horas regulares totales:  {cb['total_regular_hours']:>10.0f} h")
    print(f"  Horas extra totales:      {cb['total_overtime_hours']:>10.0f} h  (ILEGAL post-2027)")
    print(f"  Costo regular:            $ {cb['cost_regular_mxn']:>12,.0f} MXN")
    print(f"  Costo overtime:           $ {cb['cost_overtime_mxn']:>12,.0f} MXN")
    print(f"  COSTO TOTAL BASELINE:     $ {cb['cost_total_mxn']:>12,.0f} MXN/semana")
    print(f"  Empleados >40h:           {cb['employees_over_40h']} de {len(baseline['hours_summary'])}")
    print(f"  Sub-dotación (gap):       {cb['total_gap_personhours']:.0f} personas-hora")
    print(f"  Sobrestaffing:            {cb['total_overstaff_personhours']:.0f} personas-hora")

    print("\n=== TOP 10 EMPLEADOS CON MÁS HORAS ===")
    print(baseline["hours_summary"].sort_values("total_hours", ascending=False).head(10)[
        ["emp_id", "name", "role", "total_hours", "overtime_hours", "exceeds_legal_cap"]
    ].to_string(index=False))
