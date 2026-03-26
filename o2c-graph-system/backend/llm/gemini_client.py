"""
Gemini LLM client - wrapper around google-generativeai SDK.
Handles two-stage pipeline: query generation and response synthesis.
"""

import google.generativeai as genai
import os
import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def _truncate(value: Any, max_len: int = 280) -> str:
    """Safely truncate values for logs."""
    text = str(value).replace("\n", " ").strip()
    return text if len(text) <= max_len else f"{text[:max_len]}..."

GENERATION_CONFIG = {
    "temperature": 0.1,  # Low temp for deterministic SQL/queries
    "top_p": 0.8,
    "max_output_tokens": 2048,
    "response_mime_type": "application/json",
}

GENERATION_CONFIG_SYNTHESIS = {
    "temperature": 0.5,  # Higher temp for more natural synthesis
    "top_p": 0.9,
    "max_output_tokens": 2048,
    "response_mime_type": "application/json",
}


class GeminiClient:
    """Client for Gemini API interactions."""
    
    def __init__(self, api_key: str = None):
        """Initialize Gemini client with API key."""
        if api_key is None:
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        api_key = self._normalize_api_key(api_key)

        if not api_key:
            raise ValueError("Neither GEMINI_API_KEY nor GOOGLE_API_KEY environment variable is set")

        # Keep both env var names in sync for SDK/tooling compatibility.
        os.environ["GEMINI_API_KEY"] = api_key
        os.environ["GOOGLE_API_KEY"] = api_key
        genai.configure(api_key=api_key)
        logger.info("Gemini client initialized | api_key_present=%s | api_key_len=%s", True, len(api_key))
        self.model_name = self._resolve_model_name()

    @staticmethod
    def _normalize_api_key(api_key: Any) -> str:
        """Normalize API key by trimming whitespace and optional wrapping quotes."""
        if api_key is None:
            return ""

        normalized = str(api_key).strip()
        if (
            len(normalized) >= 2
            and normalized[0] == normalized[-1]
            and normalized[0] in {"'", '"'}
        ):
            normalized = normalized[1:-1].strip()
        return normalized

    def _resolve_model_name(self) -> str:
        """Resolve a valid model name, preferring env override and known flash variants."""
        env_model = os.environ.get("GEMINI_MODEL")
        candidates = [
            env_model,
            "gemini-3-flash",
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ]
        candidates = [name for name in candidates if name]

        try:
            available_models = list(genai.list_models())
            available_names = {
                model.name.replace("models/", "") for model in available_models
                if "generateContent" in getattr(model, "supported_generation_methods", [])
            }

            for candidate in candidates:
                if candidate in available_names:
                    logger.info(f"Using Gemini model: {candidate}")
                    return candidate

            if available_names:
                selected = sorted(available_names)[0]
                logger.warning(
                    f"None of preferred Gemini models are available. Falling back to: {selected}"
                )
                return selected

        except Exception as e:
            logger.warning(f"Could not resolve model via list_models: {e}")

        selected = env_model or "gemini-1.5-flash"
        logger.warning(f"Falling back to configured Gemini model without validation: {selected}")
        return selected
    
    def generate_query(
        self,
        system_prompt: str,
        user_message: str,
        history: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Stage 1: Generate query spec from natural language.
        
        Args:
            system_prompt: System prompt with schema and instructions
            user_message: User's natural language query
            history: Conversation history for context
        
        Returns:
            Parsed JSON response with query specification
        """
        try:
            logger.info(
                "Gemini generate_query start | model=%s | message_len=%s | history_len=%s",
                self.model_name,
                len(user_message or ""),
                len(history or []),
            )

            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
                generation_config=GENERATION_CONFIG
            )
            
            messages = (history or []) + [{"role": "user", "parts": [user_message]}]
            response = model.generate_content(messages)
            
            # Parse JSON response
            try:
                parsed = json.loads(response.text)
                logger.info("Gemini generate_query success | model=%s", self.model_name)
                return parsed
            except json.JSONDecodeError:
                # Try to extract JSON from response
                text = response.text
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    parsed = json.loads(text[start:end])
                    logger.warning(
                        "Gemini generate_query recovered JSON from non-JSON response | model=%s | raw_preview=%s",
                        self.model_name,
                        _truncate(text)
                    )
                    return parsed
                else:
                    logger.error(
                        "Gemini generate_query parse failure | model=%s | raw_preview=%s",
                        self.model_name,
                        _truncate(text, 600)
                    )
                    return {"error": "Could not parse JSON from response", "raw": response.text}
        
        except Exception as e:
            logger.exception(
                "Gemini generate_query failed | model=%s | user_preview=%s",
                self.model_name,
                _truncate(user_message),
            )
            return {"error": str(e)}
    
    def synthesize_response(
        self,
        system_prompt: str,
        question: str,
        query_spec: Dict,
        query_result: Any
    ) -> Dict[str, Any]:
        """
        Stage 2: Convert raw data to natural language answer.
        
        Args:
            system_prompt: System prompt for synthesis
            question: Original user question
            query_spec: The executed query specification
            query_result: Raw result data from query execution
        
        Returns:
            Parsed JSON with 'answer' and 'highlighted_nodes'
        """
        try:
            result_size = len(query_result) if isinstance(query_result, list) else 1
            logger.info(
                "Gemini synthesize_response start | model=%s | query_type=%s | result_size=%s",
                self.model_name,
                query_spec.get("type", "unknown") if isinstance(query_spec, dict) else "unknown",
                result_size,
            )

            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
                generation_config=GENERATION_CONFIG_SYNTHESIS
            )
            
            # Prepare synthesis prompt
            synthesis_input = f"""
Original question: {question}

Query executed: {json.dumps(query_spec)}

Result data: {json.dumps(query_result, default=str)[:4000]}
"""
            
            response = model.generate_content(synthesis_input)
            
            try:
                parsed = json.loads(response.text)
                logger.info("Gemini synthesize_response success | model=%s", self.model_name)
                return parsed
            except json.JSONDecodeError:
                text = response.text
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    parsed = json.loads(text[start:end])
                    logger.warning(
                        "Gemini synthesize_response recovered JSON from non-JSON response | model=%s | raw_preview=%s",
                        self.model_name,
                        _truncate(text)
                    )
                    return parsed
                else:
                    logger.warning(
                        "Gemini synthesize_response returned plain text fallback | model=%s | raw_preview=%s",
                        self.model_name,
                        _truncate(text, 600)
                    )
                    return {
                        "answer": response.text,
                        "highlighted_nodes": []
                    }
        
        except Exception as e:
            logger.exception(
                "Gemini synthesize_response failed | model=%s | question_preview=%s",
                self.model_name,
                _truncate(question),
            )
            return {"error": str(e)}
