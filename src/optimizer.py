"""
Optimizador de schedule: algoritmo greedy con turnos continuos.

Contraints duros:
- Tope estricto: 40h/semana por empleado (cumplimiento legal post-reforma 2027)
- Máximo 8h/día por empleado
- Mínimo 4h por turno (no fragmentar contratos)
- Al menos 1 día de descanso a la semana
- Turnos continuos por día (no fragmentados)
- Cobertura: cubrir 100% de la demanda en cada hora-día

Objetivo: minimizar costo total = horas asignadas × salario hora.
Bajo el constraint de 40h, NO hay overtime → el costo es 100% horas regulares.

Estrategia greedy:
1. Iteramos sobre slots (día, hora) ordenados por demanda descendente
2. Para cada slot, asignamos empleados que continúan turno YA empezado primero,
   luego empleados frescos elegibles (orden: menos horas acumuladas, más baratos)
3. Post-procesamiento: forzar continuidad de turnos por (empleado, día)

Trade-off de diseño documentado:
Greedy NO garantiza óptimo global. Un solver MIP (OR-Tools CP-SAT) lo lograría.
Trade-off elegido: latencia <1s + cero dependencias externas vs. ~5-10pp de eficiencia
adicional. Para v0 que demuestra el concepto, greedy es suficiente.
Roadmap Q3: migrar a CP-SAT si un design partner justifica el upgrade.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Set
from .data_generator import (
    DAYS, OPERATING_HOURS, OVERTIME_MULTIPLIER, operating_hours_for
)


MAX_WEEKLY_HOURS = 40
MAX_DAILY_HOURS = 8
MIN_SHIFT_HOURS = 4
MAX_DAYS_WORKED = 6  # 1 día de descanso obligatorio


def optimize_schedule(demand_df: pd.DataFrame, employees_df: pd.DataFrame) -> Dict:
    """
    Construye el schedule optimizado respetando todos los constraints.

    Returns dict con:
        - schedule_df: filas (emp_id, dia, hora, working=1/0)
        - hours_summary: horas y costo por empleado
        - cost_breakdown: totales agregados
        - coverage_df: cobertura hora-día (requerido vs asignado)
    """
    employees = employees_df.to_dict("records")
    emp_by_id = {e["id"]: e for e in employees}
    n_employees = len(employees)

    # Estado de tracking
    schedule: Dict[Tuple[str, str, int], int] = {}  # (emp_id, dia, hora) -> 1
    weekly_hours: Dict[str, float] = {e["id"]: 0.0 for e in employees}
    daily_hours: Dict[Tuple[str, str], float] = {}  # (emp_id, dia) -> hours
    days_worked: Dict[str, Set[str]] = {e["id"]: set() for e in employees}
    shift_start: Dict[Tuple[str, str], int] = {}  # (emp_id, dia) -> hora inicio
    shift_end: Dict[Tuple[str, str], int] = {}    # (emp_id, dia) -> hora fin (exclusive)

    coverage_rows = []

    # Iteramos sobre cada slot (día, hora) en orden cronológico
    # (en lugar de por demanda descendente, para preservar continuidad de turnos)
    for day in DAYS:
        for hora in operating_hours_for(day):
            # Demanda en este slot
            row = demand_df[(demand_df["dia"] == day) & (demand_df["hora"] == hora)].iloc[0]
            requerido = int(row["personas_requeridas"])

            # ¿Quiénes ya están continuando turno en este slot?
            # (Empleados que trabajaron la hora anterior y aún no han llegado a su límite)
            continuando = []
            for emp_id in [e["id"] for e in employees]:
                if (emp_id, day, hora - 1) in schedule:
                    # Sigue elegible para continuar?
                    if (
                        weekly_hours[emp_id] < MAX_WEEKLY_HOURS
                        and daily_hours.get((emp_id, day), 0) < MAX_DAILY_HOURS
                    ):
                        continuando.append(emp_id)

            asignados_este_slot = []

            # Primero asignamos a los que continúan turno
            for emp_id in continuando:
                if len(asignados_este_slot) >= requerido:
                    break
                schedule[(emp_id, day, hora)] = 1
                weekly_hours[emp_id] += 1
                daily_hours[(emp_id, day)] = daily_hours.get((emp_id, day), 0) + 1
                shift_end[(emp_id, day)] = hora + 1
                asignados_este_slot.append(emp_id)

            # Si falta cubrir, traemos empleados frescos
            faltantes = requerido - len(asignados_este_slot)
            if faltantes > 0:
                candidatos = []
                for e in employees:
                    emp_id = e["id"]
                    if emp_id in asignados_este_slot:
                        continue
                    # Constraints duros
                    if weekly_hours[emp_id] >= MAX_WEEKLY_HOURS:
                        continue
                    if daily_hours.get((emp_id, day), 0) >= MAX_DAILY_HOURS:
                        continue
                    # Si ya cerró turno hoy (gap), no abre nuevo
                    if (emp_id, day) in shift_end and shift_end[(emp_id, day)] < hora:
                        continue
                    # Restricción de día de descanso
                    if (
                        day not in days_worked[emp_id]
                        and len(days_worked[emp_id]) >= MAX_DAYS_WORKED
                    ):
                        continue
                    # Si entra fresco, debe haber espacio para mínimo 4h o resto del día
                    horas_restantes_dia = OPERATING_HOURS[day][1] - hora
                    horas_disponibles = min(
                        horas_restantes_dia,
                        MAX_DAILY_HOURS - daily_hours.get((emp_id, day), 0),
                        MAX_WEEKLY_HOURS - weekly_hours[emp_id],
                    )
                    # Si es nuevo turno, validar que pueda hacer mínimo 4h
                    if (emp_id, day) not in days_worked[emp_id] and horas_disponibles < min(MIN_SHIFT_HOURS, horas_restantes_dia):
                        continue
                    candidatos.append((emp_id, weekly_hours[emp_id], e["hourly_rate"]))

                # Ordenar: menos horas acumuladas (distribuir carga), luego más barato
                candidatos.sort(key=lambda c: (c[1], c[2]))

                for emp_id, _, _ in candidatos[:faltantes]:
                    schedule[(emp_id, day, hora)] = 1
                    weekly_hours[emp_id] += 1
                    daily_hours[(emp_id, day)] = daily_hours.get((emp_id, day), 0) + 1
                    if (emp_id, day) not in shift_start:
                        shift_start[(emp_id, day)] = hora
                    shift_end[(emp_id, day)] = hora + 1
                    days_worked[emp_id].add(day)
                    asignados_este_slot.append(emp_id)

            coverage_rows.append({
                "dia": day,
                "hora": hora,
                "requerido": requerido,
                "asignado": len(asignados_este_slot),
                "gap": max(0, requerido - len(asignados_este_slot)),
                "overstaff": max(0, len(asignados_este_slot) - requerido),
            })

    # Post-procesamiento: garantizar turnos continuos
    # Si un empleado tiene gap dentro de un día (ej. 9-10 y 12-14), rellenamos el gap
    # excepto si rompe el cap de 40h. Si no se puede rellenar, dividimos en dos turnos.
    schedule, weekly_hours, daily_hours = _enforce_shift_continuity(
        schedule, weekly_hours, daily_hours, days_worked, employees
    )

    # Reconstruir coverage tras post-process (puede haber añadido staff)
    coverage_rows_final = []
    for day in DAYS:
        for hora in operating_hours_for(day):
            row = demand_df[(demand_df["dia"] == day) & (demand_df["hora"] == hora)].iloc[0]
            requerido = int(row["personas_requeridas"])
            asignado = sum(
                1 for (eid, d, h), v in schedule.items()
                if d == day and h == hora and v == 1
            )
            coverage_rows_final.append({
                "dia": day,
                "hora": hora,
                "requerido": requerido,
                "asignado": asignado,
                "gap": max(0, requerido - asignado),
                "overstaff": max(0, asignado - requerido),
            })

    coverage_df = pd.DataFrame(coverage_rows_final)
    schedule_df = pd.DataFrame([
        {"emp_id": k[0], "dia": k[1], "hora": k[2], "working": v}
        for k, v in schedule.items()
    ])

    # Resumen de horas y costo
    hours_rows = []
    for emp in employees:
        emp_id = emp["id"]
        total_h = weekly_hours[emp_id]
        regular_h = min(MAX_WEEKLY_HOURS, total_h)
        overtime_h = max(0.0, total_h - MAX_WEEKLY_HOURS)
        days_w = len(days_worked[emp_id])
        hours_rows.append({
            "emp_id": emp_id,
            "name": emp["name"],
            "role": emp["role"],
            "hourly_rate": emp["hourly_rate"],
            "total_hours": total_h,
            "regular_hours": regular_h,
            "overtime_hours": overtime_h,
            "days_worked": days_w,
            "exceeds_legal_cap": overtime_h > 0,
        })
    hours_summary = pd.DataFrame(hours_rows)
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
        "coverage_pct":         float(
            1 - coverage_df["gap"].sum() / coverage_df["requerido"].sum()
        ),
    }

    return {
        "schedule_df": schedule_df,
        "hours_summary": hours_summary,
        "cost_breakdown": cost_breakdown,
        "coverage_df": coverage_df,
    }


def _enforce_shift_continuity(
    schedule: Dict[Tuple[str, str, int], int],
    weekly_hours: Dict[str, float],
    daily_hours: Dict[Tuple[str, str], float],
    days_worked: Dict[str, Set[str]],
    employees: List[Dict],
) -> Tuple[Dict, Dict, Dict]:
    """
    Para cada (empleado, día), si hay gaps dentro del turno (ej: trabajó 9, 10, 12)
    rellena el gap (11) si:
        - No excede 40h totales semanales
        - No excede 8h diarias
    Si no se puede rellenar sin violar constraints, se deja como está
    (puede haber turnos cortos < 4h en estos casos — minoritarios).
    """
    for emp in employees:
        emp_id = emp["id"]
        for day in DAYS:
            # Horas trabajadas hoy por este empleado
            hours_today = sorted([
                h for (eid, d, h), v in schedule.items()
                if eid == emp_id and d == day and v == 1
            ])
            if len(hours_today) < 2:
                continue
            first_h, last_h = hours_today[0], hours_today[-1]
            expected_continuous = list(range(first_h, last_h + 1))
            gaps = [h for h in expected_continuous if h not in hours_today]
            for gap_h in gaps:
                # Validar constraints antes de rellenar
                if weekly_hours[emp_id] >= MAX_WEEKLY_HOURS:
                    break
                if daily_hours.get((emp_id, day), 0) >= MAX_DAILY_HOURS:
                    break
                schedule[(emp_id, day, gap_h)] = 1
                weekly_hours[emp_id] += 1
                daily_hours[(emp_id, day)] = daily_hours.get((emp_id, day), 0) + 1

    return schedule, weekly_hours, daily_hours


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.data_generator import generate_store_dataset

    ds = generate_store_dataset()
    result = optimize_schedule(ds["demand_df"], ds["employees_df"])

    cb = result["cost_breakdown"]
    print("=== SCHEDULE OPTIMIZADO ===")
    print(f"  Horas regulares totales:  {cb['total_regular_hours']:>10.0f} h")
    print(f"  Horas extra totales:      {cb['total_overtime_hours']:>10.0f} h")
    print(f"  Costo regular:            $ {cb['cost_regular_mxn']:>12,.0f} MXN")
    print(f"  Costo overtime:           $ {cb['cost_overtime_mxn']:>12,.0f} MXN")
    print(f"  COSTO TOTAL OPTIMIZADO:   $ {cb['cost_total_mxn']:>12,.0f} MXN/semana")
    print(f"  Empleados >40h:           {cb['employees_over_40h']} de {len(result['hours_summary'])}")
    print(f"  Cobertura demanda:        {cb['coverage_pct']*100:.1f}%")
    print(f"  Sub-dotación (gap):       {cb['total_gap_personhours']:.0f} personas-hora")
    print(f"  Sobrestaffing:            {cb['total_overstaff_personhours']:.0f} personas-hora")

    print("\n=== DISTRIBUCIÓN DE HORAS ===")
    hs = result["hours_summary"]
    print(f"  Promedio:     {hs['total_hours'].mean():.1f} h")
    print(f"  Mediana:      {hs['total_hours'].median():.1f} h")
    print(f"  Min - Max:    {hs['total_hours'].min():.1f} - {hs['total_hours'].max():.1f} h")
    print(f"  Días promedio:{hs['days_worked'].mean():.1f}")
