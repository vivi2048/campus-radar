from __future__ import annotations

from dataclasses import dataclass, field

from ..mail.mime import ParsedEmail
from .classify import Classification, classify_email
from .dates import TimingExtraction, extract_timings
from .fields import ExtractedFields, extract_fields


@dataclass
class Analysis:
    accepted: bool
    classification: Classification
    fields: ExtractedFields | None = None
    timing: TimingExtraction | None = None
    needs_review: bool = False
    auto_notes: str | None = None
    reasons: list[str] = field(default_factory=list)


def analyze_email(parsed: ParsedEmail) -> Analysis:
    classification = classify_email(
        parsed.subject,
        parsed.body_text,
        parsed.links,
        sender_email=parsed.sender_email,
        sender_name=parsed.sender_name,
    )
    if not classification.accepted:
        return Analysis(
            accepted=False,
            classification=classification,
            reasons=classification.reasons,
        )

    combined = f"{parsed.subject}\n{parsed.body_text}"
    fields = extract_fields(
        parsed.subject,
        parsed.body_text,
        parsed.sender_name,
        parsed.sender_email,
        parsed.links,
    )
    timing = extract_timings(combined, parsed.received_at)

    notes_parts: list[str] = []
    if fields.auto_notes:
        notes_parts.append(fields.auto_notes)
    if timing.deadline_note:
        notes_parts.append(timing.deadline_note)
    auto_notes = "\n".join(notes_parts) if notes_parts else None

    needs_review = bool(
        not timing.exam_start
        or not timing.exam_time_known
        or not fields.company
    )
    return Analysis(
        accepted=True,
        classification=classification,
        fields=fields,
        timing=timing,
        needs_review=needs_review,
        auto_notes=auto_notes,
        reasons=classification.reasons,
    )
