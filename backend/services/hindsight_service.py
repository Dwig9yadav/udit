"""Hindsight memory integration service with safe no-op fallbacks."""

import logging
import os
import re
from typing import Any, Dict, List, Optional

try:
    from hindsight_client import Hindsight
except ImportError:  # package not installed — run in disabled mode
    Hindsight = None  # type: ignore

# Hardware/Service configuration
logger = logging.getLogger(__name__)

HINDSIGHT_ENABLED = os.getenv("HINDSIGHT_ENABLED", "false").lower() in {"1", "true", "yes"}
HINDSIGHT_BASE_URL = (os.getenv("HINDSIGHT_BASE_URL") or "https://api.hindsight.vectorize.io").rstrip("/")
HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY", "")
HINDSIGHT_TIMEOUT = float(os.getenv("HINDSIGHT_TIMEOUT", "6"))

# Default bank to use if no user-specific bank is found
# We saw 'udit' and 'dwig' in the bank list, using 'udit' as default for now
HINDSIGHT_DEFAULT_BANK = os.getenv("HINDSIGHT_DEFAULT_BANK", "udit")

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?(?:\d[\s-]?){9,12}(?!\d)")

# Initialize the global client
_client: Optional[Hindsight] = None

def get_client() -> Optional["Hindsight"]:
    global _client
    if not HINDSIGHT_ENABLED:
        return None
    if Hindsight is None:
        logger.error("hindsight_client package is not installed. Run: pip install hindsight-client")
        return None
    if _client is None:
        try:
            _client = Hindsight(api_key=HINDSIGHT_API_KEY, base_url=HINDSIGHT_BASE_URL)
        except Exception as e:
            logger.error(f"Failed to initialize Hindsight client: {e}")
            return None
    return _client

def is_enabled() -> bool:
    """Return True only when Hindsight integration is configured and enabled."""
    return bool(HINDSIGHT_ENABLED and HINDSIGHT_BASE_URL and HINDSIGHT_API_KEY)

def redact_pii(text: str) -> str:
    """Anonymize emails and phone numbers before storage."""
    if not text:
        return text
    text = EMAIL_PATTERN.sub("[EMAIL]", text)
    text = PHONE_PATTERN.sub("[PHONE]", text)
    return text

def build_bank_id(user: Optional[dict], bank_id: Optional[str] = None) -> str:
    """Build a stable bank identifier for the current user."""
    if bank_id:
        return bank_id
    
    # Try to find a bank ID from user metadata or name
    if user:
        username = user.get("name") or str(user.get("id"))
        # In Hindsight, we saw banks named 'udit' and 'dwig'. 
        # If the current user's name is in that list, use it.
        # Otherwise, fall back to the default or a user-specific bank
        if username.lower() in {"udit", "dwig"}:
            return username.lower()
            
    return HINDSIGHT_DEFAULT_BANK

async def retain(
    *,
    bank_id: str,
    content: str,
    fact_type: str = "experience_fact",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Store a fact in Hindsight memory bank (Async)."""
    client = get_client()
    if not client:
        return {"ok": False, "disabled": True}

    print(f"DEBUG: Hindsight RETAIN called for bank_id: {bank_id}")
    try:
        merged_metadata = metadata or {}
        if fact_type:
            merged_metadata["original_fact_type"] = fact_type
            
        # The Hindsight SDK requires metadata values to be strings
        string_metadata = {k: str(v) for k, v in merged_metadata.items()}
            
        result = await client.aretain(
            bank_id=bank_id,
            content=redact_pii(content),
            metadata=string_metadata
        )
        return {"ok": True, "result": str(result)}
    except Exception as exc:
        logger.warning("Hindsight retain failed: %s", exc)
        return {"ok": False, "error": str(exc)}

async def recall(*, bank_id: str, query: str, limit: int = 5) -> Dict[str, Any]:
    """Retrieve candidate memories for a query (Async)."""
    client = get_client()
    if not client:
        return {"ok": False, "disabled": True}

    print(f"DEBUG: Hindsight RECALL called for bank_id: {bank_id}")
    try:
        response = await client.arecall(
            bank_id=bank_id,
            query=redact_pii(query),
        )
        memories = response.results if hasattr(response, 'results') else []
        if limit and len(memories) > limit:
            memories = memories[:limit]
        return {"ok": True, "memories": memories}
    except Exception as exc:
        logger.warning("Hindsight recall failed: %s", exc)
        return {"ok": False, "error": str(exc)}

async def reflect(
    *,
    bank_id: str,
    query: str,
    mission: Optional[str] = None,
    directives: Optional[List[str]] = None,
    disposition: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Run Hindsight reflect against memory bank configuration (Async)."""
    client = get_client()
    if not client:
        return {"ok": False, "disabled": True}

    try:
        response = await client.areflect(
            bank_id=bank_id,
            query=redact_pii(query),
            context=mission,
            budget="low"  # default budget
        )
        # In SDK 0.1.0, the answer is in .text attribute
        answer = getattr(response, 'text', getattr(response, 'answer', ""))
        return {"ok": True, "answer": answer}
    except Exception as exc:
        logger.warning("Hindsight reflect failed: %s", exc)
        return {"ok": False, "error": str(exc)}

async def retain_chat_message(user: dict, message: str) -> Dict[str, Any]:
    """Best-effort background retention of user chat input."""
    if not is_enabled():
        return {"ok": False}
    
    bank_id = build_bank_id(user)
    content = f"User chat message: {message}"
    metadata = {
        "source": "chat",
        "user_id": user.get("id"),
        "institution_id": user.get("institution_id"),
    }
    return await retain(bank_id=bank_id, content=content, fact_type="experience_fact", metadata=metadata)

async def recall_interaction_context(user: dict, query: str) -> str:
    """Personalization helper: recall recent context based on query."""
    if not is_enabled():
        return ""

    bank_id = build_bank_id(user)
    res = await recall(bank_id=bank_id, query=query, limit=5)
    
    if not res.get("ok"):
        return ""
    
    memories = res.get("memories", [])
    if not memories:
        return ""
        
    context_chunks = []
    for m in memories:
        content = getattr(m, 'content', str(m))
        context_chunks.append(f"- {content}")
        
    return "\n".join(context_chunks)


async def retain_rag_search(user: dict, query: str, language: str, results_count: int, retrieval_mode: str) -> Dict[str, Any]:
    """Best-effort retain for RAG interactions."""
    bank_id = build_bank_id(user)
    content = (
        f"User asked: {query}. Language={language}. "
        f"Retrieved {results_count} results via {retrieval_mode}."
    )
    metadata = {
        "source": "rag_search",
        "user_id": user.get("id"),
        "language": language,
        "results_count": results_count,
        "retrieval_mode": retrieval_mode,
    }
    return await retain(bank_id=bank_id, content=content, fact_type="experience_fact", metadata=metadata)
