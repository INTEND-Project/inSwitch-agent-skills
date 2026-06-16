"""Remote HTTP request tool.

Thin wrapper around ``requests.request``. Network errors are not caught
here — they propagate to the dispatch layer, which converts them to
``{"error": "..."}`` so the LLM can react.
"""

from typing import Any, Dict

import requests

from core.tools import tool, ToolContext


@tool(
    name="http_request",
    description="Call a remote HTTP API and return status, headers, and body.",
    parameters={
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "description": "HTTP method, e.g. GET, POST.",
            },
            "url": {"type": "string", "description": "Full URL."},
            "headers": {"type": "object", "description": "HTTP headers."},
            "params": {"type": "object", "description": "Query parameters."},
            "json": {"type": "object", "description": "JSON body."},
            "data": {"type": "string", "description": "Raw body as string."},
            "timeout": {"type": "number", "description": "Timeout in seconds."},
        },
        "required": ["method", "url"],
    },
)
def http_request(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    response = requests.request(
        method=args.get("method", "GET"),
        url=args.get("url", ""),
        headers=args.get("headers"),
        params=args.get("params"),
        json=args.get("json"),
        data=args.get("data"),
        timeout=args.get("timeout") or 30,
    )
    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": response.text,
    }