import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Boolean
from app.db.session import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="User", nullable=False)  # "Admin" o "User"
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)



class SignatureRequest(Base):
    __tablename__ = "signature_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reference = Column(String(100), index=True, nullable=True)
    subject = Column(String(255), nullable=True)
    message = Column(Text, nullable=True)

    sender_user_code = Column(String(100), nullable=True)
    sender_entity_code = Column(String(100), nullable=True)
    addressee_user_code = Column(String(100), nullable=True)
    addressee_entity_code = Column(String(100), nullable=True)
    addressee_action = Column(String(50), default="SIGN")

    # Códigos retornados por Firma GOB
    firmagob_code = Column(String(100), nullable=True)
    public_access_id = Column(String(100), index=True, nullable=True)
    document_id = Column(String(100), index=True, nullable=True)

    # Archivos
    original_filename = Column(String(255), nullable=True)
    original_file_path = Column(String(500), nullable=True)
    signed_file_path = Column(String(500), nullable=True)

    # Estados: PENDING, IN_PROCESS, COMPLETED, REJECTED, ERROR
    status = Column(String(50), default="PENDING", index=True)
    error_message = Column(Text, nullable=True)

    # Auditoría JSON
    raw_request = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)
    raw_callback = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
