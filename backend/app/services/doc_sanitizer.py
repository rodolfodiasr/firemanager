"""Sanitizador de documentação — detecta e mascara dados sensíveis antes da publicação."""
from __future__ import annotations

import re

# Padrões que indicam dado sensível
_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    (
        "IPv4 privado",
        re.compile(
            r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
            r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
            r"|192\.168\.\d{1,3}\.\d{1,3})\b"
        ),
        "[IP-PRIVADO]",
    ),
    (
        "IPv4 público",
        re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "[IP]",
    ),
    (
        "Token / API Key",
        re.compile(
            r"(?i)(?:token|api[_-]?key|secret|password|passwd|pwd|bearer)\s*[:=]\s*\S+"
        ),
        "[CREDENCIAL REMOVIDA]",
    ),
    (
        "Hash/Token longo",
        re.compile(r"\b[A-Za-z0-9+/]{32,}={0,2}\b"),
        "[HASH/TOKEN]",
    ),
    (
        "Senha em bloco de código",
        re.compile(r"(?i)(set\s+password|password\s+['\"]?)\S+"),
        r"\1[SENHA]",
    ),
]


def sanitize(content: str) -> tuple[str, list[dict]]:
    """Detecta dados sensíveis, mascara e retorna (conteúdo_sanitizado, lista_de_warnings).

    Cada warning: {"pattern": str, "excerpt": str (trecho original, max 60 chars)}
    """
    warnings: list[dict] = []
    sanitized = content

    for label, pattern, replacement in _PATTERNS:
        matches = pattern.findall(sanitized)
        if matches:
            unique = list(dict.fromkeys(str(m) for m in matches))
            for match in unique:
                excerpt = match[:60] + ("…" if len(match) > 60 else "")
                warnings.append({"pattern": label, "excerpt": excerpt})
            sanitized = pattern.sub(replacement, sanitized)

    return sanitized, warnings


def has_warnings(warnings: list[dict]) -> bool:
    return len(warnings) > 0
