from __future__ import annotations

import hashlib
import io
import os
import re
from typing import List

from bs4 import BeautifulSoup

from .constants import EMAIL_RE, NAME_RE, PHONE_CAND_RE, TOKEN_SPLIT

try:
    from pdfminer.high_level import extract_text as pdf_extract_text
except Exception:
    pdf_extract_text = None
try:
    import docx
except Exception:
    docx = None

ALLOWED_RTF = {".txt", ".md", ".rtf"}


def read_file_text(filename: str, bytes_data: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        if not pdf_extract_text:
            raise RuntimeError("pdfminer.six is missing. pip install pdfminer.six")
        with io.BytesIO(bytes_data) as bio:
            return pdf_extract_text(bio)
    if ext == ".docx":
        if not docx:
            raise RuntimeError("python-docx is missing. pip install python-docx")
        with io.BytesIO(bytes_data) as bio:
            d = docx.Document(bio)
            return "\n".join(p.text for p in d.paragraphs)
    if ext in ALLOWED_RTF:
        try:
            return bytes_data.decode("utf-8", errors="ignore")
        except Exception:
            return bytes_data.decode("latin-1", errors="ignore")
    raise ValueError(f"Unsupported format: {ext}")


def html_to_text(html_bytes: bytes, base_url: str = "") -> str:
    try:
        soup = BeautifulSoup(html_bytes, "lxml")
    except Exception:
        soup = BeautifulSoup(html_bytes, "html.parser")
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    for t in soup.find_all(["nav", "footer", "aside"]):
        t.decompose()
    title = ""
    try:
        title = (soup.title.string or "").strip()
    except Exception:
        pass
    text = soup.get_text(separator="\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    header_bits = []
    if title:
        header_bits.append(title)
    if base_url:
        header_bits.append(base_url)
    return ("\n".join(header_bits + [text])).strip()


def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def sha1_text(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()


def normalize_for_sim(t: str) -> str:
    t = re.sub(r"\s+", " ", t.lower())
    return re.sub(r"[^a-zа-я0-9 ]+", " ", t)


def normalize_phone_digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit() or ch == "+")


def best_phone(phones: List[str]) -> str:
    cleaned = []
    for p in phones:
        norm = normalize_phone_digits(p)
        digits = "".join(d for d in norm if d.isdigit())
        if 10 <= len(digits) <= 15:
            cleaned.append(norm)
    if not cleaned:
        return ""
    cleaned.sort(key=lambda x: (not x.startswith("+"), -len(x)))
    return cleaned[0]


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]


def clamp(s: str, max_len: int) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return (s[:max_len-1] + "…") if len(s) > max_len else s


def normalize_url(u: str) -> str:
    u = (u or "").strip().strip('"').strip("'")
    if not u:
        return ""
    u = u.replace(" ", "%20")
    if not re.match(r"^https?://", u, flags=re.I):
        return ""
    return u


def guess_full_name(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()][:30]
    for l in lines:
        if EMAIL_RE.search(l) or PHONE_CAND_RE.search(l) or "http" in l.lower():
            continue
        m = NAME_RE.search(l)
        if m:
            return m.group(0)
    return ""


def extract_contacts(text: str) -> tuple[list[str], list[str]]:
    emails = EMAIL_RE.findall(text)
    phones = PHONE_CAND_RE.findall(text)
    return emails, phones
