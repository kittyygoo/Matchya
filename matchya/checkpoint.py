from __future__ import annotations

import json
import os
from typing import Dict


def load_checkpoint(cp_path: str) -> Dict[str, Dict]:
    if not cp_path or not os.path.exists(cp_path):
        return {}
    cache: Dict[str, Dict] = {}
    with open(cp_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                cache[obj["hash"]] = obj["data"]
            except Exception:
                continue
    return cache


def append_checkpoint(cp_path: str, file_hash: str, data: Dict):
    with open(cp_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"hash": file_hash, "data": data}, ensure_ascii=False) + "\n")


def reset_checkpoint(cp_path: str):
    if cp_path and os.path.exists(cp_path):
        os.remove(cp_path)
