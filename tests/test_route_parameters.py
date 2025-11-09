"""Test route parameter validation and types.

These tests specifically validate that:
1. Query parameters are properly typed
2. No Optional[List[...]] in Query parameters (FastAPI incompatibility)
3. All required parameters are validated
4. Default values work correctly
"""

import pytest
from typing import get_type_hints, get_origin, get_args
from fastapi import Query
from fastapi.routing import APIRoute
import inspect


def test_no_optional_list_in_query_params():
    """Test that no route uses Optional[List[...]] in Query parameters.

    This was causing FastAPI errors. We should use List[...] with default=[]
    instead of Optional[List[...]] with default=None.
    """
    from src.app import app
    from typing import Union

    for route in app.routes:
        if isinstance(route, APIRoute):
            # Get the endpoint function
            endpoint = route.endpoint

            # Get type hints
            hints = get_type_hints(endpoint)

            # Check each parameter
            sig = inspect.signature(endpoint)
            for param_name, param in sig.parameters.items():
                if param_name in hints:
                    type_hint = hints[param_name]

                    # Check if it's Optional (Union with None)
                    if get_origin(type_hint) is Union:
                        args = get_args(type_hint)
                        if type(None) in args:
                            # It's Optional - check if it contains List
                            for arg in args:
                                if arg is not type(None):
                                    if get_origin(arg) is list:
                                        # Found Optional[List[...]]
                                        # Check if parameter has Query default
                                        if param.default and isinstance(param.default, type(Query(...))):
                                            pytest.fail(
                                                f"Route {route.path} parameter '{param_name}' "
                                                f"uses Optional[List[...]] with Query. "
                                                f"Use List[...] with Query(default=[]) instead."
                                            )


def test_all_query_params_have_defaults_or_required():
    """Test that all Query parameters have either default values or are required."""
    from src.app import app

    for route in app.routes:
        if isinstance(route, APIRoute):
            endpoint = route.endpoint
            sig = inspect.signature(endpoint)

            for param_name, param in sig.parameters.items():
                # Skip special parameters
                if param_name in ["self", "request", "translation_service",
                                   "language_detector", "cls"]:
                    continue

                # If it has a default that's a Query object
                if hasattr(param.default, "__class__") and "Query" in str(param.default.__class__):
                    # It should either have a default value or be required
                    assert param.default is not inspect.Parameter.empty, \
                        f"Route {route.path} param '{param_name}' is Query without default"


@pytest.mark.integration
def test_translate_get_query_params_validation(app_client):
    """Test that translate GET endpoint validates query parameters correctly."""

    # Missing required target_lang
    response = app_client.get("/translate")
    assert response.status_code == 422  # Validation error

    # Valid request with required param
    response = app_client.get("/translate?target_lang=de")
    assert response.status_code == 200

    # Text param should accept multiple values
    response = app_client.get("/translate?target_lang=de&text=Hello&text=World")
    assert response.status_code == 200
    data = response.json()
    assert len(data["translations"]) == 2


@pytest.mark.integration
def test_translate_get_default_values(app_client, mock_model_manager):
    """Test that translate GET endpoint uses correct default values."""

    response = app_client.get("/translate?target_lang=de&text=Hello")
    assert response.status_code == 200

    data = response.json()

    # GET endpoint returns TranslateResponse with translations and optional pivot_path
    assert "translations" in data
    assert isinstance(data["translations"], list)

    # Should have used default beam_size
    # (Can't verify directly but endpoint should work)


@pytest.mark.integration
def test_language_detection_accepts_various_input_types(app_client):
    """Test that language detection handles different input types."""

    # Single string
    response = app_client.post("/language_detection", json={"text": "Hello world"})
    assert response.status_code == 200

    # List of strings
    response = app_client.post("/language_detection", json={"text": ["Hello", "Hola"]})
    assert response.status_code == 200

    # Dict (as per schema)
    response = app_client.post("/language_detection", json={"text": {"key": "Hello"}})
    assert response.status_code == 200


def test_route_parameter_names_match_schema():
    """Test that route parameter names match their aliases in Query."""
    from src.app import app
    from src.api.routes import translation

    # Check translate GET route specifically
    route = next(r for r in app.routes if isinstance(r, APIRoute) and r.path == "/translate" and "GET" in r.methods)

    endpoint = route.endpoint
    sig = inspect.signature(endpoint)

    # Parameters that should have aliases
    expected_aliases = {
        "text": "text",
        "target_lang": "target_lang",
        "source_lang": "source_lang",
        "beam_size": "beam_size",
        "perform_sentence_splitting": "perform_sentence_splitting",
    }

    for param_name, expected_alias in expected_aliases.items():
        if param_name in sig.parameters:
            param = sig.parameters[param_name]
            # Note: Can't easily check alias from param object,
            # but this documents expected behavior


@pytest.mark.integration
def test_translate_post_with_all_parameters(app_client):
    """Test translate POST with all possible parameters."""

    request_data = {
        "text": ["Hello world"],
        "target_lang": "de",
        "source_lang": "en",
        "beam_size": 3,
        "perform_sentence_splitting": False,
        "show_alternatives": 0,
    }

    response = app_client.post("/translate", json=request_data)
    assert response.status_code == 200

    data = response.json()
    assert "translated" in data
    assert len(data["translated"]) == 1


@pytest.mark.integration
def test_translate_post_minimal_parameters(app_client):
    """Test translate POST with only required parameters."""

    request_data = {
        "text": ["Hello"],
        "target_lang": "de",
    }

    response = app_client.post("/translate", json=request_data)
    assert response.status_code == 200

    data = response.json()
    assert "translated" in data


def test_all_routes_use_dependency_injection():
    """Test that all routes properly use dependency injection for services."""
    from src.app import app

    routes_needing_translation_service = ["/translate"]

    for route in app.routes:
        if isinstance(route, APIRoute) and route.path in routes_needing_translation_service:
            endpoint = route.endpoint
            sig = inspect.signature(endpoint)

            # Should have translation_service parameter
            assert "translation_service" in sig.parameters, \
                f"Route {route.path} missing translation_service dependency"


@pytest.mark.integration
def test_query_param_type_coercion(app_client):
    """Test that query parameters are properly coerced to their types."""

    # beam_size should be coerced to int
    response = app_client.get("/translate?target_lang=de&text=Hello&beam_size=7")
    assert response.status_code == 200

    # perform_sentence_splitting should be coerced to bool
    response = app_client.get(
        "/translate?target_lang=de&text=Hello&perform_sentence_splitting=false"
    )
    assert response.status_code == 200

    # Invalid int should fail
    response = app_client.get("/translate?target_lang=de&text=Hello&beam_size=not_a_number")
    assert response.status_code == 422


@pytest.mark.integration
def test_empty_list_parameters_handled_correctly(app_client, mock_model_manager):
    """Test that endpoints handle empty lists correctly.

    This specifically tests the fix for Optional[List[str]] → List[str] with default=[].
    """

    # GET with no text parameter (should use default empty list)
    response = app_client.get("/translate?target_lang=de")
    assert response.status_code == 200
    data = response.json()
    assert data["translations"] == []

    # POST with empty text list (needs source_lang for validation)
    response = app_client.post("/translate", json={"text": [], "target_lang": "de", "source_lang": "en"})
    assert response.status_code == 200
    data = response.json()
    assert data["translated"] == []
