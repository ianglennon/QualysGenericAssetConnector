"""Template variable resolution for child endpoint URL paths.

Resolves {variable} placeholders in endpoint paths using parent record data
and variable_extractions configuration. Pure functions, no DB/ORM dependencies.
"""

import logging
import re
from urllib.parse import quote

logger = logging.getLogger(__name__)

_VARIABLE_PATTERN = re.compile(r"\{(\w+)\}")


class TemplateResolutionError(Exception):
    """Raised when a template variable cannot be resolved."""

    def __init__(self, variable: str, path: str, reason: str) -> None:
        self.variable = variable
        self.path = path
        self.reason = reason
        super().__init__(f"Cannot resolve '{{{variable}}}' in '{path}': {reason}")


def extract_variables(path: str) -> list[str]:
    """Return deduplicated list of variable names from a path template.

    Example: "/nodes/{name}/qemu/{vmid}" -> ["name", "vmid"]
    """
    matches = _VARIABLE_PATTERN.findall(path)
    return list(dict.fromkeys(matches))


def _resolve_dot_path(record: dict, dot_path: str) -> object:
    """Traverse nested dict using dot-separated path segments.

    First checks for a literal flat key match (e.g. "_parent.node" as a single
    key in the dict), then falls back to nested traversal. This supports merged
    parent context records where _merge_parent_context creates flat keys with
    dots like "_parent.node".

    Raises KeyError if a segment is not found.
    Raises TypeError if an intermediate value is not a dict.
    """
    # Fast path: literal flat key match (supports _parent.* merged keys)
    if dot_path in record:
        return record[dot_path]

    current = record
    for segment in dot_path.split("."):
        if not isinstance(current, dict):
            raise TypeError(
                f"Expected dict at segment '{segment}', got {type(current).__name__}"
            )
        current = current[segment]
    return current


def _resolve_variable(var_name: str, path: str, parent_record: dict,
                      variable_extractions: dict[str, str]) -> str:
    """Resolve a single template variable to a URL-encoded string value.

    Resolution order:
    1. Explicit extraction rule in variable_extractions
    2. Direct key match in parent_record (e.g. "vmid" in record)
    3. Ancestor key via _parent.{var_name} in parent_record (for multi-level chains)

    Raises TemplateResolutionError if the variable cannot be resolved.
    """
    # 1. Explicit extraction rule
    if var_name in variable_extractions:
        dot_path = variable_extractions[var_name]
        try:
            raw_value = _resolve_dot_path(parent_record, dot_path)
        except (KeyError, TypeError):
            raise TemplateResolutionError(
                var_name, path, f"field '{dot_path}' not found in parent record"
            )
        if raw_value is None:
            raise TemplateResolutionError(
                var_name, path, f"field '{dot_path}' is null"
            )
        return quote(str(raw_value), safe="")

    # 2. Direct key in parent record
    if var_name in parent_record and parent_record[var_name] is not None:
        return quote(str(parent_record[var_name]), safe="")

    # 3. Ancestor key via _parent.* (for multi-level chains where
    #    grandchild paths need variables resolved at ancestor levels,
    #    e.g. {node} from grandparent available as _parent.node in
    #    the merged parent record)
    ancestor_key = f"_parent.{var_name}"
    if ancestor_key in parent_record and parent_record[ancestor_key] is not None:
        return quote(str(parent_record[ancestor_key]), safe="")

    raise TemplateResolutionError(
        var_name, path, "no extraction rule defined and not found in parent record"
    )


def resolve_path(
    path: str,
    parent_record: dict,
    variable_extractions: dict[str, str],
) -> str:
    """Replace {variable} placeholders in path with URL-encoded parent record values.

    Args:
        path: URL path template, e.g. "/nodes/{name}/qemu/{vmid}"
        parent_record: Dict of parent response data to extract values from.
        variable_extractions: Mapping of variable_name -> dot_notation_path
            describing how to extract each variable from parent_record.

    Returns:
        Resolved path with all variables replaced and values URL-encoded.

    Raises:
        TemplateResolutionError: If a variable cannot be resolved from
            extraction rules, direct record keys, or _parent.* ancestor keys.

    Security:
        Uses str.replace() for substitution — NOT str.format(), format_map(),
        or string.Template which allow Python attribute access (SSTI risk).
        All values are URL-encoded with safe="" to prevent path traversal
        and query injection.
    """
    variables = extract_variables(path)
    if not variables:
        return path

    resolved = path
    for var_name in variables:
        encoded_value = _resolve_variable(var_name, path, parent_record, variable_extractions)
        resolved = resolved.replace(f"{{{var_name}}}", encoded_value)

    return resolved
