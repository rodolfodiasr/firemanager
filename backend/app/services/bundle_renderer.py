"""Fase 26 — Bundle template renderer for Golden Config Bundles."""
from __future__ import annotations

import json
import re


def render_template(template: str, variables: dict) -> str:
    """Replace {VARIABLE_NAME} placeholders in template string."""
    def replace(m: re.Match) -> str:
        key = m.group(1)
        return str(variables.get(key, m.group(0)))

    return re.sub(r"\{([A-Z0-9_]+)\}", replace, template)


def merge_variables(bundle_vars: dict, device_vars: dict, extra_vars: dict) -> dict:
    """Merge variable dicts: bundle < device < extra (extra wins)."""
    return {**bundle_vars, **device_vars, **extra_vars}


def render_rest_payload(section_template: str, variables: dict) -> dict:
    """Render section's rest_payload_template and parse as JSON."""
    rendered = render_template(section_template, variables)
    return json.loads(rendered)
