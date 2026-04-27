"""Render ssh_commands templates by substituting {param} placeholders."""
import re


class _SafeDict(dict):
    """Return the placeholder unchanged when a key is missing."""
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower().strip()).strip("-")


def _is_ip(value: str) -> bool:
    return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", value.strip()))


def render_commands(ssh_commands: list[str], params: dict[str, str]) -> list[str]:
    """Substitute {key} placeholders in ssh_commands with param values.

    Derived keys automatically available:
    - {key_dashes}  → value with dots and spaces replaced by hyphens, lowercase
    - {key_slug}    → slugified value (alphanumeric + hyphens only)
    """
    expanded: dict[str, str] = {}
    for key, value in params.items():
        expanded[key] = value
        expanded[f"{key}_dashes"] = value.replace(".", "-").replace(" ", "-").lower()
        expanded[f"{key}_slug"] = _slugify(value)

    safe = _SafeDict(expanded)
    return [cmd.format_map(safe) for cmd in ssh_commands]


def validate_params(parameters: list[dict], submitted: dict[str, str]) -> list[str]:
    """Return list of error messages for missing/invalid params."""
    errors: list[str] = []
    for p in parameters:
        key = p["key"]
        required = p.get("required", False)
        ptype = p.get("type", "string")
        value = submitted.get(key, "").strip()

        if required and not value:
            errors.append(f"Campo obrigatório: {p.get('label', key)}")
            continue

        if value and ptype == "ip" and not _is_ip(value):
            errors.append(f"IP inválido em '{p.get('label', key)}': {value!r}")

    return errors
