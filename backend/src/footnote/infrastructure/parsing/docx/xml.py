from __future__ import annotations

from lxml.etree import _Element

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"w": W_NS, "a": A_NS}

_FALSE = frozenset({"0", "false", "off"})


def w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def child(element: _Element | None, tag: str) -> _Element | None:
    if element is None:
        return None
    return element.find(w(tag))


def attr(element: _Element | None, name: str) -> str | None:
    if element is None:
        return None
    value = element.get(w(name))
    return value if value is not None else None


def int_attr(element: _Element | None, name: str) -> int | None:
    value = attr(element, name)
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def toggle(element: _Element | None) -> bool | None:
    """OOXML on/off property: present without value means on."""
    if element is None:
        return None
    value = attr(element, "val")
    return value is None or value.lower() not in _FALSE
