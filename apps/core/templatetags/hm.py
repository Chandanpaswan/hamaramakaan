"""Template helpers: brand icons, Indian price formatting, safe rich text and query-string helpers."""
import re
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from django import template
from django.conf import settings
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

register = template.Library()

ICON_DIR = Path(settings.BASE_DIR) / "static" / "icons"


@lru_cache(maxsize=128)
def _load_icon(name):
    for candidate in (f"ui-{name}.svg", f"category-{name}.svg", f"{name}.svg"):
        path = ICON_DIR / candidate
        if path.exists():
            svg = path.read_text(encoding="utf-8")
            svg = svg.replace('stroke="#0F1B33"', 'stroke="currentColor"')
            return re.sub(r'\s(width|height)="24"', "", svg, count=2)
    return ""


@register.simple_tag
def icon(name, size=20, css=""):
    """Inline a Lucide brand icon that inherits the current text colour."""
    svg = _load_icon(name)
    if not svg:
        return ""
    attrs = f'<svg width="{int(size)}" height="{int(size)}" class="ic {escape(css)}" aria-hidden="true" focusable="false"'
    return mark_safe(svg.replace("<svg", attrs, 1))


def _to_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def indian_grouping(number):
    """1234567 -> '12,34,567'."""
    s = str(int(number))
    neg = s.startswith("-")
    s = s.lstrip("-")
    if len(s) <= 3:
        out = s
    else:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        out = ",".join(parts) + "," + tail
    return f"-{out}" if neg else out


@register.filter
def inr(value):
    """Full rupee amount with Indian digit grouping: ₹ 1,45,00,000."""
    d = _to_decimal(value)
    if d is None:
        return ""
    return f"₹ {indian_grouping(d.quantize(Decimal('1')))}"


def _trim(d):
    text = f"{d:.2f}".rstrip("0").rstrip(".")
    return text


@register.filter
def inr_short(value):
    """Compact rupee amount: ₹ 85 Lakh, ₹ 1.45 Cr, ₹ 28,000."""
    d = _to_decimal(value)
    if d is None:
        return ""
    if d >= Decimal("10000000"):
        return f"₹ {_trim(d / Decimal('10000000'))} Cr"
    if d >= Decimal("100000"):
        return f"₹ {_trim(d / Decimal('100000'))} Lakh"
    return f"₹ {indian_grouping(d.quantize(Decimal('1')))}"


@register.filter
def num(value):
    d = _to_decimal(value)
    if d is None:
        return ""
    if d == d.to_integral():
        return indian_grouping(d)
    return f"{indian_grouping(int(d))}.{str(d.quantize(Decimal('0.01'))).split('.')[1].rstrip('0')}"


_INLINE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_INLINE_LINK = re.compile(r"\[([^\]]+)\]\(((?:https?://|/)[^\s)]+)\)")


def _inline(text):
    text = escape(text)
    text = _INLINE_BOLD.sub(r"<strong>\1</strong>", text)

    def link(m):
        href = m.group(2)
        external = href.startswith("http")
        rel = ' rel="noopener" target="_blank"' if external else ""
        return f'<a href="{href}"{rel}>{m.group(1)}</a>'

    return _INLINE_LINK.sub(link, text)


@register.filter
def rich_text(value):
    """
    Very small, safe Markdown subset for staff-written content.
    Everything is HTML-escaped first, so editors cannot inject scripts.
    Supports: ## / ### headings, - bullet lists, 1. numbered lists, **bold**, [link](https://...), paragraphs.
    """
    if not value:
        return ""
    blocks, para, items, list_tag = [], [], [], None

    def flush_para():
        if para:
            blocks.append(f"<p>{'<br>'.join(_inline(p) for p in para)}</p>")
            para.clear()

    def flush_list():
        nonlocal list_tag
        if items:
            blocks.append(f"<{list_tag}>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + f"</{list_tag}>")
            items.clear()
        list_tag = None

    for raw in str(value).replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        numbered = re.match(r"^\d+[.)]\s+(.*)", line)
        if not line:
            flush_para()
            flush_list()
        elif line.startswith("### "):
            flush_para(), flush_list()
            blocks.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            flush_para(), flush_list()
            blocks.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith(("- ", "* ")):
            flush_para()
            if list_tag == "ol":
                flush_list()
            list_tag = "ul"
            items.append(line[2:])
        elif numbered:
            flush_para()
            if list_tag == "ul":
                flush_list()
            list_tag = "ol"
            items.append(numbered.group(1))
        else:
            flush_list()
            para.append(line)
    flush_para()
    flush_list()
    return mark_safe("\n".join(blocks))


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """Return the current query string with some keys replaced (used for pagination and sorting)."""
    request = context["request"]
    query = request.GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    encoded = query.urlencode()
    return f"?{encoded}" if encoded else "?"


@register.simple_tag(takes_context=True)
def absolute_url(context, path=None):
    request = context["request"]
    return request.build_absolute_uri(path or request.path)


@register.filter
def ago(value):
    """'3 days ago' (single unit) or 'today'."""
    from django.utils.timesince import timesince

    if not value:
        return ""
    text = timesince(value, depth=1).replace("\xa0", " ")
    return "today" if text.startswith("0 ") or "minute" in text or "hour" in text else f"{text} ago"


@register.filter
def initials(value):
    parts = [p for p in str(value or "").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "HM"


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.simple_tag
def locality_city_map():
    """{locality_id: {"id": city_id, "slug": city_slug}} for client-side locality filtering."""
    from apps.locations.models import Locality

    rows = Locality.objects.filter(is_active=True).values_list("id", "city_id", "city__slug")
    return {str(pk): {"id": str(city_id), "slug": slug} for pk, city_id, slug in rows}


@register.simple_tag
def badge(text, kind="info"):
    return format_html('<span class="hm-badge hm-badge-{}">{}</span>', kind, text)
