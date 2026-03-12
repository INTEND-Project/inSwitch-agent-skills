"""Utility functions for k8s_manager API calls used by this skill."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_TIMEOUT_SECONDS = 30


def _http_get_json(service_endpoint: str, relative_path: str) -> dict[str, Any]:
    base = service_endpoint.rstrip("/") + "/"
    url = urljoin(base, relative_path.lstrip("/"))
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def get_deployable_services_basic(service_endpoint: str) -> dict[str, Any]:
    """Fetch deployable services and return only name/description/dependencies.

    Args:
        service_endpoint: Base API endpoint, for example "http://host.docker.internal:8001".

    Returns:
        JSON-compatible dictionary:
        {
          "services": [
            {"name": str, "description": str, "dependencies": list[str]},
            ...
          ],
          "total": int
        }
    """

    raw_payload = _http_get_json(service_endpoint, "info/services")

    services = raw_payload.get("services", [])
    compact_services: list[dict[str, Any]] = []
    for item in services:
        compact_services.append(
            {
                "name": item.get("name"),
                "description": item.get("description"),
                "dependencies": item.get("dependencies", []) or [],
            }
        )

    return {"services": compact_services, "total": len(compact_services)}


def get_service_env_schema(service_endpoint: str, service_name: str) -> dict[str, Any]:
    """Fetch required/optional env var metadata for a specific service.

    Args:
        service_endpoint: Base API endpoint, for example "http://host.docker.internal:8001".
        service_name: Service name to look up.

    Returns:
        JSON-compatible dictionary:
        {
          "name": str,
          "required_env_vars": list[dict],
          "optional_env_vars": list[dict]
        }
    """

    raw_payload = _http_get_json(service_endpoint, "info/services")
    for item in raw_payload.get("services", []):
        if item.get("name") == service_name:
            return {
                "name": service_name,
                "required_env_vars": item.get("required_env_vars", []) or [],
                "optional_env_vars": item.get("optional_env_vars", []) or [],
            }
    raise ValueError(f"Service not found in /info/services: {service_name}")


def is_service_deployed(service_endpoint: str, expected: dict[str, Any]) -> dict[str, Any]:
    """Check whether a deployed instance matches the expected env var values.

    Args:
        service_endpoint: Base API endpoint, for example "http://host.docker.internal:8001".
        expected: JSON-like dict with:
            {
              "service_name": str,
              "env_vars": {str: Any}
            }

    Returns:
        JSON-compatible dictionary:
        {
          "service_name": str,
          "is_deployed": bool,
          "matched_instance": dict | None
        }
    """

    service_name = expected.get("service_name")
    if not service_name:
        raise ValueError("expected.service_name is required")

    expected_env = expected.get("env_vars", {}) or {}
    if not isinstance(expected_env, dict):
        raise ValueError("expected.env_vars must be an object/dict")

    status_candidates = [
        f"status/name={service_name}",
        f"status?service_name={service_name}",
        f"status?name={service_name}",
    ]

    payload: dict[str, Any] | None = None
    last_error: Exception | None = None
    for path in status_candidates:
        try:
            payload = _http_get_json(service_endpoint, path)
            break
        except HTTPError as exc:
            last_error = exc
            if exc.code != 404:
                raise
        except Exception as exc:  # pragma: no cover - transport/runtime safety
            last_error = exc

    if payload is None:
        if last_error is not None:
            raise last_error
        raise RuntimeError("Unable to fetch service status")

    expected_str = {k: str(v) for k, v in expected_env.items()}
    for instance in payload.get("instances", []):
        if instance.get("service_name") != service_name:
            continue
        actual_env = instance.get("env_vars", {}) or {}
        actual_str = {k: str(v) for k, v in actual_env.items()}
        if all(actual_str.get(key) == value for key, value in expected_str.items()):
            return {
                "service_name": service_name,
                "is_deployed": True,
                "matched_instance": instance,
            }

    return {"service_name": service_name, "is_deployed": False, "matched_instance": None}
