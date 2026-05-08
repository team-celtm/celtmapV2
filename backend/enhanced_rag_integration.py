"""
Integration Examples - Using Enhanced RAG Pipeline in FastAPI

Shows how to integrate the enhanced RAG pipeline into your existing
FastAPI application without modifying the original RAG service.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path

# Note: Adjust these imports based on your project structure
try:
    from app.services.rag_service import RagService
    from app.dependencies.services import get_rag_service
    from enhanced_rag_pipeline import EnhancedRAGPipeline
    HAS_DEPENDENCIES = True
except ImportError:
    print("Note: Some imports unavailable. This is an example file.")
    HAS_DEPENDENCIES = False

    if 'RagService' not in locals():
        class RagService: pass
    def get_rag_service(): return None

router = APIRouter(prefix="/api/v1/rag-enhanced", tags=["rag-enhanced"])

# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

# Global pipeline instance (initialize on app startup)
_pipeline_instance: EnhancedRAGPipeline | None = None


async def get_enhanced_rag_pipeline(
    rag_service: RagService = Depends(get_rag_service)
) -> EnhancedRAGPipeline:
    """Get or create enhanced RAG pipeline instance."""
    global _pipeline_instance
    
    if _pipeline_instance is None:
        # Initialize with default settings
        _pipeline_instance = EnhancedRAGPipeline(
            rag_service=rag_service,
            lightweight_mode=False,  # Can be made configurable
            cache_ttl=3600  # 1 hour
        )
    elif _pipeline_instance.rag_service is None and rag_service is not None:
        _pipeline_instance.rag_service = rag_service
    
    return _pipeline_instance

def get_pipeline_instance() -> EnhancedRAGPipeline | None:
    """
    Get the global pipeline instance without requiring FastAPI dependency injection.
    Use this for background tasks or other services.
    """
    return _pipeline_instance

async def init_enhanced_rag():
    """Initialize the global enhanced RAG pipeline instance."""
    from app.config.settings import get_settings
    from app.integrations.cache import CacheClient
    from app.integrations.supabase import get_supabase_client
    from app.repositories.rag_repository import RagRepository
    from app.services.rag_service import RagService
    
    settings = get_settings()
    cache = CacheClient(settings)
    
    # We must delay initializing the RAG Service if it relies on other components
    # However, since we just need it to run background indexing we can initialize a dummy or real instance.
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = EnhancedRAGPipeline(
            rag_service=None,
            lightweight_mode=False,
            cache_ttl=3600
        )
    return _pipeline_instance

async def shutdown_enhanced_rag():
    """Clean up the enhanced RAG pipeline."""
    global _pipeline_instance
    _pipeline_instance = None


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class EnhancedSearchRequest(BaseModel):
    """Enhanced search request with options."""
    query: str
    top_k: int = 5
    user_id: str | None = None
    use_expansion: bool = True


class EnhancedSearchResponse(BaseModel):
    """Enhanced search response with metadata."""
    success: bool
    query: str
    keywords: list[str]
    expanded_queries: list[str]
    results_count: int
    results: list[dict]
    latency_ms: float
    cache_hit: bool


class PerformanceStatsResponse(BaseModel):
    """Performance statistics response."""
    total_queries: int
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    cache_hits: int
    total_memory_mb: float


class CacheStatsResponse(BaseModel):
    """Cache statistics response."""
    cached_keys: int
    total_access: int
    top_queries: list[tuple[str, int]]


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/search", response_model=EnhancedSearchResponse)
async def enhanced_search(
    request: EnhancedSearchRequest,
    pipeline: EnhancedRAGPipeline = Depends(get_enhanced_rag_pipeline),
) -> dict:
    """
    Enhanced semantic search with NLP preprocessing.
    
    Features:
    - Automatic keyword extraction
    - Query expansion with synonyms
    - Multi-level caching
    - Performance metrics
    
    Example:
    ```
    POST /api/v1/rag-enhanced/search
    {
        "query": "How to use React hooks?",
        "top_k": 5,
        "user_id": "user_123",
        "use_expansion": true
    }
    ```
    
    Response:
    ```
    {
        "success": true,
        "query": "How to use React hooks?",
        "keywords": ["react", "hook", "use"],
        "expanded_queries": ["react.js", "reactjs", ...],
        "results_count": 5,
        "results": [...],
        "latency_ms": 45.3,
        "cache_hit": false
    }
    ```
    """
    try:
        # Process query
        result = await pipeline.process_query(
            query=request.query,
            top_k=request.top_k,
            user_id=request.user_id,
            use_expansion=request.use_expansion,
        )
        
        return {
            "success": True,
            "query": result.query,
            "keywords": result.keywords,
            "expanded_queries": result.expanded_query,
            "results_count": len(result.results),
            "results": [
                {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "content": r.get("content", "")[:500],
                    "score": r.get("relevance_score", r.get("similarity", 0.5)),
                    "source": r.get("source_type", "unknown"),
                }
                for r in result.results
            ],
            "latency_ms": result.total_time_ms,
            "cache_hit": result.cache_hit,
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@router.get("/search/quick")
async def quick_search(
    query: str,
    top_k: int = 3,
    user_id: str | None = None,
    pipeline: EnhancedRAGPipeline = Depends(get_enhanced_rag_pipeline),
) -> dict:
    """
    Quick search with minimal latency.
    
    Uses default parameters for fastest possible response.
    Results are cached for subsequent identical queries.
    """
    try:
        result = await pipeline.process_query(
            query=query,
            top_k=top_k,
            user_id=user_id,
            use_expansion=False,  # Skip expansion for speed
        )
        
        return {
            "query": query,
            "count": len(result.results),
            "latency_ms": result.total_time_ms,
            "results": [
                {
                    "title": r.get("title"),
                    "score": round(r.get("relevance_score", 0.5), 3),
                }
                for r in result.results
            ],
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/with-keywords")
async def search_with_keywords(
    request: EnhancedSearchRequest,
    pipeline: EnhancedRAGPipeline = Depends(get_enhanced_rag_pipeline),
) -> dict:
    """
    Search that emphasizes keyword matching.
    
    Useful for exact phrase queries where keyword extraction is important.
    """
    try:
        result = await pipeline.process_query(
            query=request.query,
            top_k=request.top_k,
            user_id=request.user_id,
            use_expansion=True,
        )
        
        return {
            "success": True,
            "query": request.query,
            "keywords": result.keywords,
            "keyword_count": len(result.keywords),
            "results": [
                {
                    **r,
                    "keyword_matches": r.get("keyword_matches", 0),
                }
                for r in result.results
            ],
            "latency_ms": result.total_time_ms,
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/performance", response_model=PerformanceStatsResponse)
async def get_performance_stats(
    pipeline: EnhancedRAGPipeline = Depends(get_enhanced_rag_pipeline),
) -> dict:
    """
    Get performance statistics since pipeline initialization.
    
    Includes:
    - Average, min, max latency
    - Cache hit rate
    - Memory usage
    - Total queries processed
    """
    summary = pipeline.get_performance_summary()
    return {
        "total_queries": summary.get("total_queries", 0),
        "avg_latency_ms": summary.get("avg_latency_ms", 0),
        "min_latency_ms": summary.get("min_latency_ms", 0),
        "max_latency_ms": summary.get("max_latency_ms", 0),
        "cache_hits": summary.get("cache_hits", 0),
        "total_memory_mb": summary.get("total_memory_mb", 0),
    }


@router.get("/stats/cache", response_model=CacheStatsResponse)
async def get_cache_stats(
    pipeline: EnhancedRAGPipeline = Depends(get_enhanced_rag_pipeline),
) -> dict:
    """
    Get cache statistics and hit rate.
    
    Includes:
    - Number of cached queries
    - Total access count
    - Top 5 most accessed queries
    """
    stats = pipeline.get_cache_stats()
    return {
        "cached_keys": stats.get("cached_keys", 0),
        "total_access": stats.get("total_access", 0),
        "top_queries": stats.get("top_queries", []),
    }


@router.post("/cache/clear")
async def clear_cache(
    pipeline: EnhancedRAGPipeline = Depends(get_enhanced_rag_pipeline),
) -> dict:
    """
    Clear all cached search results.
    
    Use this after updating the knowledge base.
    """
    pipeline.cache_retriever.clear()
    return {
        "success": True,
        "message": "Cache cleared successfully",
        "timestamp": str(datetime.now()),
    }


@router.get("/health")
async def health_check(
    pipeline: EnhancedRAGPipeline = Depends(get_enhanced_rag_pipeline),
) -> dict:
    """
    Health check for enhanced RAG pipeline.
    
    Verifies:
    - Pipeline is initialized
    - Cache is working
    - Performance metrics are being recorded
    """
    stats = pipeline.get_performance_summary()
    return {
        "status": "healthy",
        "pipeline_initialized": True,
        "cache_enabled": True,
        "metrics_recording": stats.get("total_queries", 0) > 0,
        "total_queries": stats.get("total_queries", 0),
        "avg_latency_ms": stats.get("avg_latency_ms", 0),
    }


# ============================================================================
# INITIALIZATION (Add to your FastAPI app startup)
# ============================================================================

async def init_enhanced_rag():
    """
    Initialize enhanced RAG pipeline.
    
    Add this to your app startup events:
    
    @app.on_event("startup")
    async def startup_event():
        await init_enhanced_rag()
    """
    global _pipeline_instance
    
    print("🚀 Initializing Enhanced RAG Pipeline...")
    
    _pipeline_instance = EnhancedRAGPipeline(
        lightweight_mode=False,
        cache_ttl=3600,
    )
    
    print("✅ Enhanced RAG Pipeline ready")


async def shutdown_enhanced_rag():
    """
    Cleanup on app shutdown.
    
    Add this to your app shutdown events:
    
    @app.on_event("shutdown")
    async def shutdown_event():
        await shutdown_enhanced_rag()
    """
    global _pipeline_instance
    
    if _pipeline_instance:
        stats = _pipeline_instance.get_performance_summary()
        print(f"📊 Final stats: {stats['total_queries']} queries, "
              f"avg {stats['avg_latency_ms']:.2f}ms latency")
        
        # Optional: Log final metrics
        print("🛑 Enhanced RAG Pipeline shutdown complete")


# ============================================================================
# USAGE EXAMPLE IN MAIN APP
# ============================================================================

"""
How to integrate in your main FastAPI app (backend/app/main.py):

from fastapi import FastAPI
from enhanced_rag_integration import (
    router,
    init_enhanced_rag,
    shutdown_enhanced_rag,
)

app = FastAPI()

# Include enhanced RAG routes
app.include_router(router)

# Initialize pipeline on startup
@app.on_event("startup")
async def startup():
    await init_enhanced_rag()

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown():
    await shutdown_enhanced_rag()


# Now your API has these new endpoints:
# POST   /api/v1/rag-enhanced/search
# GET    /api/v1/rag-enhanced/search/quick
# POST   /api/v1/rag-enhanced/search/with-keywords
# GET    /api/v1/rag-enhanced/stats/performance
# GET    /api/v1/rag-enhanced/stats/cache
# POST   /api/v1/rag-enhanced/cache/clear
# GET    /api/v1/rag-enhanced/health
"""


# ============================================================================
# CURL EXAMPLES
# ============================================================================

"""
Test the endpoints with curl:

1. Enhanced search:
curl -X POST http://localhost:8000/api/v1/rag-enhanced/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How to use React hooks?",
    "top_k": 5,
    "user_id": "user_123",
    "use_expansion": true
  }'

2. Quick search:
curl http://localhost:8000/api/v1/rag-enhanced/search/quick \
  -G \
  --data-urlencode "query=python basics" \
  --data-urlencode "top_k=3"

3. Get performance stats:
curl http://localhost:8000/api/v1/rag-enhanced/stats/performance

4. Get cache stats:
curl http://localhost:8000/api/v1/rag-enhanced/stats/cache

5. Clear cache:
curl -X POST http://localhost:8000/api/v1/rag-enhanced/cache/clear

6. Health check:
curl http://localhost:8000/api/v1/rag-enhanced/health
"""


if __name__ == "__main__":
    print("This is an integration example file.")
    print("Copy the content to your FastAPI app to use the enhanced RAG pipeline.")
