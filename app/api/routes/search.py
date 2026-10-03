from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_search_service
from app.schemas.search import (
    HybridSearchRequest,
    SearchResponse,
    SemanticSearchRequest,
)
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Search"])


@router.post(
    "/semantic",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic vector search for candidates",
    description="Vectorizes natural language job descriptions/queries and queries MongoDB Atlas Vector Search.",
)
async def semantic_search(
    request: SemanticSearchRequest,
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """Execute semantic candidate search."""
    return search_service.semantic_search(request)


@router.post(
    "/hybrid",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid candidate search (semantic vector + hard filters)",
    description="Combines 384-dimensional vector relevance with hard skill/experience filters and weighted ranking.",
)
async def hybrid_search(
    request: HybridSearchRequest,
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """Execute hybrid candidate search."""
    return search_service.hybrid_search(request)
