"""Read the coloured Excel gradebook and write it back in the same layout."""
import io
import re

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import delete, select

import services
from db import ClassTopic, SchoolClass, Student, Topic

FILL_TO_COLOR = {"00B050": "green", "FFFF00": "yellow", "FF0000": "red"}
COLOR_TO_FILL = {v: k for k, v in FILL_TO_COLOR.items()}
PART_RE = re.compile(r"^(.*?)\s*\((toq|juft)\)$", re.I)


def _cell_color(cell):
    fill = cell.fill
    if not fill or fill.fill_type != "solid" or fill.fgColor.type != "rgb":
        return None
    return FILL_TO_COLOR.get(str(fill.fgColor.rgb)[-6:].upper())


def import_workbook(s, data: bytes) -> list[dict]:
    """Each sheet becomes a class. A class with the same name is replaced."""
    wb = load_workbook(io.BytesIO(data))
    report = []
    for ws in wb.worksheets:
        # Row 1: topic headers. "(toq)" / "(juft)" columns of one title form one topic.
        columns = []  # (column index, title, part)
        for col in range(3, ws.max_column + 1):
            head = ws.cell(1, col).value
            if head is None or not services.clean(head):
                continue  # the old hand-typed total column has no header
            head = services.clean(head)
            m = PART_RE.match(head)
            columns.append((col, m.group(1).strip(), m.group(2).lower()) if m else (col, head, "single"))
        rows = [r for r in range(2, ws.max_row + 1)
                if isinstance(ws.cell(r, 2).value, str) and services.clean(ws.cell(r, 2).value)]
        if not columns or not rows:
            continue

        cls = services.add_class(s, ws.title)
        s.execute(delete(Student).where(Student.class_id == cls.id))
        s.execute(delete(ClassTopic).where(ClassTopic.class_id == cls.id))
        s.flush()

        topic_ids, pos = {}, 0
        for _, title, part in columns:
            has_parts = part != "single"
            key = (title, has_parts)
            if key in topic_ids:
                continue
            t = s.scalar(select(Topic).where(Topic.title == title, Topic.has_parts == has_parts))
            if not t:
                t = services.add_topic(s, title, has_parts, class_ids=[])
            pos += 1
            s.add(ClassTopic(class_id=cls.id, topic_id=t.id, position=pos))
            topic_ids[key] = t.id
        s.flush()

        n_marks = 0
        for i, r in enumerate(rows, 1):
            st = Student(class_id=cls.id, full_name=services.clean(ws.cell(r, 2).value), position=i)
            s.add(st)
            s.flush()
            for col, title, part in columns:
                color = _cell_color(ws.cell(r, col))
                if color:
                    services.set_mark(s, st.id, topic_ids[(title, part != "single")], part, color)
                    n_marks += 1
        report.append({"class": cls.name, "students": len(rows), "topics": len(topic_ids), "marks": n_marks})
    return report


def export_workbook(s) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    head_align = Alignment(wrap_text=True, horizontal="center", vertical="center")
    for c in services.list_classes(s):
        d = services.class_data(s, c.id)
        ws = wb.create_sheet(re.sub(r"[\[\]:*?/\\]", "-", d["name"])[:31])
        col, cells = 3, []
        for t in d["topics"]:
            for part in services.parts_of(t["has_parts"]):
                label = t["title"] if part == "single" else f"{t['title']}\n({part})"
                ws.cell(1, col, label).alignment = head_align
                ws.column_dimensions[get_column_letter(col)].width = 13
                cells.append((col, f"{t['id']}:{part}"))
                col += 1
        ws.cell(1, col, "Jami").alignment = head_align
        ws.cell(1, col + 1, "O'rin").alignment = head_align
        ws.row_dimensions[1].height = 48
        ws.column_dimensions["A"].width = 5
        ws.column_dimensions["B"].width = 30
        ranked = sorted(d["students"], key=lambda r: (-r["total"], r["name"]))
        for i, st in enumerate(ranked, 1):
            ws.cell(i + 1, 1, i)
            ws.cell(i + 1, 2, st["name"])
            for cidx, key in cells:
                color = st["marks"].get(key)
                if color:
                    ws.cell(i + 1, cidx).fill = PatternFill("solid", fgColor="FF" + COLOR_TO_FILL[color])
            ws.cell(i + 1, col, st["total"]).font = Font(bold=True)
            ws.cell(i + 1, col + 1, st["place"])
        ws.freeze_panes = "C2"
    if not wb.worksheets:
        wb.create_sheet("Baholar")
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
