"""
GeminiForge
===========

AI-powered project generator that uses five specialised
Gemini agents with Retrieval-Augmented Generation.
"""

# Configure logging first so all sub-imports inherit it
from .logging_config import LOGGING  # noqa: F401  (import for side-effect)

__all__ = [
    "ProjectContext",
    "RAGManager",
    "GeminiAPIManager",
    "ProjectWorkflowManager",
    "WorkflowCLI",
]

from .context import ProjectContext  # noqa: E402
from .rag_manager import RAGManager  # noqa: E402
from .api_manager import GeminiAPIManager  # noqa: E402
from .workflow import ProjectWorkflowManager  # noqa: E402
from .cli import WorkflowCLI  # noqa: E402

__version__ = "0.1.0"
__author__ = "Huy Tran"
__email__ = "huytrngqu@gmail.com"
__license__ = "MIT"
__status__ = "Development"
