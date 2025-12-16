from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


@dataclass
class LLMSettings:
    provider: str
    api_key: str
    model: str
    base_url: str = ""
    headers: Optional[Dict[str, str]] = None


@dataclass
class RoleContext:
    description: str
    criteria: List["Criterion"]


@dataclass
class ResumeArtifact:
    id: str
    file_hash: str
    text_hash: str
    name: str
    text: str
    url: str = ""


class Criterion(BaseModel):
    name: str
    weight: float = Field(1.0, ge=0)
    keywords: List[str] = Field(default_factory=list)


class LLMScores(BaseModel):
    scores: Dict[str, float]
    reasoning: Dict[str, str] = Field(default_factory=dict)
