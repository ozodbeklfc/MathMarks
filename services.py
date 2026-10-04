"""Queries and scoring shared by the bot, the API and Excel."""
import re

from sqlalchemy import delete, func, select

import config
from db import ClassTopic, Mark, SchoolClass, Student, Topic


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).replace("\xa0", " ")).strip()


def parts_of(has_parts: bool):
    return ("toq", "juft") if has_parts else ("single",)


def parse_names(text: str) -> list[str]:
    """Pasted list -> names. Accepts '1. Name', '2) Name', '- Name' and plain lines."""
    names = []
    for line in re.split(r"[\n;]+", text):
        name = clean(re.sub(r"^\s*(\d+\s*[.)\-]?|[-•*])\s*", "", line))
        if len(name) > 1:
            names.append(name)
    return names


def list_classes(s):
    return s.scalars(select(SchoolClass).order_by(SchoolClass.position, SchoolClass.id)).all()


def add_class(s, name: str) -> SchoolClass:
    name = clean(name)
    cls = s.scalar(select(SchoolClass).where(SchoolClass.name == name))
    if cls:
        return cls
    pos = (s.scalar(select(func.max(SchoolClass.position))) or 0) + 1
    cls = SchoolClass(name=name, position=pos)
    s.add(cls)
    s.flush()
    # A new class starts with every existing topic.
    for t in s.scalars(select(Topic).order_by(Topic.position)):
        s.add(ClassTopic(class_id=cls.id, topic_id=t.id, position=t.position))
    return cls


def add_students(s, class_id: int, names: list[str]) -> int:
    existing = {n.lower() for n in s.scalars(select(Student.full_name).where(Student.class_id == class_id))}
    pos = s.scalar(select(func.max(Student.position)).where(Student.class_id == class_id)) or 0
    added = 0
    for name in names:
        name = clean(name)
        if not name or name.lower() in existing:
            continue
        pos += 1
        s.add(Student(class_id=class_id, full_name=name, position=pos))
        existing.add(name.lower())
        added += 1
    return added


def add_topic(s, title: str, has_parts: bool, class_ids=None) -> Topic:
    pos = (s.scalar(select(func.max(Topic.position))) or 0) + 1
    t = Topic(title=clean(title), has_parts=has_parts, position=pos)
    s.add(t)
    s.flush()
    if class_ids is None:
        class_ids = [c.id for c in list_classes(s)]
    for cid in class_ids:
        s.add(ClassTopic(class_id=cid, topic_id=t.id, position=pos))
    return t


def set_mark(s, student_id: int, topic_id: int, part: str, color):
    st = s.get(Student, student_id)
    t = s.get(Topic, topic_id)
    if not st or not t or part not in parts_of(t.has_parts):
        raise ValueError("bad cell")
    if not s.get(ClassTopic, (st.class_id, topic_id)):
        raise ValueError("topic is not in this class")
    if color is not None and color not in config.COLORS:
        raise ValueError("bad color")
    s.execute(delete(Mark).where(Mark.student_id == student_id, Mark.topic_id == topic_id, Mark.part == part))
    if color:
        s.add(Mark(student_id=student_id, topic_id=topic_id, part=part, color=color))


def class_topics(s, class_id: int):
    return s.scalars(
        select(Topic).join(ClassTopic, ClassTopic.topic_id == Topic.id)
        .where(ClassTopic.class_id == class_id).order_by(ClassTopic.position, Topic.id)
    ).all()


def class_data(s, class_id: int):
    """Everything about one class: topics, students, marks, totals and places."""
    cls = s.get(SchoolClass, class_id)
    if not cls:
        return None
    topics = class_topics(s, class_id)
    cells = [(t.id, p) for t in topics for p in parts_of(t.has_parts)]
    max_total = len(cells) * max(config.POINTS.values())
    students = s.scalars(select(Student).where(Student.class_id == class_id).order_by(Student.position, Student.id)).all()
    marks = {}
    if students:
        for m in s.scalars(select(Mark).where(Mark.student_id.in_([st.id for st in students]))):
            marks.setdefault(m.student_id, {})[f"{m.topic_id}:{m.part}"] = m.color
    rows = []
    for st in students:
        mk = marks.get(st.id, {})
        total = cw = hw = 0
        for tid, part in cells:
            pts = config.POINTS.get(mk.get(f"{tid}:{part}"), 0)
            total += pts
            cw += pts if part == "toq" else 0
            hw += pts if part == "juft" else 0
        rows.append({"id": st.id, "name": st.full_name, "marks": {k: v for k, v in mk.items()},
                     "total": total, "cw": cw, "hw": hw})
    # Places: highest total first, equal totals share a place.
    for r in rows:
        r["place"] = 1 + sum(1 for o in rows if o["total"] > r["total"])
    return {
        "id": cls.id, "name": cls.name, "points": config.POINTS, "max": max_total,
        "topics": [{"id": t.id, "title": t.title, "has_parts": t.has_parts} for t in topics],
        "students": rows,
    }


def classes_summary(s):
    out = []
    for c in list_classes(s):
        d = class_data(s, c.id)
        n = len(d["students"])
        avg = round(sum(r["total"] for r in d["students"]) / n, 1) if n else 0
        out.append({"id": c.id, "name": c.name, "students": n, "topics": len(d["topics"]), "avg": avg, "max": d["max"]})
    return out
