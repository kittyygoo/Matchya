from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import requests
import streamlit as st

from .constants import DEFAULT_MODEL_CHOICES, REQ_TIMEOUT
from .models import Criterion, LLMSettings


def _safe_get_json(url: str, headers: Optional[Dict[str, str]] = None) -> Dict:
    resp = requests.get(url, headers=headers or {}, timeout=REQ_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(show_spinner=False)
def fetch_provider_models(provider: str, api_key: str = "", base_url: str = "") -> List[str]:
    """Fetch model list for the UI; fall back to defaults when discovery fails."""
    provider = (provider or "").strip().lower()
    if provider not in DEFAULT_MODEL_CHOICES:
        return DEFAULT_MODEL_CHOICES["openai"]

    try:
        if provider == "openai" and api_key.strip():
            from openai import OpenAI

            client = OpenAI(api_key=api_key.strip())
            models = client.models.list().data
            ids = sorted({m.id for m in models if getattr(m, "id", "")})
            if ids:
                return ids
        elif provider == "openrouter" and api_key.strip():
            data = _safe_get_json(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key.strip()}"},
            )
            ids = sorted({m.get("id", "") for m in data.get("data", []) if m.get("id")})
            if ids:
                return ids
        elif provider == "lmstudio":
            # Support both /v1 and plain roots to be resilient to user-supplied base URLs
            base = (base_url or "http://localhost:1234").rstrip("/")
            primary = base if base.endswith("/v1") else base + "/v1"
            candidates = [primary + "/models"]
            if base != primary:
                candidates.append(base + "/models")  # fallback for pre-suffixed URLs

            headers = {"Authorization": f"Bearer {api_key.strip()}"} if api_key.strip() else None
            for url in candidates:
                try:
                    data = _safe_get_json(url, headers=headers)
                    ids = sorted({m.get("id", "") for m in data.get("data", []) if m.get("id")})
                    if ids:
                        return ids
                except Exception:
                    continue
            raise RuntimeError("LM Studio did not return model IDs")
    except Exception as exc:
        st.warning(f"Failed to fetch models from {provider}: {exc}")

    return DEFAULT_MODEL_CHOICES[provider]


class LLMClient:
    """Thin wrapper for OpenAI-compatible LLMs."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = "", extra_headers: Optional[Dict[str, str]] = None):
        from openai import OpenAI

        client_opts = {"api_key": api_key}
        if base_url:
            client_opts["base_url"] = base_url
        if extra_headers:
            client_opts["default_headers"] = extra_headers
        self.client = OpenAI(**client_opts)
        self.model = model

    def score_and_extract_single(self, resume: Dict[str, str], role_desc: str, criteria: List[Criterion]) -> Dict[str, object]:
        """Safer single-resume scoring without batching."""

        system = (
            "You are an HR assistant. You receive ONE resume.\n"
            "1) Extract specialization: 'specialization_main' (<=80 chars) plus up to 3 alternatives.\n"
            "2) Extract the candidate full name into 'full_name' (leave empty if unknown).\n"
            "3) Extract contacts: 'emails' and 'phones' (international format preferred).\n"
            "4) Score every criterion 0..5 with concise reasoning per criterion.\n"
            "Return JSON exactly following the schema."
        )

        payload = {
            "role_description": role_desc,
            "criteria": [c.model_dump() for c in criteria],
            "resume": {"id": resume["id"], "text": resume["text"][:18000]},
        }

        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "full_name": {"type": "string"},
                "specialization_main": {"type": "string"},
                "specialization_alt": {"type": "array", "items": {"type": "string"}},
                "emails": {"type": "array", "items": {"type": "string"}},
                "phones": {"type": "array", "items": {"type": "string"}},
                "scores": {"type": "object", "additionalProperties": {"type": "number"}},
                "reasoning": {"type": "object", "additionalProperties": {"type": "string"}},
            },
            "required": ["id", "specialization_main", "emails", "phones", "scores"],
            "additionalProperties": False,
        }

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_schema", "json_schema": {"name": "ResumeSingle", "schema": schema}},
            temperature=0.1,
        )

        content = resp.choices[0].message.content
        data = json.loads(content)
        return data

    def suggest_criteria(self, role_desc: str, max_items: int = 10) -> List[Criterion]:
        """Generate skill/criteria suggestions from the role description."""
        prompt = {
            "role_description": role_desc,
            "format": "json",
            "max_items": max_items,
        }
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a career expert. Based on the job description, return up to 10 key criteria/skills. "
                        "Each item: name, weight (0.5..3.0, higher for must-haves), keywords (3-6)."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "Criteria",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "criteria": {
                                "type": "array",
                                "maxItems": max_items,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "weight": {"type": "number"},
                                        "keywords": {"type": "array", "items": {"type": "string"}},
                                    },
                                    "required": ["name", "weight"],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["criteria"],
                        "additionalProperties": False,
                    },
                },
            },
            temperature=0.2,
        )
        raw = json.loads(resp.choices[0].message.content)
        out: List[Criterion] = []
        for item in raw.get("criteria", []):
            try:
                out.append(Criterion(**item))
            except Exception:
                continue
        return out


def create_llm_client(settings: LLMSettings) -> LLMClient:
    provider = (settings.provider or "openai").lower()
    if provider == "lmstudio":
        base_url = settings.base_url.strip() or "http://localhost:1234/v1"
        key = settings.api_key.strip() or "lm-studio"
        return LLMClient(api_key=key, model=settings.model, base_url=base_url)
    if provider == "openrouter":
        key = settings.api_key.strip()
        if not key:
            raise ValueError("OpenRouter API Key is required")
        headers = settings.headers or {
            "HTTP-Referer": "https://github.com/user/portfolio",  # good manners for OpenRouter
            "X-Title": "Resume ranker",
        }
        return LLMClient(api_key=key, model=settings.model, base_url="https://openrouter.ai/api/v1", extra_headers=headers)
    if provider == "custom":
        base_url = settings.base_url.strip()
        if not base_url:
            raise ValueError("Provide base_url for the custom provider")
        key = settings.api_key.strip() or "token-placeholder"
        return LLMClient(api_key=key, model=settings.model, base_url=base_url, extra_headers=settings.headers)
    return LLMClient(
        api_key=settings.api_key.strip(),
        model=settings.model,
        base_url=settings.base_url or "",
        extra_headers=settings.headers,
    )
