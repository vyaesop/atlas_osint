"""OSINT transform/connector framework (#17).

A Maltego-style registry of pluggable *transforms* that take text (or an
entity's text) and return structured selectors, plus optional entities and
relationships to fold into the graph. Built-in transforms are dependency-free
and offline; network-backed connectors can register against the same interface.
"""
from app.transforms.base import REGISTRY, Transform, TransformResult
from app.transforms.selectors import Selector, extract_selectors

__all__ = ["REGISTRY", "Transform", "TransformResult", "Selector", "extract_selectors"]
