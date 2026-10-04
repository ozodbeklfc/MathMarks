"""Database tables."""
from pathlib import Path

from sqlalchemy import ForeignKey, String, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

import config

Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{config.DB_PATH}", connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _fk_on(conn, _):
    conn.execute("PRAGMA foreign_keys=ON")


Session = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class SchoolClass(Base):
    __tablename__ = "classes"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    position: Mapped[int] = mapped_column(default=0)


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    position: Mapped[int] = mapped_column(default=0)


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    # True: two marks (toq = classwork, juft = homework). False: one mark.
    has_parts: Mapped[bool] = mapped_column(default=True)
    position: Mapped[int] = mapped_column(default=0)


class ClassTopic(Base):
    __tablename__ = "class_topics"
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(default=0)


class Mark(Base):
    __tablename__ = "marks"
    __table_args__ = (UniqueConstraint("student_id", "topic_id", "part"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    part: Mapped[str] = mapped_column(String(8))  # toq | juft | single
    color: Mapped[str] = mapped_column(String(8))  # green | yellow | red


def init_db():
    Base.metadata.create_all(engine)
