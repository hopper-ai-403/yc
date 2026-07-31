"""API surface integrity validation (Sprint 12, Part 6).

Verifies OpenAPI generation, route uniqueness, and the standard response
envelope on every endpoint.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi.routing import APIRoute

from app.main import create_application

app = create_application()


def _api_routes() -> list[APIRoute]:
    return [r for r in app.routes if isinstance(r, APIRoute)]


def test_openapi_generation_succeeds() -> None:
    schema = app.openapi()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"]
    assert len(schema["paths"]) > 0


def test_no_duplicate_routes() -> None:
    pairs: list[tuple[str, str]] = []
    for route in _api_routes():
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            pairs.append((method, route.path))
    duplicates = [pair for pair, count in Counter(pairs).items() if count > 1]
    assert duplicates == [], f"duplicate routes: {duplicates}"


def test_every_endpoint_declares_envelope_response_model() -> None:
    from fastapi.responses import JSONResponse

    offenders: list[str] = []
    for route in _api_routes():
        # File-download endpoints legitimately stream non-JSON payloads.
        if route.response_class is not JSONResponse:
            continue
        model = route.response_model
        if model is None:
            offenders.append(f"{sorted(route.methods or set())} {route.path}")
            continue
        fields: dict[str, Any] = getattr(model, "model_fields", {})
        if "success" not in fields or "message" not in fields or "data" not in fields:
            offenders.append(f"{sorted(route.methods or set())} {route.path}")
    assert offenders == [], f"endpoints missing success envelope: {offenders}"


def test_openapi_documents_all_routes() -> None:
    schema = app.openapi()
    documented = {
        (method.upper(), path)
        for path, methods in schema["paths"].items()
        for method in methods
        if method not in {"head", "options"}
    }
    actual = {
        (method, route.path)
        for route in _api_routes()
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert documented == actual


def test_openapi_has_no_broken_refs() -> None:
    """Every $ref resolves to a component inside the generated schema."""
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                assert ref.startswith("#/components/schemas/"), ref
                name = ref.rsplit("/", 1)[-1]
                assert name in components, f"broken ref: {ref}"
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(schema)
