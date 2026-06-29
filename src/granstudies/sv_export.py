"""Genera CSV di envelope per Sonic Visualiser dai YAML di variante generati.

Ogni parametro con envelope lineare (type: linear + points) diventa un CSV
``time_seconds,valore`` importabile in SV come Time Values layer.
"""
from __future__ import annotations

import csv
import os
from typing import Any, List, Tuple


def _find_envelopes(obj: Any, prefix: str = "") -> List[Tuple[str, List]]:
    """Walk ricorsivo: restituisce [(path_dotted, points)] per ogni envelope lineare."""
    if isinstance(obj, dict):
        if obj.get("type") == "linear" and "points" in obj:
            return [(prefix.lstrip("."), obj["points"])]
        results = []
        for k, v in obj.items():
            results.extend(_find_envelopes(v, f"{prefix}.{k}"))
        return results
    return []


def variant_to_csvs(variant_yaml_path: str, out_dir: str) -> List[str]:
    """Legge un variant YAML, scrive un CSV per ogni parametro envelope.

    Returns lista dei CSV scritti.
    """
    import yaml

    with open(variant_yaml_path, "r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    duration = float(doc.get("duration", 1.0))
    streams = doc.get("streams", [])
    if not streams:
        return []

    envelopes = _find_envelopes(streams[0])
    os.makedirs(out_dir, exist_ok=True)

    written = []
    for path, points in envelopes:
        fpath = os.path.join(out_dir, path.replace(".", "_") + ".csv")
        with open(fpath, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["time", path])
            for t_norm, value in points:
                w.writerow([round(t_norm * duration, 6), value])
        written.append(fpath)
    return written
