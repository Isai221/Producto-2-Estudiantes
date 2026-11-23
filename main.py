from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. CONFIGURACIÓN DE BASE DE DATOS
# ==========================================
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace('"', '').replace("'", "")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(DATABASE_URL)

# ==========================================
# 2. CONFIGURACIÓN DE SEGURIDAD (JWT)
# ==========================================
SECRET_KEY = os.getenv("JWT_SECRET", "clave_por_defecto_por_si_acaso")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI(title="API Escuela ITP Conecta", description="Backend completo con JWT y Roles")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ==========================================
# 3. MODELOS DE VALIDACIÓN (Pydantic)
# ==========================================
class EstudianteCreate(BaseModel):
    nombre: str
    email: str
    password: str
    fecha_nac: str = None

class EstudianteUpdate(BaseModel):
    nombre: str
    email: str

class CursoCreate(BaseModel):
    nombre: str
    creditos: int = 3

class InscripcionCreate(BaseModel):
    estudiante_id: int
    curso_id: int

class CalificacionCreate(BaseModel):
    inscripcion_id: int
    parcial: int
    calificacion: float

class PasswordReset(BaseModel):
    nueva_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# ==========================================
# 4. MIDDLEWARES (SEGURIDAD)
# ==========================================
def verificar_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def obtener_password_hash(password):
    return pwd_context.hash(password)

def crear_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verificar_rol(roles_permitidos: list):
    def role_checker(token: str = Depends(oauth2_scheme)):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("rol") not in roles_permitidos:
                raise HTTPException(status_code=403, detail="No tienes permisos suficientes")
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="El token ha expirado")
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Token inválido")
    return role_checker

# ==========================================
# 5. RUTAS DE LA API
# ==========================================

@app.get("/")
def inicio():
    return {"mensaje": "Servidor FastAPI funcionando."}

# --- Autenticación ---
@app.post("/registro")
def registrar_usuario(user: EstudianteCreate):
    with engine.connect() as conn:
        existe = conn.execute(text("SELECT id FROM estudiantes WHERE email = :email"), {"email": user.email}).fetchone()
        if existe:
            raise HTTPException(status_code=400, detail="El correo ya está registrado")
        
        # Forzamos rol ESTUDIANTE
        query = text("""
            INSERT INTO estudiantes (nombre, email, password_hash, rol, fecha_nac) 
            VALUES (:nombre, :email, :pass, CAST('ESTUDIANTE' AS "Rol"), CAST(:fecha AS DATE)) RETURNING id
        """)
        try:
            result = conn.execute(query, {
                "nombre": user.nombre, "email": user.email, "pass": obtener_password_hash(user.password), 
                "fecha": user.fecha_nac
            })
            conn.commit()
            return {"mensaje": "Usuario registrado exitosamente", "id": result.fetchone()[0]}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al guardar: {e}")

@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with engine.connect() as conn:
        user = conn.execute(text("SELECT id, password_hash, rol FROM estudiantes WHERE email = :email"), {"email": form_data.username}).fetchone()
        if not user or not verificar_password(form_data.password, user[1]):
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")
        return {"access_token": crear_token({"sub": str(user[0]), "rol": user[2]}), "token_type": "bearer"}

@app.get("/estudiante/perfil")
def ver_mi_perfil(payload: dict = Depends(verificar_rol(["ESTUDIANTE", "ADMIN"]))):
    with engine.connect() as conn:
        user = conn.execute(text("SELECT id, nombre, email, rol FROM estudiantes WHERE id = :id"), {"id": payload.get("sub")}).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return dict(user._mapping)

# --- CRUD ESTUDIANTES ---
@app.get("/admin/estudiantes")
def listar_estudiantes(payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, nombre, email, rol, fecha_nac, creado_en 
            FROM estudiantes ORDER BY id DESC
        """)).fetchall()
        return [dict(row._mapping) for row in result]

@app.delete("/admin/estudiantes/{id}")
def eliminar_estudiante(id: int, payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM estudiantes WHERE id = :id"), {"id": id})
        conn.commit()
        return {"mensaje": "Estudiante eliminado."}

@app.put("/admin/estudiantes/{id}/password")
def cambiar_password_estudiante(id: int, data: PasswordReset, payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        existe = conn.execute(text("SELECT id FROM estudiantes WHERE id = :id"), {"id": id}).fetchone()
        if not existe:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")
        
        hashed_pw = obtener_password_hash(data.nueva_password)
        conn.execute(text("UPDATE estudiantes SET password_hash = :pass WHERE id = :id"), {"pass": hashed_pw, "id": id})
        conn.commit()
        return {"mensaje": "Contraseña actualizada correctamente"}

@app.put("/admin/estudiantes/{id}")
def editar_estudiante(id: int, data: EstudianteUpdate, payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        # Verificamos que el correo no esté en uso por OTRO usuario
        existe_correo = conn.execute(
            text("SELECT id FROM estudiantes WHERE email = :email AND id != :id"), 
            {"email": data.email, "id": id}
        ).fetchone()
        if existe_correo:
            raise HTTPException(status_code=400, detail="El correo ya está en uso por otro estudiante.")
        
        conn.execute(
            text("UPDATE estudiantes SET nombre = :nombre, email = :email WHERE id = :id"),
            {"nombre": data.nombre, "email": data.email, "id": id}
        )
        conn.commit()
        return {"mensaje": "Datos del estudiante actualizados correctamente"}

# --- CRUD CURSOS ---
@app.get("/admin/cursos")
def listar_cursos(payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, nombre, creditos FROM cursos ORDER BY id DESC")).fetchall()
        return [dict(row._mapping) for row in result]

@app.post("/admin/cursos")
def crear_curso(curso: CursoCreate, payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        query = text("INSERT INTO cursos (nombre, creditos) VALUES (:nombre, :creditos) RETURNING id")
        result = conn.execute(query, {"nombre": curso.nombre, "creditos": curso.creditos})
        conn.commit()
        return {"mensaje": "Curso creado", "id": result.fetchone()[0]}

@app.delete("/admin/cursos/{id}")
def eliminar_curso(id: int, payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM cursos WHERE id = :id"), {"id": id})
        conn.commit()
        return {"mensaje": "Curso eliminado."}

# --- CRUD INSCRIPCIONES ---
@app.get("/admin/inscripciones")
def listar_inscripciones(payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        query = text("""
            SELECT i.id, e.nombre AS estudiante, c.nombre AS curso, i.fecha
            FROM inscripciones i
            JOIN estudiantes e ON e.id = i.estudiante_id
            JOIN cursos c ON c.id = i.curso_id
            ORDER BY i.id DESC
        """)
        result = conn.execute(query).fetchall()
        return [dict(row._mapping) for row in result]

@app.post("/admin/inscripciones")
def inscribir_estudiante(inscripcion: InscripcionCreate, payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        query = text("""
            INSERT INTO inscripciones (estudiante_id, curso_id) 
            VALUES (:est, :cur) ON CONFLICT (estudiante_id, curso_id) DO NOTHING RETURNING id
        """)
        result = conn.execute(query, {"est": inscripcion.estudiante_id, "cur": inscripcion.curso_id})
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=400, detail="El estudiante ya está inscrito en este curso.")
        return {"mensaje": "Inscripción exitosa", "id": result.fetchone()[0]}

@app.delete("/admin/inscripciones/{id}")
def eliminar_inscripcion(id: int, payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM inscripciones WHERE id = :id"), {"id": id})
        conn.commit()
        return {"mensaje": "Inscripción eliminada."}

# --- CRUD CALIFICACIONES ---
@app.get("/admin/calificaciones")
def listar_calificaciones(payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        query = text("""
            SELECT cal.id, e.nombre AS estudiante, c.nombre AS curso, cal.parcial, cal.calificacion
            FROM calificaciones cal
            JOIN inscripciones i ON i.id = cal.inscripcion_id
            JOIN estudiantes e ON e.id = i.estudiante_id
            JOIN cursos c ON c.id = i.curso_id
            ORDER BY cal.id DESC
        """)
        result = conn.execute(query).fetchall()
        return [dict(row._mapping) for row in result]

@app.post("/admin/calificaciones")
def registrar_calificacion(calif: CalificacionCreate, payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        existe = conn.execute(text("SELECT id FROM inscripciones WHERE id = :id"), {"id": calif.inscripcion_id}).fetchone()
        if not existe:
            raise HTTPException(status_code=400, detail="El ID de inscripción no existe.")
        
        query = text("""
            INSERT INTO calificaciones (inscripcion_id, parcial, calificacion) 
            VALUES (:ins, :par, :cal) RETURNING id
        """)
        result = conn.execute(query, {"ins": calif.inscripcion_id, "par": calif.parcial, "cal": calif.calificacion})
        conn.commit()
        return {"mensaje": "Calificación registrada", "id": result.fetchone()[0]}

@app.delete("/admin/calificaciones/{id}")
def eliminar_calificacion(id: int, payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM calificaciones WHERE id = :id"), {"id": id})
        conn.commit()
        return {"mensaje": "Calificación eliminada."}

# --- REPORTES (VISTAS) ---
@app.get("/reportes/promedios")
def ver_promedios(payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM vista_promedio_estudiante")).fetchall()
        return [dict(row._mapping) for row in result]

@app.get("/reportes/reprobados")
def ver_reprobados(payload: dict = Depends(verificar_rol(["ADMIN"]))):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM vista_reprobados")).fetchall()
        return [dict(row._mapping) for row in result]

# --- VISTA ESTUDIANTE ---
@app.get("/estudiante/mis_calificaciones")
def ver_mis_calificaciones(payload: dict = Depends(verificar_rol(["ESTUDIANTE"]))):
    with engine.connect() as conn:
        query = text("""
            SELECT c.nombre AS curso, cal.parcial, cal.calificacion
            FROM calificaciones cal
            JOIN inscripciones i ON i.id = cal.inscripcion_id
            JOIN cursos c ON c.id = i.curso_id
            WHERE i.estudiante_id = :id
            ORDER BY c.nombre, cal.parcial
        """)
        result = conn.execute(query, {"id": payload.get("sub")}).fetchall()
        return [dict(row._mapping) for row in result]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)