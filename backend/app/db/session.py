from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from opensearchpy import OpenSearch
from app.core.config import settings
import os

# SQL Database (PostgreSQL)
pool_size = settings.DB_POOL_SIZE
engine = create_engine(
    settings.DATABASE_URL, pool_size=pool_size, max_overflow=10, pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# OpenSearch
os_client = OpenSearch([settings.OPENSEARCH_URL])


# Dependency to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
