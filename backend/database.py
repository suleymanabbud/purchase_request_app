from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# استخدم SQLite كبداية، ويمكن استبداله بقاعدة أخرى (PostgreSQL/MySQL) بسهولة
DATABASE_URL = "sqlite:///./database/purchase_requests.db"

# ل SQLite فقط: نحتاج هذا الخيار لتجاوز قيود الـ thread
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()
