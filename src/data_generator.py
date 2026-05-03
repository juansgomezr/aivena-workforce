"""
Generador de datos sintéticos calibrados a retail mexicano genérico.

Supuestos documentados:
- Tienda con ~80 FTEs, operación domingo a domingo
- Lunes-sábado: 9:00 - 21:00 (12h operativas)
- Domingo: 10:00 - 20:00 (10h operativas)
- Mix de roles típico: cajeros (38%), piso (31%), inventario (19%), supervisores (12%)
- Salarios base alineados a SMG México 2026 + retención retail
- Curvas de tráfico calibradas a patrones observados públicamente
  (picos de almuerzo y after-work, sábado como día más fuerte)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple

# ---------- CONSTANTES DE NEGOCIO ----------

DAYS = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
DAY_INDEX = {d: i for i, d in enumerate(DAYS)}

# Horario operativo por día (start_hour, end_hour) — formato 24h
OPERATING_HOURS = {
    "Domingo":   (10, 20),
    "Lunes":     (9, 21),
    "Martes":    (9, 21),
    "Miércoles": (9, 21),
    "Jueves":    (9, 21),
    "Viernes":   (9, 21),
    "Sábado":    (9, 21),
}

# Factor de demanda por (día, hora) — 0.0 a 1.0
# Valor 1.0 = peak absoluto del retailer (sábado 13:00)
DEMAND_FACTORS = {
    "Domingo": {
        10: 0.55, 11: 0.70, 12: 0.85, 13: 0.95, 14: 0.90,
        15: 0.80, 16: 0.75, 17: 0.70, 18: 0.55, 19: 0.40
    },
    "Lunes": {
        9: 0.30, 10: 0.40, 11: 0.50, 12: 0.60, 13: 0.70, 14: 0.65,
        15: 0.50, 16: 0.55, 17: 0.75, 18: 0.85, 19: 0.70, 20: 0.50
    },
    "Martes": {
        9: 0.30, 10: 0.40, 11: 0.50, 12: 0.60, 13: 0.70, 14: 0.65,
        15: 0.50, 16: 0.55, 17: 0.75, 18: 0.85, 19: 0.70, 20: 0.50
    },
    "Miércoles": {
        9: 0.32, 10: 0.42, 11: 0.52, 12: 0.62, 13: 0.72, 14: 0.67,
        15: 0.52, 16: 0.57, 17: 0.77, 18: 0.87, 19: 0.72, 20: 0.52
    },
    "Jueves": {
        9: 0.35, 10: 0.45, 11: 0.55, 12: 0.65, 13: 0.72, 14: 0.68,
        15: 0.55, 16: 0.60, 17: 0.80, 18: 0.88, 19: 0.75, 20: 0.55
    },
    "Viernes": {
        9: 0.40, 10: 0.50, 11: 0.55, 12: 0.65, 13: 0.70, 14: 0.65,
        15: 0.55, 16: 0.65, 17: 0.85, 18: 0.95, 19: 0.80, 20: 0.65
    },
    "Sábado": {
        9: 0.50, 10: 0.65, 11: 0.80, 12: 0.95, 13: 1.00, 14: 0.95,
        15: 0.85, 16: 0.85, 17: 0.90, 18: 0.85, 19: 0.70, 20: 0.55
    },
}

# Personas requeridas en piso por unidad de demanda
# Peak (factor=1.0) = 45 personas; valle (factor=0.3) ≈ 14 personas
PEAK_STAFFING = 45

# Mix de roles y salarios (MXN/hora)
# Salarios base alineados a retail mexicano post-SMG 2026
ROLE_DISTRIBUTION = {
    "Cajero":        {"count": 30, "hourly_rate": 50},
    "Piso de venta": {"count": 25, "hourly_rate": 55},
    "Inventario":    {"count": 15, "hourly_rate": 60},
    "Supervisor":    {"count": 10, "hourly_rate": 90},
}

# Multiplicador de horas extra (LFT México: doble las primeras 9h extra/sem, triple después)
OVERTIME_MULTIPLIER = 2.0


# ---------- ESTRUCTURAS DE DATOS ----------

@dataclass
class Employee:
    id: str
    name: str
    role: str
    hourly_rate: float

    def to_dict(self):
        return asdict(self)


# ---------- GENERADORES ----------

def generate_demand_curve() -> pd.DataFrame:
    """
    Devuelve DataFrame con columnas: dia, hora, factor, personas_requeridas
    Una fila por cada hora operativa de la semana (82 filas en total).
    """
    rows = []
    for day in DAYS:
        for hour, factor in DEMAND_FACTORS[day].items():
            personas = max(1, round(PEAK_STAFFING * factor))
            rows.append({
                "dia": day,
                "dia_idx": DAY_INDEX[day],
                "hora": hour,
                "factor_demanda": factor,
                "personas_requeridas": personas,
            })
    return pd.DataFrame(rows)


def generate_employees() -> List[Employee]:
    """Genera plantilla de 80 FTEs con mix de roles típico de retail."""
    employees = []
    counter = 1
    nombres_pool = [
        "García", "Hernández", "López", "Martínez", "Rodríguez", "Pérez",
        "González", "Sánchez", "Ramírez", "Torres", "Flores", "Rivera",
        "Gómez", "Díaz", "Reyes", "Morales", "Jiménez", "Ruiz",
        "Álvarez", "Mendoza", "Castillo", "Vázquez", "Romero", "Aguilar",
        "Vargas", "Castro", "Ortiz", "Ramos", "Domínguez", "Guerrero",
        "Medina", "Silva", "Núñez", "Salazar", "Rojas", "Soto",
        "Contreras", "Luna", "Cruz", "Cortés", "Peña", "Delgado",
        "León", "Carrillo", "Vega", "Espinoza", "Padilla", "Cabrera",
    ]
    primeros = [
        "Ana", "Luis", "María", "Carlos", "Sofía", "Diego", "Valentina",
        "José", "Camila", "Miguel", "Daniela", "Jorge", "Fernanda", "Andrés",
        "Lucía", "Ricardo", "Paola", "Javier", "Adriana", "Eduardo",
    ]

    rng = np.random.default_rng(seed=42)

    for role, props in ROLE_DISTRIBUTION.items():
        for i in range(props["count"]):
            first = rng.choice(primeros)
            last = rng.choice(nombres_pool)
            emp = Employee(
                id=f"E{counter:03d}",
                name=f"{first} {last}",
                role=role,
                hourly_rate=props["hourly_rate"],
            )
            employees.append(emp)
            counter += 1

    return employees


def employees_to_df(employees: List[Employee]) -> pd.DataFrame:
    return pd.DataFrame([e.to_dict() for e in employees])


def operating_hours_for(day: str) -> List[int]:
    """Devuelve la lista de horas operativas para un día dado."""
    start, end = OPERATING_HOURS[day]
    return list(range(start, end))


# ---------- GENERADOR DE TIENDA COMPLETA (entry-point) ----------

def generate_store_dataset(store_name: str = "Tienda Demo") -> Dict:
    """
    Genera un dataset completo de tienda lista para alimentar al optimizador.
    Devuelve un dict con: demand_df, employees_df, store_meta.
    """
    demand_df = generate_demand_curve()
    employees = generate_employees()
    employees_df = employees_to_df(employees)

    store_meta = {
        "store_name": store_name,
        "num_employees": len(employees),
        "operating_days": 7,
        "weekly_operating_hours": sum(
            len(operating_hours_for(d)) for d in DAYS
        ),
        "peak_staffing": PEAK_STAFFING,
        "overtime_multiplier": OVERTIME_MULTIPLIER,
    }

    return {
        "demand_df": demand_df,
        "employees_df": employees_df,
        "store_meta": store_meta,
    }


if __name__ == "__main__":
    ds = generate_store_dataset()
    print("=== DEMAND CURVE ===")
    print(ds["demand_df"].head(15))
    print(f"\nTotal horas operativas/semana: {ds['demand_df']['hora'].count()}")
    print(f"Total personas-hora requeridas: {ds['demand_df']['personas_requeridas'].sum()}")
    print(f"\n=== EMPLEADOS ===")
    print(ds["employees_df"].groupby("role").agg(
        count=("id", "count"),
        avg_rate=("hourly_rate", "mean")
    ))
    print(f"\n=== STORE META ===")
    for k, v in ds["store_meta"].items():
        print(f"  {k}: {v}")
