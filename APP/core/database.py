from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from APP.core.config import settings

# pool_pre_ping=True ensures stale connections are detected and recycled automatically
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency that provides a database session and ensures it is closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
