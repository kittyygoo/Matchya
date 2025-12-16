from __future__ import annotations

import re

ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md", ".rtf"}
TOKEN_SPLIT = re.compile(r"[\W_]+", re.UNICODE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_CAND_RE = re.compile(r"(?:\+?\d[\d\-\s()\./]{6,}\d)")
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

CT_TO_EXT = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/rtf": ".rtf",
    "application/rtf": ".rtf",
    "text/markdown": ".md",
}

EXT_GUESS_FALLBACK = [".pdf", ".docx", ".txt", ".rtf", ".md"]
MAX_DOWNLOAD_MB = 25
REQ_TIMEOUT = 30

DEFAULT_MODEL_CHOICES = {
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
    "openrouter": ["openrouter/auto", "anthropic/claude-3.5-sonnet", "openai/gpt-4o-mini"],
    "lmstudio": ["lmstudio-community/gpt-4o-mini-gguf", "lmstudio-community/llama-3.1-8b-instruct"],
    "custom": ["gpt-4o-mini"],
}

NAME_RE = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+(?: [A-Z][a-z]+)?\b")
