"""
Exporta datasets demo a CSV para usar como ejemplo de input cuando un usuario
quiere correr Aivena con datos de una tienda nueva.

Genera tres archivos:
  - demanda_demo.csv: tráfico/demanda por hora-día
  - empleados_demo.csv: plantilla
  - resultados_demo.csv: schedule optimizado (output de referencia)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_generator import generate_store_dataset
from src.comparator import run_comparison


def main(output_dir: str = "data"):
    os.makedirs(output_dir, exist_ok=True)
    ds = generate_store_dataset(store_name="Tienda Demo CDMX")

    # Inputs
    ds["demand_df"][["dia", "hora", "personas_requeridas"]].to_csv(
        os.path.join(output_dir, "demanda_demo.csv"), index=False
    )
    ds["employees_df"].to_csv(
        os.path.join(output_dir, "empleados_demo.csv"), index=False
    )

    # Output de referencia (lo que la herramienta produce)
    result = run_comparison(ds["demand_df"], ds["employees_df"], num_stores=50)

    schedule_out = result["optimized"]["schedule_df"].pivot_table(
        index="emp_id", columns=["dia", "hora"], values="working", fill_value=0
    )
    schedule_out.to_csv(os.path.join(output_dir, "schedule_optimizado_demo.csv"))

    print(f"Archivos generados en {output_dir}/:")
    for f in os.listdir(output_dir):
        path = os.path.join(output_dir, f)
        print(f"  {f}  ({os.path.getsize(path):,} bytes)")


if __name__ == "__main__":
    main()
