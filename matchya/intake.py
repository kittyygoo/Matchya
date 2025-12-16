from __future__ import annotations

import os
import re
import urllib.parse
from typing import Dict, List, Tuple

import requests
import streamlit as st

from .constants import ALLOWED_EXT, CT_TO_EXT, EXT_GUESS_FALLBACK, MAX_DOWNLOAD_MB, REQ_TIMEOUT
from .models import ResumeArtifact, RoleContext, LLMSettings
from .text_utils import html_to_text, normalize_for_sim, normalize_url, read_file_text, sha1_bytes, sha1_text


def normalize_drive_url(u: str) -> str:
    try:
        pr = urllib.parse.urlparse(u)
        if pr.netloc.lower().endswith("drive.google.com"):
            qs = urllib.parse.parse_qs(pr.query)
            if "id" in qs and qs["id"]:
                file_id = qs["id"][0]
                return f"https://drive.google.com/uc?export=download&id={file_id}"
            m = re.search(r"/file/d/([^/]+)/", pr.path)
            if m:
                file_id = m.group(1)
                return f"https://drive.google.com/uc?export=download&id={file_id}"
    except Exception:
        pass
    return u


def ensure_allowed_extension(filename: str, content_type: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in ALLOWED_EXT:
        return filename
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in CT_TO_EXT:
        return (filename + CT_TO_EXT[ct]) if ext == "" else (os.path.splitext(filename)[0] + CT_TO_EXT[ct])
    for g in EXT_GUESS_FALLBACK:
        if filename.lower().endswith(g):
            return filename
    return filename + ".pdf"


def is_content_type_supported(content_type: str) -> bool:
    ct = (content_type or "").split(";")[0].strip().lower()
    return (ct in CT_TO_EXT) or any(ct.endswith(x) for x in ["pdf", "rtf", "plain", "markdown", "msword", "officedocument.wordprocessingml.document"])


def guess_filename_from_headers(url: str, resp: requests.Response) -> str:
    cd = resp.headers.get("Content-Disposition") or resp.headers.get("content-disposition") or ""
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^\";]+)"?', cd, flags=re.I)
    if m:
        name = m.group(1).strip().strip('"')
        return name
    path = urllib.parse.urlparse(url).path
    base = os.path.basename(path) or "download"
    return base


def stream_download(url: str) -> Tuple[str, bytes, str]:
    headers = {"User-Agent": "Mozilla/5.0 (ResumeRankerBot/1.0)"}
    with requests.get(url, headers=headers, timeout=REQ_TIMEOUT, stream=True, allow_redirects=True) as r:
        r.raise_for_status()
        total = 0
        chunks_list = []
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                chunks_list.append(chunk)
                total += len(chunk)
                if total > MAX_DOWNLOAD_MB * 1024 * 1024:
                    raise RuntimeError(f"File too large (> {MAX_DOWNLOAD_MB}MB)")
        data = b"".join(chunks_list)
        fname = guess_filename_from_headers(url, r)
        fname = ensure_allowed_extension(fname, r.headers.get("Content-Type", ""))
        return fname, data, r.headers.get("Content-Type", "")


def collect_incoming_items(intake_mode: str, files, link_inputs: List[str]) -> List[Dict[str, object]]:
    """Normalize uploaded files or remote links into a single list of work items."""
    incoming_items: List[Dict[str, object]] = []
    if intake_mode == "Upload files":
        for f in (files or []):
            try:
                b = f.getvalue()
                incoming_items.append({"kind": "file", "name": f.name, "bytes": b})
            except Exception as e:
                st.error(f"{f.name}: failed to read — {e}")
    elif intake_mode == "Cloud links":
        if link_inputs:
            st.markdown("#### Downloading resumes from links")
            dl_bar = st.progress(0.0)
            for i, u in enumerate(link_inputs, start=1):
                try:
                    fname, data, ct = stream_download(u)
                    incoming_items.append({"kind": "url", "name": fname, "bytes": data, "url": u, "content_type": ct})
                except Exception as e:
                    st.warning(f"Could not download {u}: {e}")
                finally:
                    dl_bar.progress(i / len(link_inputs))
    return incoming_items


def parse_and_dedupe_items(incoming_items: List[Dict[str, object]], status_holder, progress_bar) -> Tuple[List[ResumeArtifact], set, set]:
    """Read bytes into text, convert HTML when needed, and drop duplicates early."""
    parsed_items: List[ResumeArtifact] = []
    seen_file_hash, seen_text_hash = set(), set()
    total_items = len(incoming_items)

    for i, item in enumerate(incoming_items, start=1):
        disp_name = item.get("name") or item.get("url") or f"item_{i}"
        status_holder.text(f"Reading source: {disp_name} ({i}/{total_items})")
        b = item["bytes"]
        fh = sha1_bytes(b)
        if fh in seen_file_hash:
            progress_bar.progress(i / total_items)
            continue

        content_type = (item.get("content_type") or "").lower()
        ext = os.path.splitext(disp_name)[1].lower()

        try:
            if content_type.startswith("text/html") or ext in {".html", ".htm"}:
                text = html_to_text(b, base_url=item.get("url", ""))
            else:
                if ext not in ALLOWED_EXT and ext == "":
                    disp_name = disp_name + ".pdf"
                    ext = ".pdf"
                text = read_file_text(disp_name, b)
        except Exception as e:
            st.error(f"{disp_name}: failed to read — {e}")
            progress_bar.progress(i / total_items)
            continue

        th = sha1_text(normalize_for_sim(text))
        if th in seen_text_hash:
            progress_bar.progress(i / total_items)
            continue

        parsed_items.append(
            ResumeArtifact(
                id=fh,
                file_hash=fh,
                text_hash=th,
                name=disp_name,
                text=text,
                url=item.get("url", ""),
            )
        )

        seen_file_hash.add(fh)
        seen_text_hash.add(th)
        progress_bar.progress(i / total_items)

    return parsed_items, seen_file_hash, seen_text_hash


def validate_inputs(settings: LLMSettings, role_ctx: RoleContext, intake_mode: str, files, link_inputs: List[str]):
    """Stop execution with clear UI errors when required inputs are missing."""
    if settings.provider == "openai" and not settings.api_key:
        st.error("Provide an OpenAI API Key")
        st.stop()
    if settings.provider == "openrouter" and not settings.api_key:
        st.error("Provide an OpenRouter API Key")
        st.stop()
    if settings.provider == "custom" and not settings.base_url.strip():
        st.error("Custom providers require a base_url")
        st.stop()
    if not role_ctx.description.strip():
        st.error("Role description is required: add a short vacancy/context paragraph")
        st.stop()
    if not role_ctx.criteria:
        st.error("Please provide valid criteria")
        st.stop()
    if intake_mode == "Select an option":
        st.error("Choose how to provide resumes: upload files or paste cloud links")
        st.stop()
    if intake_mode == "Upload files" and not files:
        st.error("Upload at least one resume file")
        st.stop()
    if intake_mode == "Cloud links" and not link_inputs:
        st.error("Add at least one direct link to resume files or pages")
        st.stop()
