"""
🍵 Matchya — Resume Ranker

Features:
- OpenAI-compatible LLMs (OpenAI, OpenRouter, LM Studio, custom) extract the main role, full name, contacts, and scores per
  criterion with concise reasoning — one request per resume for reliability.
- Robust composite scoring: 0.75×weighted percentiles + 0.25×coverage.
- Strong deduplication: same files/texts, same emails/phones, and near-duplicates by similarity threshold.
- Export to XLSX with styling, duplicate risk highlights, and similarity pairs for audits.
- JSONL checkpointing by SHA1 for safe resumability.
- Sources: uploaded files or direct cloud links to resume files (PDF/DOCX/TXT/MD/RTF/HTML).

Quick start:
    pip install streamlit pdfminer.six python-docx rapidfuzz pandas openpyxl pydantic tenacity openai requests beautifulsoup4 lxml

Run:
    streamlit run app.py
"""

from __future__ import annotations

import io
import os
import re
from typing import Dict, List

import pandas as pd
import streamlit as st

from matchya.checkpoint import append_checkpoint, load_checkpoint, reset_checkpoint
from matchya.constants import ALLOWED_EXT, EMAIL_RE, PHONE_CAND_RE
from matchya.intake import collect_incoming_items, parse_and_dedupe_items, validate_inputs
from matchya.llm_client import create_llm_client, fetch_provider_models
from matchya.models import Criterion, LLMSettings, RoleContext
from matchya.scoring import compute_scores_table
from matchya.similarity import max_similarities
from matchya.text_utils import best_phone, clamp, extract_contacts, guess_full_name, normalize_url


# ---------- UI ----------
st.set_page_config(page_title="🍵 Matchya — Hire faster", layout="wide")
st.markdown(
    """
    <style>
    section[data-testid='stSidebar'] {width: 27rem;}
    section[data-testid='stSidebar'] > div:first-child {width: 27rem;}
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("🍵 Matchya")
st.caption("Hire faster")

with st.sidebar:
    st.header("⚙️ LLM")
    provider = st.selectbox(
        "LLM provider",
        ["openai", "openrouter", "lmstudio", "custom"],
        format_func=lambda x: {
            "openai": "OpenAI (cloud)",
            "openrouter": "OpenRouter (cloud)",
            "lmstudio": "LM Studio (local)",
            "custom": "Custom base_url",
        }[x],
    )
    api_key = st.text_input(
        "API Key",
        type="password",
        help="Leave blank for LM Studio if you rely on the default 'lm-studio' token.",
    )
    default_lm_url = "http://localhost:1234/v1"
    custom_base_url = ""
    if provider in {"lmstudio", "custom"}:
        custom_base_url = st.text_input(
            "Base URL (LM Studio/custom)",
            value=default_lm_url if provider == "lmstudio" else "",
            help="OpenAI-compatible endpoint. LM Studio default port is 1234.",
        )
    model_options = fetch_provider_models(provider, api_key, custom_base_url)
    model_name = st.selectbox("Model", model_options, index=0)

    llm_headers = {"HTTP-Referer": "https://github.com/user/portfolio", "X-Title": "Matchya"} if provider == "openrouter" else None
    llm_settings = LLMSettings(
        provider=provider,
        api_key=api_key,
        model=model_name,
        base_url=custom_base_url,
        headers=llm_headers,
    )

    st.header("📌 Role & criteria")
    role_desc = st.text_area("Role / vacancy description (required)", height=140)

    st.subheader("Key skills / criteria (required)")
    default_criteria = [
        {"name": "Domain experience", "weight": 2.0, "keywords": ["experience", "domain"]},
        {"name": "Hard skills", "weight": 1.8, "keywords": ["stack", "tech"]},
        {"name": "Soft skills", "weight": 1.2, "keywords": ["communication", "teamwork"]},
        {"name": "Achievements", "weight": 1.4, "keywords": ["results", "impact"]},
    ]
    crit_state_key = "criteria_table"
    if crit_state_key not in st.session_state:
        st.session_state[crit_state_key] = [
            {
                "Criterion": c["name"],
                "Weight": c["weight"],
                "Keywords": ", ".join(c.get("keywords") or []),
            }
            for c in default_criteria
        ]

    def _generate_criteria():
        if not role_desc.strip():
            st.error("Add a role description first to generate skills automatically.")
            return
        try:
            generator_client = create_llm_client(llm_settings)
            generated = generator_client.suggest_criteria(role_desc)
            if not generated:
                st.warning("LLM returned no skills. Please fill manually.")
                return
            st.session_state[crit_state_key] = [
                {"Criterion": c.name, "Weight": c.weight, "Keywords": ", ".join(c.keywords)}
                for c in generated
            ]
            st.session_state["criteria_generated_ok"] = True
        except Exception as e:
            st.error(f"Could not generate skills: {e}")

    crit_cols = st.columns([1, 3])
    with crit_cols[0]:
        if st.button("⚡️ Generate skills", use_container_width=True):
            _generate_criteria()
        st.caption("Optional: draft criteria from the description, then tweak below.")

    editor_value = st.data_editor(
        st.session_state[crit_state_key],
        column_config={
            "Criterion": st.column_config.TextColumn("Criterion", help="One skill per row"),
            "Weight": st.column_config.NumberColumn(
                "Weight (0.0–3.0)", min_value=0.0, step=0.1, format="%.1f"
            ),
            "Keywords": st.column_config.TextColumn(
                "Keywords (comma-separated)",
                help="Optional hints to keep the LLM focused",
                width="medium",
            ),
        },
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        key="criteria_editor",
    )

    st.session_state[crit_state_key] = (
        editor_value.to_dict("records") if hasattr(editor_value, "to_dict") else editor_value
    )

    if st.session_state.pop("criteria_generated_ok", False):
        st.success("Skills generated and inserted below")

    criteria: List[Criterion] = []
    try:
        crit_records = st.session_state.get(crit_state_key, [])
        parsed_records: List[Dict[str, object]] = (
            crit_records.to_dict("records") if hasattr(crit_records, "to_dict") else list(crit_records)
        )
        for row in parsed_records:
            name = str(row.get("Criterion", "")).strip()
            if not name:
                continue
            weight_val = float(row.get("Weight") or 0.0)
            kw_raw = row.get("Keywords") or ""
            if isinstance(kw_raw, list):
                keywords = [str(k).strip() for k in kw_raw if str(k).strip()]
            else:
                keywords = [k.strip() for k in str(kw_raw).split(",") if k.strip()]
            criteria.append(Criterion(name=name, weight=weight_val, keywords=keywords))
    except Exception as e:
        st.error(f"Criteria parsing error: {e}")

    role_ctx = RoleContext(description=role_desc, criteria=criteria)

    st.subheader("Duplicates")
    dup_threshold = st.slider("Similarity threshold (duplicate risk)", min_value=70, max_value=100, value=90, step=1)

    st.subheader("Output")
    save_path = st.text_input("Save XLSX path (server)", value="resume_ranking.xlsx")
    add_pairs = st.checkbox("Include SimilarityPairs sheet (top 200)", value=True)

    st.subheader("Checkpoint")
    cp_path = st.text_input("Checkpoint file (.jsonl)", value="resume_ranker_checkpoint.jsonl")
    colA, colB = st.columns(2)
    with colA:
        resume_from_cp = st.checkbox("Resume from checkpoint", value=True)
    with colB:
        if st.button("♻️ Reset checkpoint"):
            reset_checkpoint(cp_path)
            st.success("Checkpoint removed.")

st.markdown("## 📥 Resume intake")
intake_mode = st.selectbox("Choose how to provide resumes", ["Select an option", "Upload files", "Cloud links"])
files: List = []
link_inputs: List[str] = []

if intake_mode == "Upload files":
    files = st.file_uploader(
        "Files (PDF/DOCX/TXT/MD/RTF)",
        type=[ext[1:] for ext in ALLOWED_EXT],
        accept_multiple_files=True,
    )
elif intake_mode == "Cloud links":
    urls_raw = st.text_area(
        "One link per line (direct links to resume files or HTML pages)",
        placeholder="https://...",
    )
    link_inputs = [normalize_url(u) for u in urls_raw.splitlines() if normalize_url(u)]

run = st.button("🚀 Process and export XLSX")

# ---------- Main ----------
if run:
    validate_inputs(llm_settings, role_ctx, intake_mode, files, link_inputs)

    try:
        client = create_llm_client(llm_settings)
    except Exception as e:
        st.error(f"LLM client could not be created: {e}")
        st.stop()
    cache = load_checkpoint(cp_path) if resume_from_cp else {}

    rows: List[Dict] = []
    texts: List[str] = []
    filenames: List[str] = []
    criteria = role_ctx.criteria

    incoming_items = collect_incoming_items(intake_mode, files, link_inputs)

    status = st.empty()
    st.markdown("#### Progress")
    progress_bar = st.progress(0.0)

    parsed_items, _, _ = parse_and_dedupe_items(incoming_items, status, progress_bar)

    kept_after_parse = len(parsed_items)
    status.text(f"Parsing finished. Sources: {len(incoming_items)}. After local dedup: {kept_after_parse}.")

    if not parsed_items:
        st.warning("No usable resumes after parsing/dedup")
        st.stop()

    progress_bar.progress(0.0)

    total_llm = len(parsed_items)
    for idx, it in enumerate(parsed_items, start=1):
        status.text(f"LLM {idx}/{total_llm}: {it.name}")

        if "pack" not in cache.get(it.file_hash, {}):
            try:
                pack = client.score_and_extract_single(
                    resume={"id": it.id, "text": it.text},
                    role_desc=role_ctx.description,
                    criteria=criteria,
                )
            except Exception as e:
                st.error(f"LLM error on {it.name}: {e}")
                pack = {}

            obj = cache.get(it.file_hash, {})
            obj["pack"] = {
                "id": it.id,
                "full_name": "",
                "specialization_main": "",
                "specialization_alt": [],
                "emails": [],
                "phones": [],
                "scores": {},
                "reasoning": {},
                **(pack or {}),
            }
            cache[it.file_hash] = obj
            append_checkpoint(cp_path, it.file_hash, obj)

        cobj = cache[it.file_hash]["pack"]
        text = it.text

        emails_all, phones_all = extract_contacts(text)
        emails_all = list(cobj.get("emails") or []) or emails_all
        phones_all = list(cobj.get("phones") or []) or phones_all
        email_final = emails_all[0] if emails_all else ""
        phone_final = best_phone(phones_all)

        fio_llm = (cobj.get("full_name") or "").strip()
        fio_val = fio_llm if fio_llm else guess_full_name(text)

        specialization = (cobj.get("specialization_main") or "").strip()
        if not specialization:
            lines = [l.strip() for l in text.splitlines() if l.strip()][:20]
            for l in lines[:15]:
                if "@" in l or re.search(r"https?://", l):
                    continue
                if EMAIL_RE.search(l) or PHONE_CAND_RE.search(l):
                    continue
                if len(l) <= 140 and (l.istitle() or re.search(r"[A-Za-zА-Яа-я ]{6,}", l)):
                    specialization = l
                    break

        score_map = {k: float(cobj.get("scores", {}).get(k, 0.0)) for k in [c.name for c in criteria]}
        base = {
            "File": it.name,
            "FullName": fio_val,
            "Specialization": specialization,
            "Email": email_final,
            "Phone": phone_final,
            "FullText": text,
            "SourceURL": it.url,
            "_FileHash": it.file_hash,
            "_TextHash": it.text_hash,
            "_Reasoning": cobj.get("reasoning", {}),
        }
        for c in criteria:
            base[f"{c.name} (0-5)"] = score_map.get(c.name, 0.0)

        rows.append(base)
        texts.append(text)
        filenames.append(it.name)

        progress_bar.progress(idx / total_llm)

    if not rows:
        st.warning("No successful LLM results")
        st.stop()

    # -------- Pass 3: similarity + email/phone duplicate removal --------
    sim_max, sim_near, pairs_df = max_similarities(texts, filenames)
    for idx, row in enumerate(rows):
        row["SimilarityMax"] = round(sim_max[idx], 1)
        row["NearDuplicateOf"] = sim_near[idx]

    by_email: Dict[str, int] = {}
    by_phone: Dict[str, int] = {}
    keep_mask = [True] * len(rows)

    def norm_email(e: str) -> str:
        return (e or "").strip().lower()

    def norm_phone(p: str) -> str:
        return "".join(d for d in (p or "") if d.isdigit())

    for i, r in enumerate(rows):
        e = norm_email(r.get("Email", ""))
        if e:
            if e in by_email:
                keep_mask[i] = False
            else:
                by_email[e] = i
    for i, r in enumerate(rows):
        if not keep_mask[i]:
            continue
        p = norm_phone(r.get("Phone", ""))
        if p:
            if p in by_phone:
                keep_mask[i] = False
            else:
                by_phone[p] = i

    if not pairs_df.empty:
        name_to_idx = {rows[i]["File"]: i for i in range(len(rows))}
        for _, r in pairs_df.iterrows():
            a, b, s = r["FileA"], r["FileB"], float(r["Similarity"])
            ia, ib = name_to_idx.get(a), name_to_idx.get(b)
            if ia is None or ib is None:
                continue
            if not keep_mask[ia] or not keep_mask[ib]:
                continue
            if s >= 100.0 or s >= dup_threshold:
                drop = ib if ia < ib else ia
                keep_mask[drop] = False

    rows = [r for i, r in enumerate(rows) if keep_mask[i]]

    # -------- Tables and export --------
    df = compute_scores_table(rows, criteria, dup_threshold)

    show_cols = [
        "File",
        "FullName",
        "Specialization",
        "Email",
        "Phone",
        "SourceURL",
        "Coverage",
        "CompositeScore",
        "PriorityBucket",
        "SimilarityMax",
        "NearDuplicateOf",
        "CalcComment",
    ]
    crit_cols = [f"{c.name} (0-5)" for c in criteria if f"{c.name} (0-5)" in df.columns]
    final_df = df[[c for c in show_cols if c in df.columns] + crit_cols].copy()
    final_df.insert(0, "Rank", range(1, len(final_df) + 1))
    final_df = final_df.sort_values(["CompositeScore", "SimilarityMax"], ascending=[False, False]).reset_index(drop=True)
    final_df["Rank"] = range(1, len(final_df) + 1)

    # Stats sheets
    stats = []
    for c in criteria:
        pcol = f"{c.name}::Pct"
        if pcol in df:
            s = df[pcol].dropna()
            stats.append(
                {
                    "Criterion": c.name,
                    "Weight": float(c.weight),
                    "MedianPct": float(s.median()) if len(s) else 0.0,
                    "P10": float(s.quantile(0.10)) if len(s) else 0.0,
                    "P90": float(s.quantile(0.90)) if len(s) else 0.0,
                    "CoverageShare": float((df[f"{c.name} (0-5)"] > 0).mean()) if f"{c.name} (0-5)" in df else 0.0,
                }
            )
    crit_stats_df = pd.DataFrame(stats)
    similarity_pairs_df = pairs_df.head(200).copy() if add_pairs and not pairs_df.empty else pd.DataFrame(columns=["FileA", "FileB", "Similarity"])

    logic_text = (
        "How scores are produced:\n"
        "• LLM scores 0–5 per criterion with reasoning — one resume per request to avoid cross-talk.\n"
        "• Full name comes from the LLM with a light text heuristic fallback.\n"
        "• Each request includes the role description and the criteria table (sent as JSON) — scores rely on this context.\n"
        "• Composite = 0.75×weighted percentiles + 0.25×coverage.\n"
        "• Duplicates: identical files/texts and repeated email/phone are dropped; Similarity ≥ threshold is flagged as risk.\n"
        "• Comment includes name/specialization, top strengths with excerpts, gaps (low scores), and risks."
    )
    config_df = pd.DataFrame(
        {
            "Key": [
                "Model",
                "RoleDescription",
                "DuplicateThreshold",
                "CheckpointFile",
                "TotalUploaded",
                "KeptAfterLocalDedup",
                "BatchSize",
                "NumBatches",
                "HumanLogic",
            ],
            "Value": [
                model_name,
                role_desc.strip()[:160] + ("…" if len(role_desc.strip()) > 160 else ""),
                str(dup_threshold),
                cp_path,
                str(len(incoming_items)),
                str(len(parsed_items)),
                "1 (no batching)",
                str(len(parsed_items)),
                logic_text,
            ],
        }
    )

    # Write XLSX with formatting
    from openpyxl.formatting.rule import ColorScaleRule, DataBarRule
    from openpyxl.styles import Alignment, Border, Color, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    DATA_BAR_COLOR = Color("FF63BE7B")

    xlsx_buf = io.BytesIO()
    with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as xw:
        final_df.to_excel(xw, sheet_name="Ranking", index=False)
        crit_stats_df.to_excel(xw, sheet_name="CriteriaStats", index=False)
        similarity_pairs_df.to_excel(xw, sheet_name="SimilarityPairs", index=False)
        config_df.to_excel(xw, sheet_name="Config", index=False)

        wb = xw.book
        ws = wb["Ranking"]

        thin = Side(border_style="thin", color="DDDDDD")
        border_all = Border(left=thin, right=thin, top=thin, bottom=thin)
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.border = border_all
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        for r in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
            for cell in r:
                cell.border = border_all
                cell.alignment = Alignment(vertical="top", wrap_text=True)

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        stripe = PatternFill(start_color="F7F7F7", end_color="F7F7F7", fill_type="solid")
        for row in range(2, ws.max_row + 1, 2):
            for col in range(1, ws.max_column + 1):
                ws.cell(row=row, column=col).fill = stripe

        for col_idx in range(1, ws.max_column + 1):
            col = get_column_letter(col_idx)
            max_len = max(
                len(str(ws[f"{col}{r}"].value)) if ws[f"{col}{r}"].value is not None else 0
                for r in range(1, ws.max_row + 1)
            )
            ws.column_dimensions[col].width = min(50, max(12, max_len + 2))

        headers = {cell.value: cell.col_idx for cell in ws[1]}

        def col_letter(name: str) -> str:
            return get_column_letter(headers[name])

        if "CompositeScore" in headers:
            c = col_letter("CompositeScore")
            ws.conditional_formatting.add(
                f"{c}2:{c}{ws.max_row}",
                ColorScaleRule(
                    start_type="min",
                    start_color="F8696B",
                    mid_type="percentile",
                    mid_value=50,
                    mid_color="FFEB84",
                    end_type="max",
                    end_color="63BE7B",
                ),
            )

        for h, idx in headers.items():
            if h.endswith(" (0-5)"):
                col = get_column_letter(idx)
                rule = DataBarRule(
                    start_type="num",
                    start_value=0,
                    end_type="num",
                    end_value=5,
                    color=DATA_BAR_COLOR,
                    showValue=True,
                )
                ws.conditional_formatting.add(f"{col}2:{col}{ws.max_row}", rule)

        if "PriorityBucket" in headers:
            bc = col_letter("PriorityBucket")
            for row in range(2, ws.max_row + 1):
                v = str(ws[f"{bc}{row}"].value or "")
                fill = None
                if v == "A":
                    fill = PatternFill(start_color="E6F4EA", end_color="E6F4EA", fill_type="solid")
                elif v == "B":
                    fill = PatternFill(start_color="FFF5CC", end_color="FFF5CC", fill_type="solid")
                elif v == "C":
                    fill = PatternFill(start_color="FDE7E9", end_color="FDE7E9", fill_type="solid")
                if fill:
                    for col in range(1, ws.max_column + 1):
                        ws.cell(row=row, column=col).fill = fill

        if "SimilarityMax" in headers:
            sc = col_letter("SimilarityMax")
            for row in range(2, ws.max_row + 1):
                try:
                    val = float(ws[f"{sc}{row}"].value)
                    if val >= dup_threshold:
                        fill = PatternFill(start_color="FFE8AA", end_color="FFE8AA", fill_type="solid")
                        for col in range(1, ws.max_column + 1):
                            ws.cell(row=row, column=col).fill = fill
                        ws[f"{sc}{row}"].font = Font(bold=True)
                except Exception:
                    pass

    data = xlsx_buf.getvalue()

    # Save to server
    try:
        if save_path:
            with open(save_path, "wb") as f:
                f.write(data)
            st.success(f"Saved on server: {save_path}")
    except Exception as e:
        st.warning(f"Could not save on server: {e}")

    # Download
    st.download_button(
        "⬇️ Download XLSX",
        data=data,
        file_name=os.path.basename(save_path) or "resume_ranking.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# Footer branding
st.markdown("---")
st.caption("© 🍵 Matchya — Hire faster")
