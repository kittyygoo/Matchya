from __future__ import annotations

import re
from typing import Dict, List

import numpy as np
import pandas as pd

from .models import Criterion


def compute_scores_table(base_rows: List[Dict], criteria: List[Criterion], dup_threshold: int) -> pd.DataFrame:
    df = pd.DataFrame(base_rows)

    crit_cols = [f"{c.name} (0-5)" for c in criteria if f"{c.name} (0-5)" in df.columns]
    if crit_cols:
        df["Coverage"] = (df[crit_cols] > 0.0).sum(axis=1) / max(1, len(crit_cols))
        pct = df[crit_cols].rank(pct=True)
        pct.columns = [c.replace(" (0-5)", "::Pct") for c in pct.columns]
        df = pd.concat([df, pct], axis=1)
    else:
        df["Coverage"] = 0.0

    weights = {c.name: float(c.weight) for c in criteria}
    sumw = sum(weights.values()) or 1.0

    w_sum = np.zeros(len(df))
    for c in criteria:
        pcol = f"{c.name}::Pct"
        if pcol in df:
            w_sum += weights[c.name] * df[pcol].fillna(0).to_numpy()

    df["CompositeScore"] = 100.0 * (0.75 * (w_sum / sumw) + 0.25 * df["Coverage"])

    def bucket(x):
        return "A" if x >= 80 else ("B" if x >= 60 else "C")

    df["PriorityBucket"] = df["CompositeScore"].apply(bucket)

    def clamp_local(s: str, n: int) -> str:
        s = re.sub(r"\s+", " ", (s or "").strip())
        return (s[: n - 1] + "…") if len(s) > n else s

    def calc_comment(row):
        fio = clamp_local(row.get("FullName", ""), 80)
        spec = clamp_local(row.get("Specialization", ""), 100)
        cov = row.get("Coverage", 0.0)

        pct_cols = [(k.replace("::Pct", ""), k) for k in df.columns if k.endswith("::Pct")]
        top = sorted([(crit, float(row[pcol])) for crit, pcol in pct_cols], key=lambda x: x[1], reverse=True)[:3]

        reason = row.get("_Reasoning", {}) or {}
        strengths_parts, examples_parts = [], []
        for crit, _ in top:
            score_val = row.get(f"{crit} (0-5)", 0.0)
            rtxt = clamp_local(str(reason.get(crit, "")), 280)
            if rtxt:
                examples_parts.append(f"{crit} ({score_val:.1f}): {rtxt}")
            strengths_parts.append(f"{crit} ({score_val:.1f})")

        gaps = []
        for c in [c.name for c in criteria]:
            sc = float(row.get(f"{c} (0-5)", 0.0))
            if sc <= 1.5:
                gap_reason = clamp_local(str(reason.get(c, "")), 160)
                gaps.append(f"{c} ({sc:.1f})" + (f": {gap_reason}" if gap_reason else ""))

        risks = []
        if float(row.get("SimilarityMax", 0)) >= dup_threshold:
            risks.append("possible duplicate by similarity")
        if not row.get("Email"):
            risks.append("missing email")
        if not row.get("Phone"):
            risks.append("missing phone")

        strengths_txt = ", ".join(strengths_parts) if strengths_parts else "no standout strengths"
        examples_txt = " | ".join(examples_parts) if examples_parts else ""
        gaps_txt = "; ".join(gaps) if gaps else "—"

        return (
            f"{('Candidate: ' + fio + '. ') if fio else ''}"
            f"{('Specialization: ' + spec + '. ') if spec else ''}"
            f"Total {row['CompositeScore']:.0f}/100. Coverage {cov:.0%}. "
            f"Strengths: {strengths_txt}. "
            f"{('Examples: ' + examples_txt + '. ') if examples_txt else ''}"
            f"Gaps: {gaps_txt}."
            f"{(' Risks: ' + ', '.join(risks) + '.') if risks else ''}"
        )

    df["CalcComment"] = df.apply(calc_comment, axis=1)
    return df
