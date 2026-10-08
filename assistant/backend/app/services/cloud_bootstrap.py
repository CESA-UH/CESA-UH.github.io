"""Idempotent cloud setup. Credentials are supplied as private deployment environment variables."""
import re
from sqlalchemy import select
from sqlalchemy.schema import CreateSchema
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_password
from app.models import User, UserRole, SiteCourse
from app.services.site_import import sync_site


def prepare_database(engine):
    schema=settings.DATABASE_SCHEMA
    if schema and not re.fullmatch(r'[a-z][a-z0-9_]{0,62}',schema):
        raise RuntimeError('Invalid database schema')
    if settings.CLOUD_DEPLOYMENT:
        if engine.dialect.name!='postgresql' or schema!='hamdars':
            raise RuntimeError('Cloud deployment requires PostgreSQL in the private hamdars schema')
        if not settings.JWT_SECRET_KEY or len(settings.JWT_SECRET_KEY)<32:
            raise RuntimeError('Cloud deployment requires a persistent JWT secret of at least 32 characters')
        if settings.SITE_FILE_STORAGE!='supabase' or not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            raise RuntimeError('Persistent cloud file storage is not configured')
    if schema:
        if engine.dialect.name!='postgresql':
            raise RuntimeError('Named database schemas require PostgreSQL')
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema,if_not_exists=True))


def initialize_cloud(engine):
    if not settings.CLOUD_DEPLOYMENT:return
    with Session(engine) as db:
        admin=db.scalar(select(User).where(User.role==UserRole.ADMIN).order_by(User.id))
        if not admin:
            email=settings.BOOTSTRAP_ADMIN_EMAIL.strip().lower()
            password=settings.BOOTSTRAP_ADMIN_PASSWORD
            if '@' not in email or len(password)<12 or len(password)>128:
                raise RuntimeError('Set a valid bootstrap admin email and a password of at least 12 characters')
            if db.scalar(select(User.id).where(User.email==email)):
                raise RuntimeError('Bootstrap email belongs to another account; select a new administrator email')
            admin=User(email=email,first_name='مدیر',last_name='سامانه',role=UserRole.ADMIN,password_hash=hash_password(password))
            db.add(admin);db.commit()
        if not db.scalar(select(SiteCourse.key).limit(1)):
            sync_site(db,settings.ECE_DOCS_PATH,admin)
            db.commit()
