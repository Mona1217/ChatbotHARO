# storage/db.py — PostgreSQL con SQLAlchemy Core (sin ORM)
from typing import Optional, Tuple
from datetime import datetime
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, DateTime, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import select
from sqlalchemy.engine import Engine, Result
from config import settings

# Engine con pool y health-check
engine: Engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,           # detecta conexiones muertas
    pool_size=5,                  # ajusta a tu carga
    max_overflow=10,              # conexiones extra cuando hay picos
)

metadata = MetaData(schema=None)  # usa schema público; pon schema="tu_schema" si usas otro

students = Table(
    "students", metadata,
    Column("id", Integer, primary_key=True),
    Column("full_name", String(200), nullable=False),
    Column("doc_id", String(64), nullable=False, unique=True, index=True),
    Column("phone", String(32)),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow)
)

consents = Table(
    "consents", metadata,
    Column("id", Integer, primary_key=True),
    Column("student_id", Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("source", String(32), nullable=False, default="whatsapp"),
    Column("text", Text, nullable=False),
    Column("accepted_at", DateTime, nullable=False, default=datetime.utcnow)
)

appointments = Table(
    "appointments", metadata,
    Column("id", Integer, primary_key=True),
    Column("student_id", Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("plate", String(20)),
    Column("date", String(10)),   # YYYY-MM-DD (si prefieres Date real, usa Date)
    Column("time", String(5)),    # HH:MM (si prefieres Time real, usa Time)
    Column("type", String(16)),   # 'practica' | 'teorico'
    Column("status", String(16), nullable=False, default="pendiente"),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow)
)

def init_db():
    """Crea tablas si no existen (equivalente a migrate inicial simple)."""
    metadata.create_all(engine)

# ============== Repositorio de funciones que tu bot ya usa ==============

def upsert_student(full_name: str, doc_id: str, phone: Optional[str]) -> int:
    """
    Inserta o actualiza por doc_id. Devuelve student_id.
    """
    with engine.begin() as conn:
        stmt = pg_insert(students).values(
            full_name=full_name,
            doc_id=doc_id,
            phone=phone
        ).on_conflict_do_update(
            index_elements=[students.c.doc_id],
            set_=dict(full_name=full_name, phone=phone)
        ).returning(students.c.id)
        sid = conn.execute(stmt).scalar_one()
    return sid

def add_consent(student_id: int, text: str, source: str = "whatsapp"):
    with engine.begin() as conn:
        conn.execute(consents.insert().values(
            student_id=student_id,
            source=source,
            text=text
        ))

def create_appointment(student_id: int, plate: str, date: str, time: str, atype: str):
    with engine.begin() as conn:
        conn.execute(appointments.insert().values(
            student_id=student_id,
            plate=plate,
            date=date,
            time=time,
            type=atype,
            status="pendiente"
        ))

def find_student_by_doc(doc_id: str) -> Optional[Tuple[int, str, Optional[str]]]:
    with engine.begin() as conn:
        result: Result = conn.execute(
            select(students.c.id, students.c.full_name, students.c.phone)
            .where(students.c.doc_id == doc_id)
            .limit(1)
        )
        row = result.fetchone()
        if row:
            return row[0], row[1], row[2]
        return None
