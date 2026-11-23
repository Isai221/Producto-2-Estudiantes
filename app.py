import os
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

VISTAS_PERMITIDAS = {
    "vista_promedio_estudiante",
    "vista_cursos_inscritos",
    "vista_boleta_estudiante",
    "vista_reprobados",
}

def conectar():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def insertar_estudiante(nombre, email, fecha_nac=None):
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO estudiantes (nombre, email, fecha_nac)
                VALUES (%s, %s, %s)
                RETURNING id, nombre, email, fecha_nac;
                """,
                (nombre, email, fecha_nac),
            )
            return cur.fetchone()

def inscribir(estudiante_id, curso_id):
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inscripciones (estudiante_id, curso_id)
                VALUES (%s, %s)
                ON CONFLICT (estudiante_id, curso_id) DO NOTHING
                RETURNING id;
                """,
                (estudiante_id, curso_id),
            )
            return cur.fetchone()

def registrar_calificacion(inscripcion_id, parcial, calificacion):
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO calificaciones (inscripcion_id, parcial, calificacion)
                VALUES (%s, %s, %s)
                RETURNING id, parcial, calificacion;
                """,
                (inscripcion_id, parcial, calificacion),
            )
            return cur.fetchone()

def consultar_vista(nombre_vista):
    if nombre_vista not in VISTAS_PERMITIDAS:
        raise ValueError("Vista no permitida")
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {nombre_vista};")
            return cur.fetchall()

def imprimir_tabla(filas):
    if not filas:
        print("No hay datos para mostrar.")
        return
    for fila in filas:
        print(dict(fila))

def procesar_fecha(fecha_str):
    if not fecha_str:
        return None
    formatos = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]
    for formato in formatos:
        try:
            fecha_obj = datetime.strptime(fecha_str, formato)
            return fecha_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Formato de fecha no válido: '{fecha_str}'. Usa YYYY-MM-DD (ej. 2004-11-22)")

def buscar_curso_id(curso_input):
    """Permite buscar un curso por su ID numérico o por su nombre."""
    try:
        # Si el usuario escribió un número, lo usamos directamente
        return int(curso_input)
    except ValueError:
        # Si escribió texto, buscamos en la base de datos por nombre
        with conectar() as conn:
            with conn.cursor() as cur:
                # ILIKE busca sin importar mayúsculas/minúsculas. El % permite búsquedas parciales
                cur.execute("SELECT id FROM cursos WHERE nombre ILIKE %s;", (f"%{curso_input}%",))
                resultado = cur.fetchone()
                if resultado:
                    return resultado['id']
                else:
                    raise ValueError(f"No existe un curso llamado '{curso_input}'")

def menu():
    while True:
        print("\n=== ESCUELA ITP CONECTA ===")
        print("1. Registrar estudiante")
        print("2. Inscribir estudiante")
        print("3. Registrar calificación")
        print("4. Promedio por estudiante")
        print("5. Cursos e inscritos")
        print("6. Boleta detallada")
        print("7. Alumnos reprobados (< 6.0)")
        print("8. Salir")
        
        opcion = input("Opción: ")
        
        try:
            if opcion == "1":
                nombre = input("Nombre: ")
                email = input("Email: ")
                fecha_raw = input("Fecha nacimiento YYYY-MM-DD (opcional): ")
                fecha = procesar_fecha(fecha_raw) if fecha_raw else None
                resultado = insertar_estudiante(nombre, email, fecha)
                print("✅ Estudiante registrado:", dict(resultado))
                
            elif opcion == "2":
                estudiante_id = int(input("ID estudiante: "))
                curso_input = input("ID o nombre del curso: ").strip()
                
                # Aquí usamos la nueva función para obtener el ID del curso
                curso_id = buscar_curso_id(curso_input)
                
                resultado = inscribir(estudiante_id, curso_id)
                if resultado:
                    print(f"✅ Estudiante inscrito correctamente en el curso (ID: {curso_id}).")
                else:
                    print("⚠️ El estudiante ya estaba inscrito en este curso.")
                    
            elif opcion == "3":
                inscripcion_id = int(input("ID inscripción: "))
                parcial = int(input("Parcial (1, 2, 3...): "))
                calificacion = float(input("Calificación (0-10): "))
                resultado = registrar_calificacion(inscripcion_id, parcial, calificacion)
                print("✅ Calificación registrada:", dict(resultado))
                
            elif opcion == "4":
                print("\n--- PROMEDIO POR ESTUDIANTE ---")
                imprimir_tabla(consultar_vista("vista_promedio_estudiante"))
                
            elif opcion == "5":
                print("\n--- CURSOS E INSCRITOS ---")
                imprimir_tabla(consultar_vista("vista_cursos_inscritos"))
                
            elif opcion == "6":
                print("\n--- BOLETA DETALLADA ---")
                imprimir_tabla(consultar_vista("vista_boleta_estudiante"))
                
            elif opcion == "7":
                print("\n--- ALUMNOS REPROBADOS ---")
                imprimir_tabla(consultar_vista("vista_reprobados"))
                
            elif opcion == "8":
                print("Práctica finalizada.")
                break
            else:
                print("⚠️ Opción no válida. Elige del 1 al 8.")
                
        except ValueError as e:
            print(f"❌ Error de validación: {e}")
        except Exception as error:
            print("❌ Error en la base de datos:", error)

if __name__ == "__main__":
    menu()