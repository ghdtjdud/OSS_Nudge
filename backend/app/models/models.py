from datetime import datetime

from sqlalchemy import Column, BigInteger, String, DateTime

from backend.app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)

    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    name = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)
    guardian_phone = Column(String(30), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)