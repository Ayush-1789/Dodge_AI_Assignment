"""
Chat API endpoint - main conversational interface.
Implements two-stage LLM pipeline: query generation → execution → synthesis.
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request
import json
import hashlib

from ..database.sql_executor import SQLExecutor
from ..graph.builder import get_builder
from ..graph.schema import NODE_TYPES
from ..graph.queries import trace_flow, find_neighbors, find_broken_flows
from ..llm.gemini_client import GeminiClient
from ..llm.intent_classifier import classify_intent, is_potential_injection
from ..llm.prompt_builder import build_query_generator_prompt, build_response_synthesizer_prompt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _truncate(text: str, max_len: int = 240) -> str:
    """Truncate text for safe logging."""
    if text is None:
        return ""
    text = str(text).replace("\n", " ").strip()
    return text if len(text) <= max_len else f"{text[:max_len]}..."


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    conversation_history: List[dict] = []
    api_key: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    answer: str
    highlighted_nodes: List[str] = []
    query_type: str = ""
    query_info: dict = {}
    result_count: int = 0


class KeyValidationRequest(BaseModel):
    """API key validation request model."""
    api_key: str


class KeyValidationResponse(BaseModel):
    """API key validation response model."""
    valid: bool
    message: str
    model: str = ""


def _key_fingerprint(api_key: str) -> str:
    """Create a safe, non-reversible fingerprint for logs."""
    normalized = GeminiClient._normalize_api_key(api_key)
    if not normalized:
        return "none"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10]
    return f"len={len(normalized)}|sha256={digest}"


def _normalize_highlight_nodes(raw_nodes: Any) -> List[str]:
    """Normalize model-provided highlighted node IDs to a clean list of strings."""
    if raw_nodes is None:
        return []
    if isinstance(raw_nodes, str):
        raw_nodes = [raw_nodes]
    if not isinstance(raw_nodes, list):
        return []

    normalized: List[str] = []
    seen: Set[str] = set()
    for value in raw_nodes:
        node_id = str(value).strip()
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        normalized.append(node_id)
    return normalized


def _filter_existing_node_ids(node_ids: List[str], graph) -> List[str]:
    """Keep only node IDs that exist in the built graph."""
    if not node_ids:
        return []
    if graph is None:
        return node_ids

    graph_node_ids = set(graph.nodes())
    return [node_id for node_id in node_ids if node_id in graph_node_ids]


def _iter_row_dicts(payload: Any):
    """Recursively yield dictionaries from nested payloads."""
    if isinstance(payload, dict):
        yield payload
        for value in payload.values():
            yield from _iter_row_dicts(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_row_dicts(item)


def _iter_scalars(payload: Any):
    """Recursively yield scalar values from nested payloads."""
    if isinstance(payload, dict):
        for value in payload.values():
            yield from _iter_scalars(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_scalars(item)
    else:
        yield payload


def _looks_like_node_id(value: Any) -> bool:
    """Check whether a value already looks like a full graph node ID."""
    text = str(value).strip()
    if not text:
        return False
    for node_type in NODE_TYPES.keys():
        if text.startswith(f"{node_type}_"):
            return True
    return False


def _find_row_value(row: Dict[str, Any], column_name: str) -> Any:
    """Resolve a column value in a row by exact or suffix match."""
    key_aliases = {
        "business_partner": ["sold_to_party", "customer", "customer_id", "business_partner_id"],
        "product": ["material", "product_id"],
    }

    direct = row.get(column_name)
    if direct is not None and str(direct).strip() != "":
        return direct

    col_lower = column_name.lower()
    exact_case_insensitive = [
        value for key, value in row.items()
        if isinstance(key, str) and key.lower() == col_lower and value is not None and str(value).strip() != ""
    ]
    if exact_case_insensitive:
        return exact_case_insensitive[0]

    suffix_matches = [
        value for key, value in row.items()
        if isinstance(key, str) and key.lower().endswith(f"_{col_lower}") and value is not None and str(value).strip() != ""
    ]
    if suffix_matches:
        return suffix_matches[0]

    alias_candidates = key_aliases.get(column_name, [])
    for alias in alias_candidates:
        alias_value = row.get(alias)
        if alias_value is not None and str(alias_value).strip() != "":
            return alias_value

    for alias in alias_candidates:
        alias_lower = alias.lower()
        alias_case_insensitive = [
            value for key, value in row.items()
            if isinstance(key, str) and key.lower() == alias_lower and value is not None and str(value).strip() != ""
        ]
        if alias_case_insensitive:
            return alias_case_insensitive[0]

    return None


def _build_node_id_from_row(node_type: str, key_cols: List[str], row: Dict[str, Any]) -> Optional[str]:
    """Attempt to reconstruct a graph node ID from a query row."""
    parts: List[str] = []
    for key_col in key_cols:
        value = _find_row_value(row, key_col)
        if value is None:
            return None

        part = str(value).strip()
        if not part:
            return None

        # Avoid double-prefixing values that are already full node IDs.
        if part.startswith(f"{node_type}_"):
            part = part[len(node_type) + 1:]
        parts.append(part)

    if not parts:
        return None
    return f"{node_type}_{'__'.join(parts)}"


def _extract_result_highlight_nodes(query_result: Any, query_spec: Dict[str, Any], graph) -> List[str]:
    """Extract highlightable node IDs from query result payloads and query metadata."""
    candidates: List[str] = []
    seen: Set[str] = set()
    graph_node_ids = set(graph.nodes()) if graph is not None else set()

    def add_candidate(node_id: Any):
        text = str(node_id).strip() if node_id is not None else ""
        if not text or text in seen:
            return
        if graph_node_ids and text not in graph_node_ids:
            return
        seen.add(text)
        candidates.append(text)

    # Graph operation inputs can be important context nodes even if result rows are sparse.
    start_node_type = query_spec.get("start_node_type")
    start_node_id = query_spec.get("start_node_id")
    if start_node_type and start_node_id:
        add_candidate(f"{start_node_type}_{start_node_id}")

    # Common graph response payloads.
    if isinstance(query_result, dict):
        for node in query_result.get("nodes", []) or []:
            if isinstance(node, dict):
                add_candidate(node.get("id"))

        for section in ("incoming", "outgoing"):
            for item in query_result.get(section, []) or []:
                if isinstance(item, dict):
                    add_candidate(item.get("node_id"))

        if isinstance(query_result.get("issues"), dict):
            for issue_node_ids in query_result["issues"].values():
                if isinstance(issue_node_ids, list):
                    for issue_node_id in issue_node_ids:
                        add_candidate(issue_node_id)

    # Include any values that are already full node IDs.
    for value in _iter_scalars(query_result):
        if _looks_like_node_id(value):
            add_candidate(value)

    # Reconstruct node IDs from row dictionaries (SQL/hybrid outputs).
    for row in _iter_row_dicts(query_result):
        for node_type, config in NODE_TYPES.items():
            key_cols = config.get("node_key_cols") or [config.get("id_col")]
            if not key_cols:
                continue
            reconstructed = _build_node_id_from_row(node_type, key_cols, row)
            if reconstructed:
                add_candidate(reconstructed)

    return candidates


def initialize_dependencies(db_path: str, graph=None):
    """Initialize chat dependencies (call from main.py)."""
    global sql_executor, graph_instance, gemini_client, db_schema
    
    sql_executor = SQLExecutor(db_path)
    db_schema = sql_executor.get_schema()
    
    if graph is None:
        builder = get_builder(db_path)
        graph_instance = builder.build_graph()
    else:
        graph_instance = graph
    
    try:
        gemini_client = GeminiClient()
    except ValueError as e:
        logger.warning(f"Gemini client not initialized: {e}")
        gemini_client = None


@router.post("/validate-key", response_model=KeyValidationResponse)
async def validate_key(request: KeyValidationRequest):
    """Validate a user-provided Gemini API key."""
    key = (request.api_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key is required")

    try:
        client = GeminiClient(api_key=key)
        return KeyValidationResponse(
            valid=True,
            message="API key is valid and ready to use.",
            model=client.model_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid API key: {exc}")


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):
    """
    Main chat endpoint.
    
    Pipeline:
    1. Intent classification (Layer 1 guardrail)
    2. Query generation via Gemini (Layer 2 self-guardrail embedded in prompt)
    3. Query execution (SQL or graph)
    4. Response synthesis via Gemini
    5. Return answer + highlighted nodes
    """
    
    request_id = uuid.uuid4().hex[:8]
    started_at = time.perf_counter()
    message = request.message.strip()
    history_size = len(request.conversation_history or [])
    client_host = getattr(http_request.client, "host", "unknown")

    logger.info(
        "[chat:%s] Incoming message | client=%s | message_len=%s | history_len=%s | preview=%s",
        request_id,
        client_host,
        len(message),
        history_size,
        _truncate(message),
    )
    
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Layer 1: Keyword-based guardrail
    is_on_topic, reason = classify_intent(message)
    
    if is_on_topic == False:
        logger.info("[chat:%s] Rejected by guardrail: off_topic (%s)", request_id, reason)
        return ChatResponse(
            answer="This system is designed to answer questions related to the provided Order-to-Cash dataset only.",
            highlighted_nodes=[],
            query_type="off_topic"
        )
    
    # Check for injection attempts
    if is_potential_injection(message):
        logger.warning("[chat:%s] Rejected by injection guardrail", request_id)
        return ChatResponse(
            answer="This system is designed to answer questions related to the provided Order-to-Cash dataset only.",
            highlighted_nodes=[],
            query_type="injection_attempt"
        )
    
    request_api_key = (request.api_key or "").strip()
    active_gemini_client = gemini_client

    # Use request-scoped API key when provided, else fallback to server key.
    if request_api_key:
        try:
            active_gemini_client = GeminiClient(api_key=request_api_key)
            logger.info(
                "[chat:%s] Gemini key source=request-scoped | key=%s",
                request_id,
                _key_fingerprint(request_api_key),
            )
        except Exception as exc:
            logger.warning("[chat:%s] Invalid request-scoped API key", request_id)
            raise HTTPException(status_code=400, detail=f"Invalid API key: {exc}")
    else:
        logger.info("[chat:%s] Gemini key source=server-default", request_id)

    if active_gemini_client is None:
        logger.error("[chat:%s] Gemini client unavailable at request time", request_id)
        raise HTTPException(
            status_code=500,
            detail="LLM service not available. Set GEMINI_API_KEY on backend or provide API key in chat settings."
        )
    
    try:
        # Stage 1: Generate query
        query_gen_prompt = build_query_generator_prompt(db_schema)
        logger.info("[chat:%s] Stage=query_generation started", request_id)
        query_spec = active_gemini_client.generate_query(
            system_prompt=query_gen_prompt,
            user_message=message,
            history=request.conversation_history
        )
        
        if "error" in query_spec:
            raise ValueError(f"Query generation error: {query_spec.get('error')}")

        logger.info(
            "[chat:%s] Stage=query_generation completed | query_type=%s",
            request_id,
            query_spec.get("type", "unknown")
        )
        
        # Check if off-topic response from LLM
        if query_spec.get("type") == "off_topic":
            return ChatResponse(
                answer=query_spec.get("message", "This system is designed to answer questions related to the provided Order-to-Cash dataset only."),
                highlighted_nodes=[],
                query_type="off_topic"
            )
        
        # Execute query/graph operation
        query_result = None
        query_type = query_spec.get("type", "unknown")
        logger.info("[chat:%s] Stage=execution started | query_type=%s", request_id, query_type)
        
        if query_type == "sql":
            sql = query_spec.get("query")
            if sql:
                logger.info("[chat:%s] Executing SQL | preview=%s", request_id, _truncate(sql))
                query_result = sql_executor.execute(sql)
        
        elif query_type == "graph":
            operation = query_spec.get("operation")
            if not operation:
                raise ValueError(f"Missing graph operation in query spec: {query_spec}")
            
            if operation == "trace_flow":
                start_node_type = query_spec.get("start_node_type")
                start_node_id = query_spec.get("start_node_id")
                if not (start_node_type and start_node_id):
                    raise ValueError(f"Missing trace_flow parameters in query spec: {query_spec}")
                full_node_id = f"{start_node_type}_{start_node_id}"
                depth = query_spec.get("depth", 4)
                logger.info("[chat:%s] Executing graph op=trace_flow | node=%s | depth=%s", request_id, full_node_id, depth)
                query_result = trace_flow(graph_instance, full_node_id, depth)
            
            elif operation == "find_neighbors":
                start_node_type = query_spec.get("start_node_type")
                start_node_id = query_spec.get("start_node_id")
                if not (start_node_type and start_node_id):
                    raise ValueError(f"Missing find_neighbors parameters in query spec: {query_spec}")
                full_node_id = f"{start_node_type}_{start_node_id}"
                depth = query_spec.get("depth", 1)
                logger.info("[chat:%s] Executing graph op=find_neighbors | node=%s | depth=%s", request_id, full_node_id, depth)
                query_result = find_neighbors(graph_instance, full_node_id, depth)
            
            elif operation == "find_broken_flows":
                logger.info("[chat:%s] Executing graph op=find_broken_flows", request_id)
                query_result = find_broken_flows(graph_instance)
            
            else:
                raise ValueError(f"Unknown graph operation: {operation}")
        
        elif query_type == "hybrid":
            sql = query_spec.get("sql_query")
            if sql:
                logger.info("[chat:%s] Executing hybrid SQL | preview=%s", request_id, _truncate(sql))
                query_result = sql_executor.execute(sql)
        
        else:
            raise ValueError(f"Unknown query type: {query_type}")
        
        if query_result is None:
            query_result = []

        result_count = len(query_result) if isinstance(query_result, list) else 1
        logger.info("[chat:%s] Stage=execution completed | result_count=%s", request_id, result_count)
        
        # Stage 2: Synthesize response
        synthesis_prompt = build_response_synthesizer_prompt()
        logger.info("[chat:%s] Stage=response_synthesis started", request_id)
        response_data = active_gemini_client.synthesize_response(
            system_prompt=synthesis_prompt,
            question=message,
            query_spec=query_spec,
            query_result=query_result
        )
        
        if "error" in response_data:
            raise ValueError(f"Response synthesis error: {response_data.get('error')}")

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "[chat:%s] Completed successfully | query_type=%s | elapsed_ms=%s",
            request_id,
            query_type,
            elapsed_ms,
        )

        llm_highlighted = _filter_existing_node_ids(
            _normalize_highlight_nodes(response_data.get("highlighted_nodes", [])),
            graph_instance,
        )
        result_highlighted = _extract_result_highlight_nodes(query_result, query_spec, graph_instance)

        merged_highlighted: List[str] = []
        merged_seen: Set[str] = set()
        for node_id in llm_highlighted + result_highlighted:
            if node_id in merged_seen:
                continue
            merged_seen.add(node_id)
            merged_highlighted.append(node_id)

        logger.info(
            "[chat:%s] Highlight nodes merged | llm=%s | result=%s | final=%s",
            request_id,
            len(llm_highlighted),
            len(result_highlighted),
            len(merged_highlighted),
        )
        
        return ChatResponse(
            answer=response_data.get("answer", ""),
            highlighted_nodes=merged_highlighted,
            query_type=query_type,
            query_info=query_spec,
            result_count=response_data.get("result_count", 
                len(query_result) if isinstance(query_result, list) else 0)
        )
    
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception(
            "[chat:%s] Failed | error_type=%s | elapsed_ms=%s | message=%s",
            request_id,
            type(e).__name__,
            elapsed_ms,
            _truncate(str(e), 500),
        )
        raise HTTPException(status_code=500, detail=f"Error processing query (ref: {request_id}): {str(e)}")
