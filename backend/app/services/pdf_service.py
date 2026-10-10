"""Itinerary PDF (backend-spec.md §4) — built with ReportLab from a finalized draft."""

import re
from datetime import date
from decimal import Decimal
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from svglib.svglib import svg2rlg

from app.models.enums import TripType
from app.schemas import DraftOut, TripOut

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
BRAND = colors.HexColor("#0369A1")
INK = colors.HexColor("#0C4A6E")
LINE = colors.HexColor("#BAE6FD")
PRIORITY_LABELS = {"time": "Time", "destinations": "Destinations", "budget": "Budget"}
TRIP_TYPES = {
    TripType.SOLO: "Solo",
    TripType.COUPLE: "Couple",
    TripType.FAMILY: "Family",
    TripType.FRIENDS: "Friends",
}


# ---------- Fonts ----------
@lru_cache
def fonts() -> tuple[str, str, str]:
    """(heading font, body font, currency symbol). Brand TTFs if present, else Helvetica + 'Rs.'"""
    files = {"Poppins-Bold": "Poppins-Bold.ttf", "Inter-Regular": "Inter-Regular.ttf"}
    paths = {name: ASSETS / "fonts" / file for name, file in files.items()}
    if all(p.exists() for p in paths.values()):
        for name, path in paths.items():
            pdfmetrics.registerFont(TTFont(name, str(path)))
        return "Poppins-Bold", "Inter-Regular", "₹"
    return "Helvetica-Bold", "Helvetica", "Rs. "


# ---------- Formatting ----------
def format_inr(amount: Decimal | float, symbol: str = "₹") -> str:
    """Indian digit grouping: 1234567.5 -> ₹12,34,567.50"""
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    whole, frac = f"{abs(value):.2f}".split(".")
    head, tail = whole[:-3], whole[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    grouped = ",".join([*groups, tail]) if groups else tail
    return f"{'-' if value < 0 else ''}{symbol}{grouped}.{frac}"


def pdf_filename(destination: str, start_date: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", destination).strip("-") or "trip"
    return f"GhumakkadYatri-{slug}-{start_date}.pdf"


def _time_range(time: str | None, duration: int | None) -> str:
    if time is None:
        return "—"
    if duration is None:
        return time
    end = int(time[:2]) * 60 + int(time[3:]) + duration
    return f"{time}–{end // 60:02d}:{end % 60:02d}"


def _date(d: date) -> str:
    return f"{d:%a}, {d.day} {d:%b %Y}"


# ---------- Logo ----------
@lru_cache
def _logo() -> Drawing | None:
    drawing = svg2rlg(str(ASSETS / "logo.svg"))
    if drawing is None:
        return None
    scale = (62 * mm) / drawing.width
    drawing.width, drawing.height = drawing.width * scale, drawing.height * scale
    drawing.scale(scale, scale)
    return drawing


# ---------- Document ----------
def build_itinerary_pdf(trip: TripOut, draft: DraftOut) -> bytes:
    heading, body, symbol = fonts()
    title = ParagraphStyle("title", fontName=heading, fontSize=16, textColor=BRAND, leading=20)
    day_style = ParagraphStyle(
        "day",
        fontName=heading,
        fontSize=11.5,
        textColor=BRAND,
        leading=15,
        spaceBefore=8,
        spaceAfter=3,
    )
    text = ParagraphStyle("text", fontName=body, fontSize=9.5, textColor=INK, leading=12)
    muted = ParagraphStyle("muted", parent=text, textColor=colors.HexColor("#3D6782"))

    story: list[object] = []
    logo = _logo()
    if logo is not None:
        story += [logo, Spacer(1, 4 * mm)]
    story.append(Paragraph(trip.destination, title))
    story.append(
        Paragraph(
            f"{_date(trip.start_date)} – {_date(trip.end_date)} · {trip.day_count} days · "
            f"{TRIP_TYPES[trip.trip_type]} trip · Plan: {draft.name}"
            + (
                f" · Top priority: {PRIORITY_LABELS[trip.top_priority.value]}"
                if trip.top_priority
                else ""
            ),
            muted,
        )
    )
    story.append(Spacer(1, 4 * mm))

    for day in draft.days:
        story.append(Paragraph(f"Day {day.day_number} · {_date(day.date)}", day_style))
        if not day.activities:
            story.append(Paragraph("No activities planned", muted))
            continue
        rows = [
            [
                _time_range(a.time, a.duration_minutes),
                Paragraph(a.destination_name, text),
                format_inr(a.cost, symbol) if a.cost is not None else "",
            ]
            for a in day.activities
        ]
        rows.append(["", "Day total", format_inr(day.total_cost, symbol)])
        table = Table(rows, colWidths=[26 * mm, 112 * mm, 32 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, -1), body, 9.5),
                    ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                    ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
                    ("FONT", (0, -1), (-1, -1), heading, 9.5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)

    summary = [["Trip total", format_inr(draft.total_cost, symbol)]]
    if trip.budget is not None:
        remaining = Decimal(str(trip.budget)) - Decimal(str(draft.total_cost))
        summary.append(["Budget", format_inr(trip.budget, symbol)])
        summary.append(
            ["Over budget by" if remaining < 0 else "Remaining", format_inr(abs(remaining), symbol)]
        )
    total = Table(summary, colWidths=[138 * mm, 32 * mm])
    total.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), heading, 12),
                ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, 0), (-1, 0), 1.5, INK),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story += [Spacer(1, 6 * mm), total]

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"{trip.destination} itinerary",
        author="GhumakkadYatri",
    )
    doc.build(story)
    return buffer.getvalue()
