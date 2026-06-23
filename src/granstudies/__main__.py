"""CLI di granstudies: orchestrazione della pipeline a stadi.

    granstudies sweep    STUDY      genera le varianti YAML
    granstudies render   STUDY      renderizza audio + partitura
    granstudies describe STUDY      calcola descrittori, aggiorna results.yml
    granstudies matrix   STUDY      costruisce kinship.json
    granstudies compose  STUDY      genera final.yml dal percorso/grafo
    granstudies render-final STUDY  renderizza il brano finale

STUDY e' il nome della cartella sotto ``studies/`` (es. study01_grain_density).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

import yaml

from .engine_bridge import REPO_ROOT


# --- layout dei path -------------------------------------------------------

def study_dir(study: str) -> str:
    return os.path.join(REPO_ROOT, "studies", study)


def gen_dir(study: str) -> str:
    return os.path.join(REPO_ROOT, "generated", study)


def samples_dir(spec_samples: str | None) -> str:
    if spec_samples:
        return spec_samples if os.path.isabs(spec_samples) else os.path.join(REPO_ROOT, spec_samples)
    return os.path.join(REPO_ROOT, "samples")


def _load_spec(study: str):
    from .study_spec import load_study_spec

    return load_study_spec(os.path.join(study_dir(study), "study.yml"))


# --- comandi ---------------------------------------------------------------

def cmd_sweep(study: str) -> int:
    from .render import write_variants

    spec = _load_spec(study)
    out = os.path.join(gen_dir(study), "variants")
    written = write_variants(spec, out)
    print(f"[sweep] {len(written)} varianti scritte in {out}")
    return 0


def cmd_render(study: str, no_score: bool) -> int:
    from .render import render_variants

    spec = _load_spec(study)
    g = gen_dir(study)
    variant_dir = os.path.join(g, "variants")
    if not os.path.isdir(variant_dir):
        print(f"[render] nessuna variante: esegui prima 'sweep {study}'.", file=sys.stderr)
        return 1
    manifest = render_variants(
        variant_dir=variant_dir,
        audio_dir=os.path.join(g, "audio"),
        score_dir=None if no_score else os.path.join(g, "score"),
        samples_dir=samples_dir(spec.samples_dir),
    )
    print(f"[render] {len(manifest)} varianti renderizzate in {g}")
    return 0


def cmd_describe(study: str) -> int:
    from .curation import update_results_file
    from .sweep import generate_variants

    spec = _load_spec(study)
    g = gen_dir(study)
    audio_dir = os.path.join(g, "audio")
    if not os.path.isdir(audio_dir):
        print(f"[describe] nessun audio: esegui prima 'render {study}'.", file=sys.stderr)
        return 1
    params_by_name = {
        v.name: v.overrides(spec) for v in generate_variants(spec)
    }
    results_path = os.path.join(g, "results.yml")
    merged = update_results_file(results_path, audio_dir, params_by_name=params_by_name)
    print(f"[describe] {len(merged)} entry in {results_path}")
    return 0


def cmd_matrix(study: str, threshold: float) -> int:
    from .states import load_states
    from .kinship import kinship_matrix, adjacency, Weights

    states = load_states(os.path.join(study_dir(study), "states.yml"))
    kin = kinship_matrix(states, Weights())
    adj = adjacency(states, kin, threshold)
    g = gen_dir(study)
    os.makedirs(g, exist_ok=True)
    out = os.path.join(g, "kinship.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"threshold": threshold, **kin, "adjacency": adj}, fh, indent=2, ensure_ascii=False)
    print(f"[matrix] kinship di {len(states)} stati -> {out}")
    return 0


def _build_steps(study: str, comp: Dict[str, Any], states):
    from .kinship import kinship_matrix, adjacency, Weights
    from .walk import random_walk, authored_path

    mode = comp.get("mode", "walk")
    if mode == "path":
        return authored_path(states, comp["path"])
    threshold = float(comp.get("threshold", 0.5))
    kin = kinship_matrix(states, Weights())
    adj = adjacency(states, kin, threshold)
    return random_walk(
        states,
        adj,
        start=comp["start"],
        steps=int(comp.get("steps", len(states))),
        seed=int(comp.get("seed", 0)),
    )


def cmd_compose(study: str, seed: int | None, steps: int | None, start: str | None) -> int:
    from .states import load_states
    from .compose import compose_document

    spec = _load_spec(study)
    states = load_states(os.path.join(study_dir(study), "states.yml"))

    comp_path = os.path.join(study_dir(study), "composition.yml")
    if os.path.exists(comp_path):
        with open(comp_path, "r", encoding="utf-8") as fh:
            comp = yaml.safe_load(fh) or {}
    else:
        comp = {"mode": "walk"}
    # gli argomenti CLI hanno la precedenza
    if seed is not None:
        comp["seed"] = seed
    if steps is not None:
        comp["steps"] = steps
    if start is not None:
        comp["start"] = start
    if comp.get("mode", "walk") == "walk" and "start" not in comp:
        comp["start"] = states[0].id

    step_list = _build_steps(study, comp, states)
    doc = compose_document(
        step_list, states, spec.base, title=f"{study} :: composition", seed=spec.seed
    )
    g = gen_dir(study)
    os.makedirs(g, exist_ok=True)
    out = os.path.join(g, "final.yml")
    with open(out, "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)
    print(f"[compose] percorso di {len(step_list)} tappe -> {out}")
    return 0


def cmd_render_final(study: str) -> int:
    from . import engine_bridge

    spec = _load_spec(study)
    g = gen_dir(study)
    final_yaml = os.path.join(g, "final.yml")
    if not os.path.exists(final_yaml):
        print(f"[render-final] manca final.yml: esegui prima 'compose {study}'.", file=sys.stderr)
        return 1
    audio = os.path.join(g, "final.aif")
    sdir = samples_dir(spec.samples_dir)
    engine_bridge.render(final_yaml, audio, samples_dir=sdir)
    engine_bridge.score_pdf(final_yaml, os.path.join(g, "final.pdf"), samples_dir=sdir)
    print(f"[render-final] {audio}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="granstudies", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("sweep", help="genera le varianti YAML")
    sp.add_argument("study")

    rp = sub.add_parser("render", help="renderizza audio + partitura")
    rp.add_argument("study")
    rp.add_argument("--no-score", action="store_true", help="salta i PDF di partitura")

    dp = sub.add_parser("describe", help="descrittori + results.yml")
    dp.add_argument("study")

    mp = sub.add_parser("matrix", help="matrice di parentela")
    mp.add_argument("study")
    mp.add_argument("--threshold", type=float, default=0.5)

    cp = sub.add_parser("compose", help="genera final.yml")
    cp.add_argument("study")
    cp.add_argument("--seed", type=int, default=None)
    cp.add_argument("--steps", type=int, default=None)
    cp.add_argument("--start", type=str, default=None)

    fp = sub.add_parser("render-final", help="renderizza il brano finale")
    fp.add_argument("study")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "sweep":
        return cmd_sweep(args.study)
    if args.command == "render":
        return cmd_render(args.study, args.no_score)
    if args.command == "describe":
        return cmd_describe(args.study)
    if args.command == "matrix":
        return cmd_matrix(args.study, args.threshold)
    if args.command == "compose":
        return cmd_compose(args.study, args.seed, args.steps, args.start)
    if args.command == "render-final":
        return cmd_render_final(args.study)
    return 1


if __name__ == "__main__":
    sys.exit(main())
