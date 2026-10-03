"""Pagination utility helpers module.

Provides calculation helpers for paginated queries and page metadata responses.
"""
from typing import Any, Dict, List


def format_paginated_response(
    items: List[Any],
    total_count: int,
    page: int,
    page_size: int,
) -> Dict[str, Any]:
    """Calculate pagination metadata and wrap result items."""
    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "items": items,
        "pagination": {
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }
