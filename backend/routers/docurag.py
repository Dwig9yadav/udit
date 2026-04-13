
"""
RAG Router for MINI-RAG Backend

Provides endpoints for Retrieval-Augmented Generation (RAG) document search, PDF upload, and management.
All PDFs are uploaded to the Supabase Storage bucket "pdfs". No local storage is used.
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from typing import List, Optional
from datetime import datetime
import os
import time
import json
import math
import tempfile
import logging
import re
from groq import Groq

from models import RAGQuery
from database import get_supabase
from routers.auth import get_current_user
from services.hindsight_service import retain_rag_search, recall as memory_recall, build_bank_id

router = APIRouter()
logger = logging.getLogger(__name__)

STORAGE_BUCKET = "pdfs"   # Supabase Storage bucket name

EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
MULTIMODAL_EMBEDDING_MODEL = os.getenv("GEMINI_MULTIMODAL_EMBEDDING_MODEL", "")
GENERATION_MODEL = os.getenv("GEMINI_GENERATION_MODEL", "models/gemini-1.5-flash")
GENERATION_MODEL_FALLBACK = os.getenv("GEMINI_GENERATION_MODEL_FALLBACK", "models/gemini-2.0-flash")


def _get_gemini_client():
    """
    Initialize and return a Gemini API client using the API key from environment variables.
    Returns None if the API key is not set or the client cannot be created.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY missing. If on Vercel, set it in Project Settings -> Environment Variables.")
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as exc:
        logger.error(f"Failed to initialize Gemini client: {exc}")
        return None


def _get_groq_client():
    """
    Initialize and return a Groq API client using the API key from environment variables.
    Returns None if the API key is not set or the client cannot be created.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY missing in .env")
        return None
    try:
        return Groq(api_key=api_key)
    except Exception as exc:
        logger.error(f"Failed to initialize Groq client: {exc}")
        return None


def _safe_mime_type(image_bytes: bytes) -> str:
    """
    Detect the MIME type of image bytes (JPEG, PNG, GIF) or return octet-stream as fallback.
    """
    if image_bytes.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG"):
        return "image/png"
    if image_bytes.startswith(b"GIF8"):
        return "image/gif"
    return "application/octet-stream"


def _extract_text_and_images_from_pdf(pdf_path: str):
    """
    Extract text and images from a local PDF file path.
    Returns a list of pages, each with text and images, and the total number of pages.
    """
    pages = []
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError("pypdf is required for PDF parsing") from exc

    reader = PdfReader(pdf_path)
    for page_number, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        page_images = []
        try:
            for image_file in getattr(page, "images", []):
                if getattr(image_file, "data", None):
                    page_images.append(image_file.data)
        except Exception:
            page_images = []

        pages.append({
            "page_number": page_number,
            "text": page_text,
            "images": page_images,
        })

    return pages, len(reader.pages)


def _download_pdf_from_storage(sb, storage_path: str) -> str:
    """
    Download a PDF from Supabase Storage to a temporary file.
    Returns the temporary file path.
    """
    data = sb.storage.from_(STORAGE_BUCKET).download(storage_path)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(data)
    tmp.close()
    return tmp.name


def _ensure_storage_bucket(sb):
    """
    Ensure the Supabase storage bucket exists; create it if it does not.
    """
    try:
        sb.storage.get_bucket(STORAGE_BUCKET)
    except Exception:
        try:
            sb.storage.create_bucket(STORAGE_BUCKET, options={"public": False})
        except Exception:
            pass  # bucket may already exist


def _embed_text(client, text: str, max_retries: int = 5):
    """
    Generate an embedding vector for the given text using the Gemini client.
    Includes a 35-second retry for status 429 (Quota Exceeded).
    """
    if not client or not text.strip():
        return None
    
    for attempt in range(max_retries):
        try:
            response = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
            )
            if hasattr(response, "embeddings") and response.embeddings:
                return response.embeddings[0].values
            if hasattr(response, "embedding") and response.embedding:
                return response.embedding.values
            return None
        except Exception as exc:
            err_msg = str(exc).lower()
            if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
                wait_time = 35 
                logger.warning(f"Embedding Quota hit. Waiting {wait_time}s before retry {attempt+1}/{max_retries}...")
                time.sleep(wait_time)
                continue
            logger.error(f"Embedding failed: {exc}")
            return None
    return None


def _try_multimodal_embed(client, image_bytes: bytes, page_text: str, max_retries: int = 3):
    """
    Generate a multimodal embedding for an image.
    Includes a 40-second retry for status 429.
    """
    if not client or not MULTIMODAL_EMBEDDING_MODEL:
        return None
    for attempt in range(max_retries):
        try:
            mime_type = _safe_mime_type(image_bytes)
            response = client.models.embed_content(
                model=MULTIMODAL_EMBEDDING_MODEL,
                contents=[
                    {
                        "parts": [
                            {"text": page_text or "Describe this educational image"},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": image_bytes,
                                }
                            },
                        ]
                    }
                ],
            )
            if hasattr(response, "embeddings") and response.embeddings:
                return response.embeddings[0].values
            return None
        except Exception as exc:
            err_msg = str(exc).lower()
            if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
                time.sleep(40)
                continue
            return None
    return None


def _caption_image_with_gemini(client, image_bytes: bytes, max_retries: int = 3):
    """
    Generate a factual caption for an image.
    Includes a 40-second retry for status 429.
    """
    if not client:
        return ""
    mime_type = _safe_mime_type(image_bytes)
    prompt = "Describe this educational image factually for RAG indexing."

    for attempt in range(max_retries):
        try:
            from google.genai import types
            response = client.models.generate_content(
                model=GENERATION_MODEL,
                contents=[prompt, types.Part.from_bytes(data=image_bytes, mime_type=mime_type)],
            )
            return (response.text or "").strip()
        except Exception as exc:
            err_msg = str(exc).lower()
            if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
                logger.warning(f"Captioning Quota hit. Waiting 40s...")
                time.sleep(40)
                continue
            return ""
    return ""


def _chunk_text(raw_text: str, chunk_size: int = 900, overlap: int = 120):
    """
    Split raw text into overlapping chunks for embedding and retrieval.
    Returns a list of text chunks.
    """
    normalized = " ".join(raw_text.split())
    if not normalized:
        return []

    chunks = []
    start_index = 0
    text_length = len(normalized)
    while start_index < text_length:
        end_index = min(start_index + chunk_size, text_length)
        chunk = normalized[start_index:end_index].strip()
        if chunk:
            chunks.append(chunk)
        if end_index == text_length:
            break
        start_index = max(0, end_index - overlap)
    return chunks


def _cosine_similarity(vector_a, vector_b):
    """
    Compute the cosine similarity between two vectors.
    Returns a float between 0.0 and 1.0.
    """
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _token_overlap_score(query_text: str, document_text: str) -> float:
    """Compute lexical overlap ratio between query and chunk text."""
    query_tokens = {tok for tok in re.findall(r"[a-zA-Z0-9_\u0900-\u097F]+", (query_text or "").lower()) if len(tok) > 2}
    if not query_tokens:
        return 0.0
    doc_tokens = {tok for tok in re.findall(r"[a-zA-Z0-9_\u0900-\u097F]+", (document_text or "").lower()) if len(tok) > 2}
    if not doc_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(doc_tokens))
    return overlap / len(query_tokens)


def _phrase_match_score(query_text: str, document_text: str) -> float:
    """Reward exact phrase presence for high-intent queries."""
    query_clean = " ".join((query_text or "").lower().split())
    doc_clean = " ".join((document_text or "").lower().split())
    if not query_clean or not doc_clean:
        return 0.0
    return 1.0 if query_clean in doc_clean else 0.0


def _language_alignment_score(language: str, document_text: str) -> float:
    """Estimate match quality between requested language and chunk script/content."""
    doc = document_text or ""
    if not doc.strip():
        return 0.0
    lang = (language or "english").lower()
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", doc))
    has_latin = bool(re.search(r"[A-Za-z]", doc))

    if lang == "hindi":
        return 1.0 if has_devanagari else 0.2
    if lang == "hinglish":
        return 1.0 if (has_devanagari and has_latin) else 0.5 if (has_devanagari or has_latin) else 0.1
    return 1.0 if has_latin else 0.3


def _generate_rag_answer(client, user_query: str, retrieved_results: list, language: str = "english", memory_context: list = None):
    """
    Generate an answer to the user query using retrieved context and Gemini models.
    Returns the generated answer as a string.
    """
    if not client or not retrieved_results:
        return "Could not generate an AI answer. Please check that your Gemini API key is configured."

    context_lines = []
    memory_lines = [line for line in (memory_context or []) if isinstance(line, str) and line.strip()]
    for idx, result in enumerate(retrieved_results[:5], 1):
        source_name = result.get('source', 'Unknown')
        page = result.get('page_number', 1)
        context_lines.append(
            f"[Source {idx}: {source_name}, Page {page}]\n{result['content']}"
        )

    language_instruction = {
        "hindi": "Write your final answer in Hindi.",
        "hinglish": "Write your final answer in Hinglish (Hindi + English mix).",
    }.get((language or "english").lower(), "Write your final answer in English.")

    prompt = (
        "You are EduRag, an intelligent educational RAG (Retrieval-Augmented Generation) assistant.\n"
        "Your job is to generate a clear, helpful, and well-structured answer based ONLY on the retrieved context below.\n"
        "IMPORTANT RULES:\n"
        "1. Synthesize the information into a coherent answer — do NOT just copy-paste chunks.\n"
        "1a. Use memory context only for personalization and continuity; do not present memory assumptions as factual citations.\n"
        "2. At the END of your answer, add a 'Sources:' section listing which sources you used "
        "(e.g., 'Sources: Source 1 (filename.pdf, Page 3), Source 2 (filename.pdf, Page 7)').\n"
        "3. If the context does not contain enough info, say so clearly.\n"
        "4. Keep the answer educational, concise, and well-formatted.\n"
        f"5. {language_instruction}\n\n"
        + (
            "Memory Context (for personalization only):\n"
            + "\n".join(f"- {line}" for line in memory_lines[:5])
            + "\n\n"
            if memory_lines else ""
        )
        + f"Student's Question: {user_query}\n\n"
        + "Retrieved Context:\n"
        + "\n\n".join(context_lines)
    )

    # Try primary model, then fallback
    for model in [GENERATION_MODEL, GENERATION_MODEL_FALLBACK]:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            text = (response.text or "").strip()
            if text:
                return text
        except Exception as e:
            logger.warning("Generation failed with %s: %s", model, e)
            continue

    # If both models fail, construct a basic answer from chunks
    fallback_text = f"Here is what I found about \"{user_query}\":\n\n"
    for idx, result in enumerate(retrieved_results[:3], 1):
        fallback_text += f"{idx}. {result['content'][:300]}...\n\n"
    fallback_text += "Sources: " + ", ".join(
        f"{r['source']} (Page {r.get('page_number', 1)})" for r in retrieved_results[:3]
    )
    return fallback_text

@router.post("/search")
async def search_documents(
    query: RAGQuery,
    current_user: dict = Depends(get_current_user),
):
    """
    Search documents using Retrieval-Augmented Generation (RAG) from Supabase.
    Returns relevant results and a generated answer.
    """
    start_time = time.time()
    gemini_client = _get_gemini_client()
    retrieval_mode = "keyword"
    used_multimodal = False
    memory_context = []

    try:
        sb = get_supabase()
        results = []
        query_vector = _embed_text(gemini_client, query.query)

        # Minimum cosine similarity threshold — below this, results are noise
        SIMILARITY_THRESHOLD = 0.65

        if query_vector:
            # Fetch all embeddings with their chunk content via join-like approach
            emb_rows = sb.table("rag_embeddings").select("id, pdf_chunk_id, modality, embedding_json").execute().data or []

            # Batch-fetch all referenced chunks
            chunk_ids = list({r["pdf_chunk_id"] for r in emb_rows if r.get("pdf_chunk_id")})
            chunk_map = {}
            if chunk_ids:
                # Supabase .in_() has a limit; batch if needed
                for i in range(0, len(chunk_ids), 200):
                    batch = chunk_ids[i:i+200]
                    c_resp = sb.table("pdf_chunks").select("id, content, source_file, page_number").in_("id", batch).execute()
                    for c in (c_resp.data or []):
                        chunk_map[c["id"]] = c

            ranked = []
            for emb in emb_rows:
                try:
                    chunk_vector = json.loads(emb["embedding_json"])
                    similarity = _cosine_similarity(query_vector, chunk_vector)
                except Exception:
                    similarity = 0.0

                # Only keep results above the threshold
                if similarity >= SIMILARITY_THRESHOLD:
                    if emb.get("modality") == "multimodal":
                        used_multimodal = True
                    chunk = chunk_map.get(emb["pdf_chunk_id"])
                    if chunk:
                        lexical = _token_overlap_score(query.query, chunk.get("content", ""))
                        phrase = _phrase_match_score(query.query, chunk.get("content", ""))
                        language_bonus = _language_alignment_score(query.language, chunk.get("content", ""))
                        blended_score = (0.68 * similarity) + (0.18 * lexical) + (0.08 * phrase) + (0.06 * language_bonus)
                        ranked.append((blended_score, chunk, chunk_vector))

            ranked.sort(key=lambda item: item[0], reverse=True)

            selected = []
            selected_vectors = []
            diversity_lambda = 0.82
            for score, chunk, vector in ranked:
                if len(selected) >= 5:
                    break
                if not selected_vectors:
                    selected.append((score, chunk))
                    selected_vectors.append(vector)
                    continue
                max_sim_to_selected = max(_cosine_similarity(vector, vec) for vec in selected_vectors)
                mmr_score = (diversity_lambda * score) - ((1 - diversity_lambda) * max_sim_to_selected)
                if mmr_score > 0.05 or len(selected) < 3:
                    selected.append((score, chunk))
                    selected_vectors.append(vector)

            for similarity, chunk in selected:
                results.append({
                    "id": chunk["id"],
                    "content": chunk["content"][:700],
                    "source": chunk["source_file"],
                    "relevance_score": round(float(similarity), 4),
                    "page_number": chunk.get("page_number") or 1,
                })
            if results:
                retrieval_mode = "semantic"

        # Keyword fallback — only if semantic found nothing above threshold
        if not results:
            kw_resp = sb.table("pdf_chunks").select("id, content, source_file, page_number").ilike("content", f"%{query.query}%").limit(5).execute()
            for idx, chunk in enumerate(kw_resp.data or []):
                results.append({
                    "id": chunk["id"],
                    "content": chunk["content"][:700],
                    "source": chunk["source_file"],
                    "relevance_score": 0.90 - (idx * 0.05),
                    "page_number": chunk.get("page_number") or 1,
                })

        if not results:
            generated_answer = f"No relevant results found for \"{query.query}\". The indexed PDFs may not contain information on this topic. Try a different query or ask your teacher to upload relevant course materials."
        else:
            try:
                memory_resp = await memory_recall(
                    bank_id=build_bank_id(current_user),
                    query=query.query,
                    limit=5,
                )
                candidates = []
                if isinstance(memory_resp, dict):
                    for key in ("results", "items", "memories", "data"):
                        value = memory_resp.get(key)
                        if isinstance(value, list):
                            candidates = value
                            break
                for item in candidates:
                    if isinstance(item, str):
                        memory_context.append(item)
                    elif isinstance(item, dict):
                        text = item.get("content") or item.get("text") or item.get("memory") or item.get("summary")
                        if text:
                            memory_context.append(str(text))
            except Exception as exc:
                logger.warning("Memory recall failed during search: %s", exc)

            generated_answer = _generate_rag_answer(
                gemini_client,
                query.query,
                results,
                query.language,
                memory_context=memory_context,
            )
        response_time = int((time.time() - start_time) * 1000)

        # Log search history
        try:
            sb.table("search_history").insert({
                "user_id": current_user.get("id"),
                "query": query.query,
                "language": query.language,
                "results_count": len(results),
                "response_time_ms": response_time,
            }).execute()
        except Exception as exc:
            logger.warning("Failed to log search history: %s", exc)

        try:
            await retain_rag_search(
                current_user,
                query=query.query,
                language=query.language,
                results_count=len(results),
                retrieval_mode=retrieval_mode,
            )
        except Exception as exc:
            logger.warning("Failed to retain RAG event in memory: %s", exc)

        return {
            "query": query.query,
            "results": results,
            "total_results": len(results),
            "response_time_ms": response_time,
            "retrieval_mode": retrieval_mode,
            "used_multimodal": used_multimodal,
            "memory_context_used": bool(memory_context),
            "memory_context_fragments": memory_context if memory_context else [],
            "generated_answer": generated_answer,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdfs/{pdf_id}/summary")
async def summarize_pdf(
    pdf_id: int,
    language: str = "english",
    current_user: dict = Depends(get_current_user),
):
    """Generate a concise study summary for an indexed PDF."""
    if current_user.get("role") not in ["teacher", "admin", "student"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    sb = get_supabase()
    pdf_resp = sb.table("pdfs").select("id, filename, status").eq("id", pdf_id).limit(1).execute()
    pdf = pdf_resp.data[0] if pdf_resp.data else None
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    if pdf.get("status") != "indexed":
        raise HTTPException(status_code=400, detail="PDF must be indexed before summarization")

    chunk_resp = (
        sb.table("pdf_chunks")
        .select("content, page_number")
        .eq("pdf_id", pdf_id)
        .order("chunk_index", desc=False)
        .limit(20)
        .execute()
    )
    chunks = chunk_resp.data or []
    if not chunks:
        raise HTTPException(status_code=404, detail="No indexed content available for summary")

    context = "\n\n".join(f"Page {c.get('page_number', 1)}: {c.get('content', '')}" for c in chunks)
    client = _get_gemini_client()
    if not client:
        raise HTTPException(status_code=503, detail="Gemini client is not configured")

    language_instruction = {
        "hindi": "Provide the summary in Hindi.",
        "hinglish": "Provide the summary in Hinglish.",
    }.get((language or "english").lower(), "Provide the summary in English.")

    prompt = (
        "You are EduRag. Create a practical study summary from the provided PDF excerpts.\n"
        "Include: Key concepts, Important formulas/facts, and 5 quick revision bullets.\n"
        f"{language_instruction}\n\n"
        f"Source file: {pdf.get('filename')}\n\n"
        f"Excerpts:\n{context}"
    )

    for model in [GENERATION_MODEL, GENERATION_MODEL_FALLBACK]:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            summary_text = (response.text or "").strip()
            if summary_text:
                return {
                    "pdf_id": pdf_id,
                    "filename": pdf.get("filename"),
                    "language": language,
                    "summary": summary_text,
                }
        except Exception as exc:
            logger.warning("Summary generation failed with %s: %s", model, exc)

    raise HTTPException(status_code=500, detail="Failed to generate summary")


@router.get("/recommendations")
async def get_personalized_recommendations(
    current_user: dict = Depends(get_current_user),
):
    """Return smart topic recommendations based on user's recent searches and global trends."""
    sb = get_supabase()

    history_resp = (
        sb.table("search_history")
        .select("query")
        .eq("user_id", current_user.get("id"))
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    user_queries = [row.get("query", "") for row in (history_resp.data or []) if row.get("query")]

    trend_resp = sb.table("search_history").select("query").limit(200).execute()
    all_queries = [row.get("query", "") for row in (trend_resp.data or []) if row.get("query")]

    from collections import Counter

    user_tokens = []
    for query in user_queries:
        user_tokens.extend([tok for tok in re.findall(r"[a-zA-Z0-9_\u0900-\u097F]+", query.lower()) if len(tok) > 3])

    trend_tokens = []
    for query in all_queries:
        trend_tokens.extend([tok for tok in re.findall(r"[a-zA-Z0-9_\u0900-\u097F]+", query.lower()) if len(tok) > 3])

    user_interest = Counter(user_tokens)
    trending = Counter(trend_tokens)

    recommendations = []
    seen = set()
    for token, _ in user_interest.most_common(5):
        if token not in seen:
            recommendations.append({"topic": token, "reason": "Based on your recent searches"})
            seen.add(token)

    for token, _ in trending.most_common(8):
        if token not in seen and len(recommendations) < 10:
            recommendations.append({"topic": token, "reason": "Trending among learners"})
            seen.add(token)

    return {
        "user_id": current_user.get("id"),
        "recommendations": recommendations,
    }


@router.post("/study-plan")
async def generate_study_plan(
    query: RAGQuery,
    current_user: dict = Depends(get_current_user),
):
    """Generate an adaptive short-term study plan from user question + retrieved context."""
    sb = get_supabase()
    search_payload = await search_documents(query=query, current_user=current_user)
    retrieved_results = search_payload.get("results", [])

    if not retrieved_results:
        return {
            "query": query.query,
            "language": query.language,
            "study_plan": "No plan generated because no relevant study material was found.",
            "recommended_actions": [
                "Upload additional course notes",
                "Try a more specific topic query",
                "Ask your instructor for targeted PDFs",
            ],
        }

    client = _get_gemini_client()
    if not client:
        raise HTTPException(status_code=503, detail="Gemini client is not configured")

    compact_context = "\n\n".join(
        f"Source: {r.get('source')} Page {r.get('page_number')}\n{r.get('content', '')[:500]}"
        for r in retrieved_results[:5]
    )

    language_instruction = {
        "hindi": "Provide the study plan in Hindi.",
        "hinglish": "Provide the study plan in Hinglish.",
    }.get((query.language or "english").lower(), "Provide the study plan in English.")

    prompt = (
        "You are an educational AI mentor. Build a 7-day actionable study plan.\n"
        "Output sections:\n"
        "1) Learning Goal\n2) Daily Plan (Day 1..Day 7)\n3) 5 Revision Questions\n4) Common Mistakes to Avoid\n"
        f"{language_instruction}\n\n"
        f"Student topic: {query.query}\n\n"
        f"Context:\n{compact_context}"
    )

    for model in [GENERATION_MODEL, GENERATION_MODEL_FALLBACK]:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            plan_text = (response.text or "").strip()
            if plan_text:
                try:
                    sb.table("analytics_events").insert({
                        "user_id": current_user.get("id"),
                        "event_type": "study_plan_generated",
                        "event_payload": json.dumps({"query": query.query, "language": query.language}),
                    }).execute()
                except Exception as exc:
                    logger.warning("Failed to log study plan event: %s", exc)

                return {
                    "query": query.query,
                    "language": query.language,
                    "study_plan": plan_text,
                    "sources_used": len(retrieved_results[:5]),
                }
        except Exception as exc:
            logger.warning("Study plan generation failed with %s: %s", model, exc)

    raise HTTPException(status_code=500, detail="Failed to generate study plan")

@router.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a PDF file to Supabase Storage (Teacher/Admin only).
    Returns the uploaded PDF's metadata.
    """
    if current_user.get("role") not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Only teachers and admins can upload PDFs")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    try:
        sb = get_supabase()
        _ensure_storage_bucket(sb)

        file_bytes = await file.read()
        # Use a unique path to avoid collisions
        storage_path = f"{int(time.time())}_{file.filename}"

        sb.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"},
        )

        resp = sb.table("pdfs").insert({
            "filename": file.filename,
            "storage_path": storage_path,
            "uploaded_by": current_user.get("id"),
            "status": "pending_indexing",
        }).execute()
        new_pdf = resp.data[0]

        return {
            "message": "PDF uploaded successfully",
            "pdf": {
                "id": new_pdf["id"],
                "filename": new_pdf["filename"],
                "status": new_pdf["status"],
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdfs")
async def list_pdfs(
    current_user: dict = Depends(get_current_user),
):
    """
    List all uploaded PDFs with their metadata.
    """
    sb = get_supabase()
    resp = sb.table("pdfs").select("*").order("created_at", desc=True).execute()
    return [
        {
            "id": p["id"],
            "filename": p["filename"],
            "status": p["status"],
            "total_pages": p.get("total_pages"),
            "total_chunks": p.get("total_chunks", 0),
            "uploaded_by": p.get("uploaded_by"),
            "created_at": p.get("created_at"),
        }
        for p in (resp.data or [])
    ]

@router.get("/search-history")
async def get_search_history(
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
):
    """
    Get the current user's search history from Supabase.
    """
    try:
        sb = get_supabase()
        resp = (
            sb.table("search_history")
            .select("id, query, language, results_count, created_at")
            .eq("user_id", current_user.get("id"))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trending")
async def get_trending_topics(
    current_user: dict = Depends(get_current_user),
):
    """
    Get trending search topics from Supabase search history.
    Returns a list of topics with their popularity.
    """
    try:
        sb = get_supabase()
        rows = sb.table("search_history").select("query").execute().data or []
        from collections import Counter
        counts = Counter(r["query"] for r in rows if r.get("query"))
        return [
            {"topic": q, "count": c, "difficulty": "High" if c > 40 else "Medium" if c > 20 else "Low"}
            for q, c in counts.most_common(10)
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/pdfs/{pdf_id}")
async def delete_pdf(
    pdf_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a PDF from Supabase Storage and database (Teacher/Admin only).
    """
    if current_user.get("role") not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Only teachers and admins can delete PDFs")

    sb = get_supabase()
    resp = sb.table("pdfs").select("*").eq("id", pdf_id).limit(1).execute()
    pdf = resp.data[0] if resp.data else None
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")

    # Delete from Supabase Storage
    if pdf.get("storage_path"):
        try:
            sb.storage.from_(STORAGE_BUCKET).remove([pdf["storage_path"]])
        except Exception:
            pass

    # Cascade: delete embeddings → chunks → pdf row
    sb.table("rag_embeddings").delete().eq("pdf_id", pdf_id).execute()
    sb.table("pdf_chunks").delete().eq("pdf_id", pdf_id).execute()
    sb.table("pdfs").delete().eq("id", pdf_id).execute()

    return {"message": "PDF deleted successfully"}


@router.post("/pdfs/{pdf_id}/index")
async def index_pdf(
    pdf_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    Index a PDF: runs in the background to prevent timeouts on large files.
    """
    if current_user.get("role") not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Only teachers and admins can index PDFs")

    sb = get_supabase()
    resp = sb.table("pdfs").select("*").eq("id", pdf_id).limit(1).execute()
    pdf = resp.data[0] if resp.data else None
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")

    sb.table("pdfs").update({"status": "indexing"}).eq("id", pdf_id).execute()
    
    background_tasks.add_task(_process_pdf_indexing_task, pdf_id, pdf)
    
    return {
        "message": "Indexing started in the background.",
        "status": "indexing"
    }

def _process_pdf_indexing_task(pdf_id: int, pdf: dict):
    """
    Background logic for extracting, chunking and embedding PDF pages.
    Limits to 50 pages to prevent Gemini rate limiting and ultra-long processing
    on massive academic textbooks.
    """
    sb = get_supabase()
    tmp_path = None
    try:
        gemini_client = _get_gemini_client()

        # Download PDF from Supabase Storage to a temp file
        tmp_path = _download_pdf_from_storage(sb, pdf["storage_path"])

        # Delete existing chunks/embeddings for this PDF
        sb.table("rag_embeddings").delete().eq("pdf_id", pdf_id).execute()
        sb.table("pdf_chunks").delete().eq("pdf_id", pdf_id).execute()

        pages, original_total_pages = _extract_text_and_images_from_pdf(tmp_path)
        chunks_created = 0
        
        # Limit to 50 pages for performance and API rate limits
        MAX_PAGES = 50
        processed_pages = pages[:MAX_PAGES]
        
        for page_info in processed_pages:
            page_number = page_info["page_number"]
            page_text = page_info["text"]
            page_images = page_info["images"]

            image_captions = []
            image_embedding_payloads = []
            multimodal_page = False

            if page_images:
                multimodal_page = True
                for image_bytes in page_images[:4]:
                    caption = _caption_image_with_gemini(gemini_client, image_bytes)
                    if caption:
                        image_captions.append(caption)
                    multimodal_vector = _try_multimodal_embed(gemini_client, image_bytes, page_text)
                    if multimodal_vector is not None:
                        image_embedding_payloads.append({
                            "vector": multimodal_vector,
                            "caption": caption or "Visual content from PDF image",
                        })

            page_composite_text = page_text
            if image_captions:
                page_composite_text = (
                    f"{page_text}\n\nImage insights:\n" + "\n".join(f"- {c}" for c in image_captions)
                ).strip()

            if not page_composite_text.strip():
                continue

            text_chunks = _chunk_text(page_composite_text)
            for chunk_text in text_chunks:
                chunk_resp = sb.table("pdf_chunks").insert({
                    "pdf_id": pdf_id,
                    "content": chunk_text,
                    "source_file": pdf["filename"],
                    "page_number": page_number,
                    "chunk_index": chunks_created,
                }).execute()
                new_chunk = chunk_resp.data[0]

                embedding_vector = _embed_text(gemini_client, chunk_text)
                if embedding_vector:
                    sb.table("rag_embeddings").insert({
                        "pdf_id": pdf_id,
                        "pdf_chunk_id": new_chunk["id"],
                        "modality": "multimodal" if multimodal_page else "text",
                        "embedding_json": json.dumps(embedding_vector),
                        "page_number": page_number,
                    }).execute()

                chunks_created += 1
                
                # Small sleep to prevent hitting Gemini API rate limits on basic tier
                time.sleep(0.5)

            # Image-specific multimodal vectors
            for img_payload in image_embedding_payloads:
                img_chunk_resp = sb.table("pdf_chunks").insert({
                    "pdf_id": pdf_id,
                    "content": f"Image insight: {img_payload['caption']}",
                    "source_file": pdf["filename"],
                    "page_number": page_number,
                    "chunk_index": chunks_created,
                }).execute()
                img_chunk = img_chunk_resp.data[0]

                sb.table("rag_embeddings").insert({
                    "pdf_id": pdf_id,
                    "pdf_chunk_id": img_chunk["id"],
                    "modality": "multimodal",
                    "embedding_json": json.dumps(img_payload["vector"]),
                    "page_number": page_number,
                }).execute()
                chunks_created += 1
                time.sleep(0.5)

        # Update PDF record
        sb.table("pdfs").update({
            "status": "indexed",
            "total_pages": original_total_pages,
            "total_chunks": chunks_created,
        }).eq("id", pdf_id).execute()

    except Exception as e:
        sb.table("pdfs").update({"status": "failed"}).eq("id", pdf_id).execute()
        logger.error(f"Background indexing failed for pdf {pdf_id}: {str(e)}")
    finally:
        # Always clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@router.get("/pdfs/{pdf_id}")
async def get_pdf_detail(
    pdf_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Get details of a specific PDF, including uploader information.
    """
    sb = get_supabase()
    resp = sb.table("pdfs").select("*").eq("id", pdf_id).limit(1).execute()
    pdf = resp.data[0] if resp.data else None
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")

    uploader_name = "Unknown"
    if pdf.get("uploaded_by"):
        try:
            u_resp = sb.table("users").select("name").eq("id", pdf["uploaded_by"]).limit(1).execute()
            if u_resp.data:
                uploader_name = u_resp.data[0]["name"]
        except Exception as exc:
            logger.warning("Failed to resolve uploader name for pdf_id=%s: %s", pdf_id, exc)

    return {
        "id": pdf["id"],
        "filename": pdf["filename"],
        "status": pdf["status"],
        "total_pages": pdf.get("total_pages"),
        "total_chunks": pdf.get("total_chunks", 0),
        "uploaded_by": pdf.get("uploaded_by"),
        "uploader_name": uploader_name,
        "created_at": pdf.get("created_at"),
    }


# ---------------------------------------------------------------------------
# AI Exam Mode — Generate Test from PDF
# ---------------------------------------------------------------------------

def _parse_test_json(raw_text: str) -> dict:
    """
    Extract and parse the JSON block from Gemini's raw response.
    Handles markdown code fences (```json ... ```) gracefully.
    """
    # Strip markdown fences if present
    text = raw_text.strip()
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        inner = text[start + 3: end].strip()
        # Strip optional language tag on first line
        if inner.startswith("json"):
            inner = inner[4:].strip()
        text = inner

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse Gemini JSON output: {exc}") from exc


def _generate_test_with_groq(groq_client, prompt: str):
    """
    Fallback function to generate test content using Groq's Llama models.
    """
    if not groq_client:
        return None
    try:
        logger.info("Using Turbo Fallback: Generating test with Groq (Llama 3.3)")
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an educational assistant that strictly outputs JSON."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
        )
        return chat_completion.choices[0].message.content
    except Exception as exc:
        logger.error(f"Groq generation failed: {exc}")
        return None


@router.post("/generate-test")
@router.post("/generate-test/")
async def generate_test(
    request: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    AI Exam Mode — Generate a structured test from an indexed PDF.
    (Route confirmed active)
    """
    logger.info("AI Exam Mode endpoint called")
    """
    AI Exam Mode — Generate a structured test (MCQs, short & long questions)
    from an indexed PDF's stored chunks using Gemini AI.

    Request body:
        pdf_id (int): ID of the indexed PDF.
        difficulty (str, optional): "easy" | "medium" | "hard". Defaults to "medium".

    Returns:
        {
            "mcqs": [{"question": ..., "options": [...], "answer": ...}],
            "short_questions": [...],
            "long_questions": [...]
        }
    """
    pdf_id = request.get("pdf_id")
    difficulty = (request.get("difficulty") or "medium").lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"

    if not pdf_id:
        raise HTTPException(status_code=422, detail="pdf_id is required")

    sb = get_supabase()

    # -- Validate PDF exists and is indexed --
    pdf_resp = sb.table("pdfs").select("id, filename, status").eq("id", pdf_id).limit(1).execute()
    pdf = pdf_resp.data[0] if pdf_resp.data else None
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    if pdf.get("status") != "indexed":
        raise HTTPException(
            status_code=400,
            detail=f"PDF '{pdf['filename']}' is not indexed yet. Ask your teacher to index it first."
        )

    # -- Fetch top chunks for context (up to 20, ordered by chunk_index) --
    chunk_resp = (
        sb.table("pdf_chunks")
        .select("content, page_number, chunk_index")
        .eq("pdf_id", pdf_id)
        .order("chunk_index", desc=False)
        .limit(20)
        .execute()
    )
    chunks = chunk_resp.data or []
    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No indexed content found for this PDF. Try re-indexing it."
        )

    # -- Build context for Gemini --
    context = "\n\n".join(
        f"[Page {c.get('page_number', '?')}] {c.get('content', '')}"
        for c in chunks
    )

    difficulty_instruction = {
        "easy": (
            "The questions should be straightforward, testing basic recall and comprehension. "
            "MCQ distractors should be clearly wrong. Short and long answers should be simple."
        ),
        "medium": (
            "The questions should require understanding and application of concepts. "
            "MCQ distractors should be plausible. Short and long answers should demonstrate understanding."
        ),
        "hard": (
            "The questions should require deep analysis, synthesis, and critical thinking. "
            "MCQ distractors should be very similar and tricky. Long answers should require evaluation."
        ),
    }.get(difficulty, "")

    prompt = f"""You are EduRag, an expert educational AI. 
Generate a comprehensive exam test from the provided PDF content.

Difficulty level: {difficulty.upper()}
{difficulty_instruction}

Generate EXACTLY:
- 5 multiple choice questions (MCQs), each with 4 options (A, B, C, D) and exactly 1 correct answer
- 3 short answer questions (require 2-4 sentence answers)
- 2 long answer questions (require detailed paragraph answers)

IMPORTANT RULES:
1. Base ALL questions on the provided PDF content only — do not invent facts.
2. MCQ options must be full strings (not just "A", "B", etc.) — they are the answer text itself.
3. The "answer" field in MCQs must be the FULL TEXT of the correct option (not just a letter).
4. Questions must be clearly worded and educationally valuable.
5. Output ONLY valid JSON — no markdown, no explanation, no extra text before or after.

Output this EXACT JSON structure:
{{
  "mcqs": [
    {{
      "question": "Question text here?",
      "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
      "answer": "Option A text"
    }}
  ],
  "short_questions": [
    "Short question 1?",
    "Short question 2?",
    "Short question 3?"
  ],
  "long_questions": [
    "Long question 1?",
    "Long question 2?"
  ]
}}

PDF Source: {pdf['filename']}

PDF Content:
{context}
"""

    client = _get_gemini_client()
    if not client:
        raise HTTPException(status_code=503, detail="Gemini API is not configured. Set GEMINI_API_KEY in .env")

    last_error = None
    # Use explicitly supported models directly
    test_models = ["gemini-1.5-flash", "gemini-2.0-flash"]
    
    for model in test_models:
        model_name = model if model.startswith("models/") else f"models/{model}"
        # Up to 3 retries per model if we hit quota limits
        for attempt in range(3):
            try:
                logger.info(f"Generating test using {model_name} (Attempt {attempt+1}/3)")
                response = client.models.generate_content(model=model_name, contents=prompt)
                raw_text = (response.text or "").strip()
                if not raw_text:
                    continue

                parsed = _parse_test_json(raw_text)

                # Validate structure
                if not isinstance(parsed.get("mcqs"), list):
                    raise ValueError("Invalid structure: 'mcqs' must be a list")
                if not isinstance(parsed.get("short_questions"), list):
                    raise ValueError("Invalid structure: 'short_questions' must be a list")
                if not isinstance(parsed.get("long_questions"), list):
                    raise ValueError("Invalid structure: 'long_questions' must be a list")

                # Log analytics event
                try:
                    sb.table("analytics_events").insert({
                        "user_id": current_user.get("id"),
                        "event_type": "exam_generated",
                        "event_data": json.dumps({
                            "pdf_id": pdf_id,
                            "filename": pdf.get("filename"),
                            "difficulty": difficulty,
                            "mcq_count": len(parsed.get("mcqs", [])),
                        }),
                    }).execute()
                except Exception as exc:
                    logger.warning("Failed to log exam_generated event: %s", exc)

                return {
                    "pdf_id": pdf_id,
                    "filename": pdf.get("filename"),
                    "difficulty": difficulty,
                    "mcqs": parsed.get("mcqs", []),
                    "short_questions": parsed.get("short_questions", []),
                    "long_questions": parsed.get("long_questions", []),
                }

            except Exception as exc:
                last_error = exc
                err_str = str(exc).lower()
                if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
                    # Turbo Fallback: Try Groq immediately instead of waiting
                    groq_client = _get_groq_client()
                    if groq_client:
                        logger.warning("Gemini Quota Hit! Switching to Turbo Fallback (Groq)...")
                        groq_raw = _generate_test_with_groq(groq_client, prompt)
                        if groq_raw:
                            try:
                                parsed = _parse_test_json(groq_raw)
                                logger.info("Turbo Fallback success! Test generated by Groq.")
                                return {
                                    "pdf_id": pdf_id,
                                    "filename": pdf.get("filename"),
                                    "difficulty": difficulty,
                                    "mcqs": parsed.get("mcqs", []),
                                    "short_questions": parsed.get("short_questions", []),
                                    "long_questions": parsed.get("long_questions", []),
                                    "turbo_active": True
                                }
                            except Exception as p_exc:
                                logger.error(f"Failed to parse Groq JSON: {p_exc}")

                    # If Groq fails or is not available, then wait (fallback to original retry)
                    wait_time = 35 
                    logger.warning(f"Test Generation Quota hit. Waiting {wait_time}s before retry {attempt+1}...")
                    time.sleep(wait_time)
                    continue
                
                logger.warning("Test generation failed with %s: %s", model, exc)
                break # Try next model if it's a different kind of error

    if last_error:
        error_str = str(last_error)
        if "429" in error_str or "resource_exhausted" in error_str or "quota" in error_str.lower():
            raise HTTPException(
                status_code=429,
                detail="Google API quota hit. We attempted retries but it's still busy. Please wait 30 seconds and try again."
            )
        
    raise HTTPException(
        status_code=500,
        detail=f"Failed to generate test. AI error: {str(last_error)}"
    )

@router.post("/voice-search")
async def voice_search(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Accepts an audio file via POST, transcribes it using Groq's whisper model,
    and then performs a standard RAG search using the transcribed text.
    """
    from dotenv import load_dotenv
    load_dotenv(override=True)
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key or groq_key == "your_groq_api_key_here":
        raise HTTPException(
            status_code=503, 
            detail="Groq API key not configured. On Vercel, please set 'GROQ_API_KEY' in your Environment Variables."
        )
        
    client = Groq(api_key=groq_key)
    
    # Save audio temporarily
    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
    try:
        temp_audio.write(await file.read())
        temp_audio.close()
        
        with open(temp_audio.name, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(file.filename, audio_file.read()),
                model="whisper-large-v3-turbo",
                language="en",
                temperature=0.0,
                prompt="Explain stateless server. Generate test from PDF. Tell me about photosynthesis, thermodynamics, neural networks."
            )
            
        user_query = transcription.text.strip()
        common_hallucinations = ["Thank you.", "Thank you", "Please subscribe.", "Bye.", "Amara.org", "Thank you very much.", "."]
        if not user_query or user_query in common_hallucinations:
            return {"error": "Could not recognize speech clearly. Please try again.", "transcript": ""}
            
        # call existing search_documents
        rag_query = RAGQuery(query=user_query, language="english")
        results_payload = await search_documents(rag_query, current_user)
        
        return {
            "transcript": user_query,
            "generated_answer": results_payload.get("generated_answer", ""),
            "results": results_payload.get("results", [])
        }
    except Exception as e:
        logger.error(f"Voice search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Voice search failed: {str(e)}")
    finally:
        os.remove(temp_audio.name)

@router.get("/pdf-logbook")
@router.get("/pdf-logbook/")
async def get_pdf_logbook(current_user: dict = Depends(get_current_user)):
    """
    Fetch all uploaded PDFs (metadata only) with the faculty name.
    (Route confirmed active)
    """
    logger.info("PDF Logbook endpoint called")
    try:
        sb = get_supabase()
        # Ensure we fetch 'uploaded_by' conceptually by joining users on uploaded_by via Supabase syntax
        # Or simple select: users(name) if foreign key exists. We verified it works above.
        resp = sb.table("pdfs").select("id, filename, created_at, users(name)").order("created_at", desc=True).execute()
        
        log_book = []
        for item in (resp.data or []):
            faculty_name = "Unknown"
            if item.get("users") and isinstance(item.get("users"), dict):
                faculty_name = item["users"].get("name", "Unknown")
            elif item.get("users") and isinstance(item.get("users"), list) and len(item["users"]) > 0:
                faculty_name = item["users"][0].get("name", "Unknown")
                
            log_book.append({
                "id": item.get("id"),
                "title": item.get("filename", "Untitled PDF"),
                "faculty_name": faculty_name,
                "uploaded_at": item.get("created_at")
            })
            
        return log_book
    except Exception as e:
        logger.error(f"Failed to fetch PDF logbook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch PDF logbook: {str(e)}")
