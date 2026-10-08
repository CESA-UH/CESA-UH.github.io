from sqlalchemy import create_engine, event, MetaData
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import BACKEND_DIR, settings

(BACKEND_DIR / "data").mkdir(exist_ok=True)
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
    echo=settings.DEBUG,
    pool_pre_ping=True,
)
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    metadata = MetaData(schema=settings.DATABASE_SCHEMA or None)


def get_db():
    with SessionLocal() as db:
        yield db
