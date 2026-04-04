"""RBAC permission constants — single source of truth for all permission strings."""

RESOURCE_AREAS = ["connectors", "canvases", "schedules", "runs", "settings", "users", "roles"]

CRUD_ACTIONS = ["create", "read", "update", "delete"]

SPECIAL_ACTIONS: dict[str, list[str]] = {
    "runs": ["trigger_sync"],
    "connectors": ["toggle_enabled"],
}

ALL_PERMISSIONS: list[str] = []
for _resource in RESOURCE_AREAS:
    for _action in CRUD_ACTIONS:
        ALL_PERMISSIONS.append(f"{_resource}:{_action}")
    for _action in SPECIAL_ACTIONS.get(_resource, []):
        ALL_PERMISSIONS.append(f"{_resource}:{_action}")

VALID_PERMISSIONS = frozenset(ALL_PERMISSIONS)
