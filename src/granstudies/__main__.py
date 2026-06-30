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


def _load_specs(study: str, stream: str | None = None) -> list:
    from .study_spec import resolve_streams

    path = os.path.join(study_dir(study), "study.yml")
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    sid = data.get("study_id") or study
    specs = resolve_streams(data, sid)
    if stream:
        specs = [s for s in specs if s.stream_id == stream]
        if not specs:
            print(f"[sweep] stream '{stream}' non trovata in {study}.", file=sys.stderr)
    return specs


# --- comandi ---------------------------------------------------------------

def cmd_sweep(study: str, stream: str | None = None) -> int:
    from .render import write_variants

    specs = _load_specs(study, stream)
    if not specs:
        return 1
    out = os.path.join(gen_dir(study), "variants")
    total = 0
    for spec in specs:
        written = write_variants(spec, out)
        total += len(written)
        label = f" [{spec.stream_id}]" if spec.stream_id else ""
        n_disc = sum(1 for p in written if (os.sep + "discrete" + os.sep) in p)
        n_env = sum(1 for p in written if (os.sep + "envelope" + os.sep) in p)
        if n_disc:
            print(f"[sweep]{label} {n_disc} varianti discrete")
        if n_env:
            print(f"[sweep]{label} {n_env} varianti envelope")
        if not written:
            print(f"[sweep]{label} nessuna variante generata (mode={spec.mode})")
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
    from .sweep import generate_discrete_variants

    spec = _load_spec(study)
    g = gen_dir(study)
    # La curation lavora solo sulle varianti discrete: l'audio sta in
    # ``audio/discrete/`` (layout di ``write_variants``); fallback flat per
    # backward compat con output precedenti.
    audio_dir = os.path.join(g, "audio", "discrete")
    if not os.path.isdir(audio_dir):
        audio_dir = os.path.join(g, "audio")
    if not os.path.isdir(audio_dir):
        print(f"[describe] nessun audio: esegui prima 'render {study}'.", file=sys.stderr)
        return 1
    params_by_name = {
        v.name: v.overrides(spec) for v in generate_discrete_variants(spec)
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


def cmd_sv(study: str, layout: str, markers: bool = True, stream: str | None = None,
           markers_scope: str = "all") -> int:
    from .sv_export import variant_to_sv

    specs = _load_specs(study, stream)
    if not specs:
        return 1
    g = gen_dir(study)
    total: list = []
    for spec in specs:
        sub = spec.stream_id or ""
        variant_dir = os.path.join(g, "variants", "envelope", sub) if sub else os.path.join(g, "variants", "envelope")
        audio_dir = os.path.join(g, "audio", "envelope", sub) if sub else os.path.join(g, "audio", "envelope")
        sv_dir = os.path.join(g, "sv", "envelope", sub) if sub else os.path.join(g, "sv", "envelope")

        if not os.path.isdir(variant_dir):
            print(f"[sv] [{sub or 'default'}] nessuna variante envelope: esegui prima 'sweep {study}'.", file=sys.stderr)
            continue
        if not os.path.isdir(audio_dir):
            print(f"[sv] [{sub or 'default'}] nessun audio envelope: esegui prima 'render {study}'.", file=sys.stderr)
            continue

        for fname in sorted(os.listdir(variant_dir)):
            if not fname.endswith(".yml"):
                continue
            variant_name = fname[:-4]
            # Il basename include il nome dello stream per distinguere i file in SV.
            basename = f"{sub}_{variant_name}" if sub else variant_name
            audio = os.path.join(audio_dir, basename + ".aif")
            if not os.path.exists(audio):
                print(f"[sv] {basename}: audio mancante, salto.", file=sys.stderr)
                continue
            suffix = f"_{layout}" if layout == "single" else ""
            out = os.path.join(sv_dir, basename + suffix + ".sv")
            variant_to_sv(os.path.join(variant_dir, fname), audio, out,
                          layout=layout, markers=markers, markers_scope=markers_scope)
            total.append(out)
            print(f"[sv] {out}")

    print(f"[sv] {len(total)} sessioni totali")
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
    print(f"[render-final] {audio}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="granstudies", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("sweep", help="genera le varianti YAML")
    sp.add_argument("study")
    sp.add_argument("--stream", default=None, help="genera solo questa stream (default: tutte)")

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

    svp = sub.add_parser("sv", help="genera sessioni .sv per Sonic Visualiser")
    svp.add_argument("study")
    svp.add_argument("--layout", choices=["multi", "single"], default="multi",
                     help="multi: un pannello per parametro (default); single: tutti in un pannello")
    svp.add_argument("--no-markers", action="store_true",
                     help="non emette i marker di inizio plateau (confini degli stati)")
    svp.add_argument("--markers-scope", choices=["all", "waveform"], default="waveform",
                     help="waveform: marker solo nel pane della forma d'onda (default); all: marker in ogni pane")
    svp.add_argument("--stream", default=None, help="genera sv solo per questa stream (default: tutte)")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "sweep":
        return cmd_sweep(args.study, args.stream)
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
    if args.command == "sv":
        return cmd_sv(args.study, args.layout, markers=not args.no_markers, stream=args.stream,
                      markers_scope=args.markers_scope)
    return 1


if __name__ == "__main__":
    sys.exit(main())
