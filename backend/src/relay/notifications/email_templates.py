# ruff: noqa: E501  (inline email HTML: long style attributes are clearer unwrapped)
"""Transactional email content: short, branded, plain, with one link into Relay.

Subjects and preview text are deliberately generic ("You have a new task in Acme"):
they show on lock screens and in notification previews, so case titles, task titles
and comment text never appear there. The body names the case and task, which the
recipient can already see in Relay, and never includes comment text, knowledge content
or anything gated by visibility.
"""

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True, slots=True)
class Rendered:
    subject: str
    html: str
    text: str


def _layout(
    *, preview: str, heading: str, lines: list[str], cta: str, url: str, footer: str
) -> str:
    body = "".join(
        f'<p style="margin:0 0 12px;font-size:14px;line-height:22px;color:#3f3f46">{escape(line)}</p>'
        for line in lines
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{escape(heading)}</title></head>
<body style="margin:0;background:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<span style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(preview)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border:1px solid #e4e4e7;border-radius:10px">
<tr><td style="padding:20px 28px;border-bottom:1px solid #f4f4f5;font-size:14px;font-weight:600;color:#18181b;letter-spacing:-0.01em">Relay</td></tr>
<tr><td style="padding:24px 28px 8px">
<h1 style="margin:0 0 14px;font-size:17px;line-height:24px;font-weight:600;color:#18181b">{escape(heading)}</h1>
{body}
<p style="margin:20px 0 8px"><a href="{escape(url, quote=True)}" style="display:inline-block;background:#18181b;color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;padding:9px 16px;border-radius:7px">{escape(cta)}</a></p>
</td></tr>
<tr><td style="padding:16px 28px 22px;font-size:12px;line-height:18px;color:#71717a">{escape(footer)}</td></tr>
</table></td></tr></table></body></html>"""


def _text(heading: str, lines: list[str], cta: str, url: str, footer: str) -> str:
    return "\n\n".join([heading, *lines, f"{cta}: {url}", footer])


def render(
    kind: str,
    *,
    workspace: str,
    url: str,
    preferences_url: str,
    actor: str | None = None,
    case_title: str | None = None,
    task_title: str | None = None,
    detail: str | None = None,
) -> Rendered:
    who = actor or "Someone"
    case_line = f"Case: {case_title}" if case_title else ""
    task_line = f"Task: {task_title}" if task_title else ""
    updates = {
        "approved": "approved the plan",
        "rejected": "rejected the plan",
        "executing": "applied the ownership changes",
        "completed": "completed the case",
        "cancelled": "cancelled the case",
        "emergency": "marked a case as an emergency",
    }
    match kind:
        case "task_assigned":
            subject, heading = f"New task in {workspace}", f"{who} assigned you a task"
            lines, cta = [task_line, case_line], "Open the task"
        case "task_due_soon":
            subject, heading = (
                f"A task is due soon in {workspace}",
                "A task assigned to you is due within a day",
            )
            lines, cta = [task_line, case_line], "Open the task"
        case "task_overdue":
            subject, heading = (
                f"A task is overdue in {workspace}",
                "A task assigned to you is overdue",
            )
            lines, cta = [task_line, case_line], "Open the task"
        case "approval_requested":
            subject, heading = (
                f"Approval requested in {workspace}",
                f"{who} asked for your approval",
            )
            lines, cta = [case_line, "Review the plan and decide in Relay."], "Review the plan"
        case "mentioned":
            subject, heading = f"You were mentioned in {workspace}", f"{who} mentioned you"
            lines, cta = [case_line, "Open the case to read the comment."], "Open the comment"
        case "case_update":
            subject = f"Case update in {workspace}"
            heading = f"{who} {updates.get(detail or '', 'updated a case')}"
            lines, cta = [case_line], "Open the case"
        case "invitation":
            subject, heading = (
                f"You're invited to {workspace} on Relay",
                f"Join {workspace} on Relay",
            )
            lines = [
                f"{who} invited you to {workspace}, where your organisation tracks who owns what "
                "and hands work over safely.",
                "Sign in with this email address to accept.",
            ]
            cta = "Accept invitation"
        case _:
            raise ValueError(f"unknown email kind {kind!r}")
    lines = [line for line in lines if line]
    footer = (
        "You received this because someone invited this address to Relay."
        if kind == "invitation"
        else f"You're receiving this as a member of {workspace}. Manage email preferences: {preferences_url}"
    )
    preview = heading if kind != "mentioned" else f"You were mentioned in {workspace}"
    return Rendered(
        subject=subject,
        html=_layout(
            preview=preview, heading=heading, lines=lines, cta=cta, url=url, footer=footer
        ),
        text=_text(heading, lines, cta, url, footer),
    )
