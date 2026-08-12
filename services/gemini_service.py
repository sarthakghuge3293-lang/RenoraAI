"""
Compatibility wrapper.

Old routes may still import generate_response
from services.gemini_service.
"""

from services.ai_engine import (
    ai_engine,
    generate_response,
)


__all__ = [
    "ai_engine",
    "generate_response",
]