"""JSON API used by the mini app."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

import config
import services
from db import ClassTopic, Session, Student, Topic


def telegram_user_id(init_data: str):
    """Check Telegram's signature on initData and return the user's ID, or None."""
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    their_hash = pairs.pop("hash", "")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
    ours = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(ours, their_hash):
        return None
    if time.time() - int(pairs.get("auth_date", 0)) > 86400:
        return None
    try:
        return int(json.loads(pairs["user"])["id"])
    except (KeyError, ValueError):
        return None


def teacher(x_init_data: str = Header(default="")):
    if config.DEV_MODE:
        return 0
    uid = telegram_user_id(x_init_data) if config.BOT_TOKEN else None
    if uid is None or uid not in config.TEACHER_IDS:
        raise HTTPException(403, "Faqat o'qituvchi uchun")
    return uid


router = APIRouter(prefix="/api", dependencies=[Depends(teacher)])


class ClassIn(BaseModel):
    name: str


class NamesIn(BaseModel):
    names: list[str]


class TopicIn(BaseModel):
    title: str
    has_parts: bool = True
    class_ids: list[int] | None = None


class TopicPatch(BaseModel):
    title: str | None = None
    class_ids: list[int] | None = None


class MarkIn(BaseModel):
    student_id: int
    topic_id: int
    part: str
    color: str | None = None


@router.get("/classes")
def get_classes():
    with Session() as s:
        return services.classes_summary(s)


@router.post("/classes")
def post_class(body: ClassIn):
    if not services.clean(body.name):
        raise HTTPException(400, "Nom bo'sh")
    with Session() as s:
        cls = services.add_class(s, body.name)
        s.commit()
        return {"id": cls.id, "name": cls.name}


@router.get("/classes/{class_id}")
def get_class(class_id: int):
    with Session() as s:
        data = services.class_data(s, class_id)
    if not data:
        raise HTTPException(404, "Sinf topilmadi")
    return data


@router.post("/classes/{class_id}/students")
def post_students(class_id: int, body: NamesIn):
    with Session() as s:
        added = services.add_students(s, class_id, body.names)
        s.commit()
        return {"added": added}


@router.delete("/students/{student_id}")
def delete_student(student_id: int):
    with Session() as s:
        s.execute(delete(Student).where(Student.id == student_id))
        s.commit()
    return {"ok": True}


def _topic_json(s, t):
    ids = s.scalars(select(ClassTopic.class_id).where(ClassTopic.topic_id == t.id)).all()
    return {"id": t.id, "title": t.title, "has_parts": t.has_parts, "class_ids": list(ids)}


@router.get("/topics")
def get_topics():
    with Session() as s:
        topics = s.scalars(select(Topic).order_by(Topic.position, Topic.id)).all()
        return [_topic_json(s, t) for t in topics]


@router.post("/topics")
def post_topic(body: TopicIn):
    if not services.clean(body.title):
        raise HTTPException(400, "Nom bo'sh")
    with Session() as s:
        t = services.add_topic(s, body.title, body.has_parts, body.class_ids)
        s.commit()
        return _topic_json(s, t)


@router.patch("/topics/{topic_id}")
def patch_topic(topic_id: int, body: TopicPatch):
    with Session() as s:
        t = s.get(Topic, topic_id)
        if not t:
            raise HTTPException(404, "Mavzu topilmadi")
        if body.title and services.clean(body.title):
            t.title = services.clean(body.title)
        if body.class_ids is not None:
            have = set(s.scalars(select(ClassTopic.class_id).where(ClassTopic.topic_id == t.id)))
            want = set(body.class_ids)
            if have - want:
                s.execute(delete(ClassTopic).where(ClassTopic.topic_id == t.id, ClassTopic.class_id.in_(have - want)))
            for cid in want - have:
                s.add(ClassTopic(class_id=cid, topic_id=t.id, position=t.position + 1000))
        s.commit()
        return _topic_json(s, t)


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: int):
    with Session() as s:
        s.execute(delete(Topic).where(Topic.id == topic_id))
        s.commit()
    return {"ok": True}


@router.put("/marks")
def put_mark(body: MarkIn):
    with Session() as s:
        try:
            services.set_mark(s, body.student_id, body.topic_id, body.part, body.color)
        except ValueError as e:
            raise HTTPException(400, str(e))
        s.commit()
    return {"ok": True}
