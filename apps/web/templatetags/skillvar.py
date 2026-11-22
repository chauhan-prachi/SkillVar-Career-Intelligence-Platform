from django import template

register = template.Library()

STATUS_CLASS = {"confirmed": "text-bg-success", "possible": "badge-soft-blue", "insufficient": "text-bg-secondary",
                "not_demonstrated": "text-bg-danger", "missing": "badge-outline"}
STATUS_LABEL = {"confirmed": "Confirmed match", "possible": "Possible match", "insufficient": "Insufficient evidence",
                "not_demonstrated": "Not demonstrated", "missing": "Missing"}


@register.filter
def pct(value) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "–"


@register.filter
def pct_int(value) -> int:
    try:
        return round(float(value) * 100)
    except (TypeError, ValueError):
        return 0


@register.filter
def status_badge(status: str) -> str:
    return STATUS_CLASS.get(status, "badge-outline")


@register.filter
def status_label(status: str) -> str:
    return STATUS_LABEL.get(status, status)


@register.filter
def level_label(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "–"
    return "Beginner" if v < 0.45 else "Intermediate" if v < 0.72 else "Advanced"


@register.filter
def get_item(mapping, key):
    return mapping.get(key, [])


@register.filter
def code_label(code: str) -> str:
    from apps.matching.scoring import LABELS
    return LABELS.get(code, code)


@register.filter
def get_field(form, name):
    return form[name]
