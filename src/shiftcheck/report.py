"""Render a Report as text, Markdown or JSON."""

from __future__ import annotations

import json
from typing import List

from .rules import Report

_LABEL = {"violation": "VIOLATION", "warning": "warning", "info": "info"}


def _summary(report: Report) -> str:
    return ("%d shifts, %d employees: %d violation(s), %d warning(s), %d note(s), %d unreadable row(s)"
            % (report.shifts, report.employees, report.count("violation"), report.count("warning"),
               report.count("info"), len(report.issues)))


def to_text(report: Report) -> str:
    lines = [_summary(report), ""]
    for issue in report.issues:
        lines.append("  INPUT      row %-4d %s" % (issue.row, issue.message))
    for f in report.findings:
        where = f.day or "whole plan"
        lines.append("  %-10s %-14s %-12s %-18s %s" % (_LABEL[f.severity], f.employee, where, f.rule, f.message))
        if f.reference:
            lines.append("  %-10s %s" % ("", "-> " + f.reference))
    if not report.findings and not report.issues:
        lines.append("  nothing to report")
    return "\n".join(lines) + "\n"


def to_markdown(report: Report) -> str:
    lines = ["# Shift plan check", "", _summary(report), ""]
    if report.issues:
        lines += ["## Unreadable rows", ""]
        lines += ["- row %d: %s" % (i.row, i.message) for i in report.issues]
        lines.append("")
    for severity, title in (("violation", "Violations"), ("warning", "Warnings"), ("info", "Notes")):
        items = [f for f in report.findings if f.severity == severity]
        if not items:
            continue
        lines += ["## " + title, "", "| Employee | Day | Rule | Finding | Reference |", "|---|---|---|---|---|"]
        for f in items:
            lines.append("| %s | %s | %s | %s | %s |" % (f.employee, f.day or "-", f.rule,
                                                          f.message.replace("|", "/"), f.reference or "-"))
        lines.append("")
    return "\n".join(lines)


def to_json(report: Report) -> str:
    payload = {
        "summary": {
            "shifts": report.shifts,
            "employees": report.employees,
            "violations": report.count("violation"),
            "warnings": report.count("warning"),
            "notes": report.count("info"),
            "unreadable_rows": len(report.issues),
        },
        "unreadable_rows": [{"row": i.row, "message": i.message} for i in report.issues],
        "findings": [f.as_dict() for f in report.findings],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


RENDERERS = {"text": to_text, "md": to_markdown, "json": to_json}
