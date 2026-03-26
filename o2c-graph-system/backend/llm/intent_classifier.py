"""
Intent classifier - determines if a query is on-topic for the O2C dataset.
Implements Layer 1 guardrail via keyword matching.
"""

import logging

logger = logging.getLogger(__name__)

# Off-topic signals that should be blocked
OFF_TOPIC_KEYWORDS = [
    # Knowledge questions
    "capital of", "who invented", "explain quantum", "write a poem",
    "tell me a joke", "translate", "recipe for", "weather in",
    
    # Injection/jailbreak attempts
    "ignore previous", "you are now", "pretend you are", "pretend to be",
    "system prompt", "jailbreak", "act as if", "act as", "forget your instructions",
    "DAN mode", "hypothetically", "in a fictional world",
    
    # Out of domain
    "stock price", "cryptocurrency", "sports score", "movie review",
    "book review", "political opinion", "write code for", "debug my",
    "medical advice", "legal advice", "financial advice"
]

O2C_DOMAIN_KEYWORDS = [
    "order", "delivery", "billing", "invoice", "payment", "customer",
    "product", "material", "journal", "gl account", "sales", "po",
    "shipment", "revenue", "fiscal", "plant", "storage", "warehouse",
    "amount", "document", "status", "date", "flow", "trace", "broken",
    "incomplete", "missing", "quantity", "unit", "price", "address",
    "partner", "company", "transaction", "currency", "posting"
]


def classify_intent(query: str) -> tuple:
    """
    Classify if a query is on-topic for the O2C dataset.
    
    Returns:
        Tuple of (is_on_topic: bool|None, reason: str)
        - True: Definitely on-topic
        - False: Definitely off-topic
        - None: Ambiguous, let LLM decide
    """
    query_lower = query.lower()
    query_words = query_lower.split()
    
    # Layer 1: Check for explicit off-topic patterns
    for keyword in OFF_TOPIC_KEYWORDS:
        if keyword in query_lower:
            return False, f"Matched off-topic pattern: '{keyword}'"
    
    # Layer 2: Check for domain relevance
    has_domain_terms = any(kw in query_lower for kw in O2C_DOMAIN_KEYWORDS)
    
    # Very short queries without domain terms -> ambiguous
    if len(query_words) <= 2 and not has_domain_terms:
        return None, "ambiguous"
    
    # Queries with O2C domain terms -> likely on-topic
    if has_domain_terms:
        return True, "on_topic"
    
    # Medium-length queries without domain terms -> ambiguous
    if len(query_words) > 3 and len(query_words) <= 10 and not has_domain_terms:
        return None, "ambiguous"
    
    # Long queries without domain terms -> likely off-topic
    if len(query_words) > 10 and not has_domain_terms:
        return False, "No O2C domain keywords detected in lengthy query"
    
    # Default: on-topic (let LLM decide)
    return True, "on_topic"


def is_potential_injection(query: str) -> bool:
    """Check if query contains SQL injection or prompt injection patterns."""
    dangerous_patterns = [
        "DROP", "DELETE", "INSERT", "UPDATE", "ALTER",
        "exec(", "eval(", "__import__", "system(",
        "subprocess", "os.system"
    ]
    
    query_upper = query.upper()
    return any(pattern in query_upper for pattern in dangerous_patterns)
