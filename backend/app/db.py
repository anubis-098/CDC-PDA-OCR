from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from datetime import datetime, timezone

from .config import settings


class Base(DeclarativeBase):
    pass


def now():
    return datetime.now(timezone.utc)


class Comparison(Base):
    __tablename__ = "comparisons"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[dict] = mapped_column(JSON)
    documents: Mapped[list["Document"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("comparisons.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(255))
    ocr_text: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON)
    original: Mapped[dict] = mapped_column(JSON)
    current: Mapped[dict] = mapped_column(JSON)


class Revision(Base):
    __tablename__ = "comparison_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("comparisons.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    revision: Mapped[int] = mapped_column(Integer)
    values: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


engine = create_engine(settings().database_url, pool_pre_ping=True)
Session = sessionmaker(engine)


def get_db():
    with Session() as session:
        yield session
