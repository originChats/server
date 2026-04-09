from aiohttp import web
import json
from typing import Any, Dict, Optional


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS, POST",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, Range",
    "Access-Control-Expose-Headers": "Content-Length, Content-Type, Cache-Control",
}


def _apply_cors(response: web.Response) -> web.Response:
    """Apply CORS headers to a response."""
    for k, v in CORS_HEADERS.items():
        response.headers[k] = v
    return response


def json_response(data: Any, status: int = 200) -> web.Response:
    """
    Create a CORS-enabled JSON response.
    
    Args:
        data: Data to serialize as JSON
        status: HTTP status code (default 200)
    
    Returns:
        web.Response with CORS headers and JSON content type
    """
    return _apply_cors(web.Response(
        status=status,
        content_type="application/json",
        text=json.dumps(data) if not isinstance(data, str) else data
    ))


def json_error(message: str, status: int = 400) -> web.Response:
    """
    Create a CORS-enabled JSON error response.
    
    Args:
        message: Error message
        status: HTTP status code (default 400)
    
    Returns:
        web.Response with CORS headers and error JSON
    """
    return json_response({"error": message}, status=status)


def text_response(text: str, status: int = 200, content_type: str = "text/plain") -> web.Response:
    """
    Create a CORS-enabled text response.
    
    Args:
        text: Response text
        status: HTTP status code (default 200)
        content_type: Content type header (default text/plain)
    
    Returns:
        web.Response with CORS headers
    """
    return _apply_cors(web.Response(status=status, text=text, content_type=content_type))


def file_response(file_path: str, cache_max_age: int = 3600, content_type: Optional[str] = None) -> web.Response:
    """
    Create a CORS-enabled file response with caching.
    
    Args:
        file_path: Path to the file to serve
        cache_max_age: Cache-Control max-age in seconds (default 3600)
        content_type: Optional content type override
    
    Returns:
        web.FileResponse with CORS headers and caching
    """
    headers = {
        "Cache-Control": f"public, max-age={cache_max_age}",
        **CORS_HEADERS
    }
    return web.FileResponse(file_path, headers=headers)


def options_response() -> web.Response:
    """
    Create a CORS preflight OPTIONS response.
    
    Returns:
        web.Response with status 204 and CORS headers
    """
    return _apply_cors(web.Response(status=204))


def not_found_response(message: str = "Not found") -> web.Response:
    """
    Create a 404 JSON error response.
    
    Args:
        message: Error message (default "Not found")
    
    Returns:
        web.Response with 404 status
    """
    return json_error(message, status=404)


def bad_request_response(message: str) -> web.Response:
    """
    Create a 400 JSON error response.
    
    Args:
        message: Error message
    
    Returns:
        web.Response with 400 status
    """
    return json_error(message, status=400)


def unauthorized_response(message: str = "Unauthorized") -> web.Response:
    """
    Create a 401 JSON error response.
    
    Args:
        message: Error message (default "Unauthorized")
    
    Returns:
        web.Response with 401 status
    """
    return json_error(message, status=401)


def forbidden_response(message: str = "Forbidden") -> web.Response:
    """
    Create a 403 JSON error response.
    
    Args:
        message: Error message (default "Forbidden")
    
    Returns:
        web.Response with 403 status
    """
    return json_error(message, status=403)


def service_unavailable_response(message: str = "Service unavailable") -> web.Response:
    """
    Create a 503 JSON error response.
    
    Args:
        message: Error message (default "Service unavailable")
    
    Returns:
        web.Response with 503 status
    """
    return json_error(message, status=503)


def no_content_response() -> web.Response:
    """
    Create a 204 No Content response.
    
    Returns:
        web.Response with 204 status
    """
    return _apply_cors(web.Response(status=204))
