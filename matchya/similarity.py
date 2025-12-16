from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd
from rapidfuzz import fuzz

from .text_utils import normalize_for_sim


def max_similarities(texts: List[str], names: List[str]) -> Tuple[List[float], List[str], pd.DataFrame]:
    n = len(texts)
    norm = [normalize_for_sim(t) for t in texts]
    max_sim = [0.0] * n
    near_name = [""] * n
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            s = float(fuzz.token_set_ratio(norm[i], norm[j]))
            pairs.append((names[i], names[j], s))
            if s > max_sim[i]:
                max_sim[i] = s
                near_name[i] = names[j]
            if s > max_sim[j]:
                max_sim[j] = s
                near_name[j] = names[i]
    pairs_df = pd.DataFrame(pairs, columns=["FileA", "FileB", "Similarity"]).sort_values("Similarity", ascending=False)
    return max_sim, near_name, pairs_df
