"""Test FastAPI app startup and route initialization.

These tests ensure that:
1. The FastAPI app can be imported and started successfully
2. All routes are properly registered
3. Query parameter types are valid
4. Pydantic models are compatible with FastAPI
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_app_can_be_imported():
    """Test that the app module can be imported without errors."""
    from src.app import app
    assert isinstance(app, FastAPI)
    assert app.title == "mostlylucid-nmt"


def test_app_startup_without_errors(app_client):
    """Test that the app starts up without exceptions."""
    # If we got here with app_client fixture, startup was successful
    assert app_client is not None


def test_all_routes_registered(app_client):
    """Test that all expected routes are registered."""
    from src.app import app

    routes = [route.path for route in app.routes]

    # Check critical routes are present
    expected_routes = [
        "/translate",
        "/lang_pairs",
        "/get_languages",
        "/language_detection",
        "/model_name",
        "/healthz",
        "/readyz",
        "/cache",
        "/discover/all",
        "/discover/opus-mt",
        "/discover/mbart50",
        "/discover/m2m100",
    ]

    for expected in expected_routes:
        assert expected in routes, f"Route {expected} not registered"


def test_openapi_schema_generation():
    """Test that OpenAPI schema can be generated without errors.

    This catches FastAPI/Pydantic compatibility issues in route definitions.
    """
    from src.app import app

    # This will fail if there are invalid parameter types or Pydantic models
    schema = app.openapi()

    assert schema is not None
    assert "openapi" in schema
    assert "paths" in schema
    assert "/translate" in schema["paths"]


def test_query_parameter_types_are_valid():
    """Test that all GET endpoints have valid query parameter types.

    This specifically catches issues like Optional[List[str]] in Query params
    which cause FastAPI to fail.
    """
    from src.app import app
    from fastapi.routing import APIRoute

    for route in app.routes:
        if isinstance(route, APIRoute) and "GET" in route.methods:
            # Try to access the route's dependant to validate parameters
            # This will raise if parameter types are invalid
            assert route.dependant is not None, f"Route {route.path} has invalid parameters"

            # Check each parameter
            for param in route.dependant.query_params:
                # Ensure parameter has a valid field_info
                assert param.field_info is not None, \
                    f"Route {route.path} param {param.name} has invalid field_info"


def test_pydantic_models_are_valid():
    """Test that all Pydantic models used in routes are valid."""
    from src import models
    import inspect
    from pydantic import BaseModel

    # Get all Pydantic models from models module
    for name, obj in inspect.getmembers(models):
        if inspect.isclass(obj) and issubclass(obj, BaseModel) and obj != BaseModel:
            # Try to create schema - will fail if model is invalid
            schema = obj.model_json_schema()
            assert schema is not None, f"Model {name} has invalid schema"


@pytest.mark.integration
def test_health_endpoint_responds(app_client):
    """Test that health endpoint works after startup."""
    response = app_client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.integration
def test_translate_get_accepts_empty_text_list(app_client):
    """Test that translate GET handles empty text list correctly.

    This validates the fix for Optional[List[str]] → List[str] with default=[].
    """
    response = app_client.get("/translate?target_lang=de")
    # Should return 200 with empty translations, not 422 validation error
    assert response.status_code == 200
    data = response.json()
    assert data["translations"] == []


@pytest.mark.integration
def test_translate_get_with_text_array(app_client):
    """Test that translate GET accepts multiple text parameters."""
    response = app_client.get(
        "/translate?target_lang=de&text=Hello&text=World"
    )
    assert response.status_code == 200
    data = response.json()
    assert "translations" in data
    assert isinstance(data["translations"], list)


def test_route_response_models_are_valid():
    """Test that all routes have valid response_model configurations."""
    from src.app import app
    from fastapi.routing import APIRoute

    for route in app.routes:
        if isinstance(route, APIRoute):
            # Routes should either have no response_model or a valid one
            if route.response_model:
                # Try to access response_model schema
                try:
                    from pydantic import TypeAdapter
                    adapter = TypeAdapter(route.response_model)
                    schema = adapter.json_schema()
                    assert schema is not None
                except Exception as e:
                    pytest.fail(
                        f"Route {route.path} has invalid response_model: {e}"
                    )


def test_no_duplicate_routes():
    """Test that there are no duplicate route paths."""
    from src.app import app
    from fastapi.routing import APIRoute

    paths_and_methods = set()

    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                key = (route.path, method)
                assert key not in paths_and_methods, \
                    f"Duplicate route: {method} {route.path}"
                paths_and_methods.add(key)


def test_all_routes_have_descriptions():
    """Test that all API routes have proper documentation."""
    from src.app import app
    from fastapi.routing import APIRoute

    for route in app.routes:
        if isinstance(route, APIRoute) and not route.path.startswith("/docs"):
            assert route.summary or route.description, \
                f"Route {route.path} lacks documentation"
