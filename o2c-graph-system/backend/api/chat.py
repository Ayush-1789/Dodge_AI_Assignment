"""
Chat API endpoint - main conversational interface.
Implements two-stage LLM pipeline: query generation → execution → synthesis.
"""

import logging
import time
import uuid
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request
import json

from ..database.sql_executor import SQLExecutor
from ..graph.builder import get_builder
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


class ChatResponse(BaseModel):
    """Chat response model."""
    answer: str
    highlighted_nodes: List[str] = []
    query_type: str = ""
    query_info: dict = {}
    result_count: int = 0


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
    
    # If no Gemini client, return error
    if gemini_client is None:
        logger.error("[chat:%s] Gemini client unavailable at request time", request_id)
        raise HTTPException(
            status_code=500,
            detail="LLM service not available. Please set GEMINI_API_KEY environment variable."
        )
    
    try:
        # Stage 1: Generate query
        query_gen_prompt = build_query_generator_prompt(db_schema)
        logger.info("[chat:%s] Stage=query_generation started", request_id)
        query_spec = gemini_client.generate_query(
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
        response_data = gemini_client.synthesize_response(
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
        
        return ChatResponse(
            answer=response_data.get("answer", ""),
            highlighted_nodes=response_data.get("highlighted_nodes", []),
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
