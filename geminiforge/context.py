from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional
@dataclass
class ProjectContext:
    """Shared context giữa các API"""
    project_name: str
    requirements: Optional[Dict] = None
    architecture: Optional[Dict] = None
    codebase: Optional[Dict] = None
    test_results: Optional[Dict] = None
    deployment: Optional[Dict] = None
    created_at: str = None
    current_stage: str = "not_started"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()