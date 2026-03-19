import csv
import re
import sys

def quote_val(val):
    if val is None or val.strip() == '':
        return 'NULL'
    # Escape single quotes
    val = val.replace("'", "''")
    return f"'{val}'"

def parse_num(val):
    if val is None or val.strip() == '':
        return 'NULL'
    # Remove commas and handle currency/percentage
    clean = val.replace(',', '').replace('$', '').replace('%', '').strip()
    try:
        if '.' in clean:
            return str(float(clean))
        return str(int(clean))
    except ValueError:
        return 'NULL'

def process_csv(filename, table_name, output_file, encoding='latin-1', custom_headers=None):
    with open(filename, 'r', encoding=encoding) as f:
        reader = csv.reader(f)
        headers = next(reader)
        
        if custom_headers:
            headers = custom_headers
        else:
            headers = [h.strip().lower().replace(' ', '_') for h in headers]
            
        rows = list(reader)
        
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"INSERT INTO {table_name} ({', '.join(headers)}) VALUES\n")
        
        for i, row in enumerate(rows):
            vals = []
            for j, val in enumerate(row):
                # Heuristic: if it's supposed to be numeric (looking at header or value)
                if 'superficie' in headers[j].lower() or 'consecutivo' in headers[j].lower() or 'dias' in headers[j].lower():
                    vals.append(parse_num(val))
                else:
                    vals.append(quote_val(val))
            
            line = f"({', '.join(vals)})"
            if i < len(rows) - 1:
                f.write(line + ",\n")
            else:
                f.write(line + ";\n")

# Process Environmental Zoning
process_csv(
    'ordenamientos_ecologicos_expedidos.csv',
    'environmental_zoning',
    'zoning_data.sql',
    encoding='latin-1'
)

# Process Income 2024
income_headers = [
    "consecutivo", "bitacora", "clave_proyecto", "promovente", "nombre_proyecto",
    "modalidad", "estatus", "fecha_ingreso", "fecha_resolucion", "resolucion",
    "quien_resolvio", "oficio_resolucion", "entidad_federativa_donde_ingreso",
    "entidad_federativa_resolucion", "estado", "municipio", "dias_laborables_transcurridos",
    "plazo_maximo_dias", "situacion_plazo", "sector"
]

process_csv(
    'ingresos_2024.csv',
    'ingresos_2024',
    'income_data.sql',
    encoding='latin-1',
    custom_headers=income_headers
)
