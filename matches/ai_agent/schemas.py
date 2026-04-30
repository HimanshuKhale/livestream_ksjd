from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentToolResult:
    ok: bool
    tool_name: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class AgentResponse:
    ok: bool
    answer: str
    tool_results: List[Dict[str, Any]]
    created_banner: bool = False
    created_card_id: Optional[int] = None
    error: Optional[str] = None
