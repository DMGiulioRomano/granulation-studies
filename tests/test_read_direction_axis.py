"""Un asse su ``grain.read_direction``: dominio discreto, non intervallo (#68).

La chiave ha due stati, ``-1`` e ``+1`` (PGE #207). Il registry le da' bounds
``(-1, 1)``, che ne sono l'inviluppo e non il dominio: ammettono ``0.3`` e
``0``, che l'engine rifiuta al parse invece di arrotondarli — ``0.3`` non e' un
verso, ``0`` non ha segno. Da qui tre regole per l'asse, tutte al parse dello
``study.yml`` invece che al render:

- i valori (e il baseline) stanno nell'insieme dell'engine;
- si enumerano con ``values``: ``ramp`` e la banda generano anche fra un
  elemento e l'altro;
- ``interpolation: step``, l'unica che l'engine accetta sulla chiave.

L'oracolo dei documenti generati e' il validatore dell'engine stesso
(``normalize_read_direction``): non un'asserzione sulla forma, la risposta di
chi poi li legge.
"""
import pytest

from granstudies import bounds
from granstudies.envelope_sweep import generate_envelope_variants
from granstudies.errors import SpecError
from granstudies.engine_bridge import _ensure_engine_on_path
from granstudies.stack import build_stack_stream
from granstudies.study_spec import parse_study_spec

AX = "grain.read_direction"


def _study(axis, interpolation="step", mode="discrete", stack=None, name=AX):
    d = {
        "study_id": "s",
        "base": {"onset": 0, "duration": 8, "sample": "x.wav", "density": 20},
        "axes": {"interpolation": interpolation, name: axis},
        "sweep": {"mode": mode, "orders": [1]},
    }
    if stack is not None:
        d["stack"] = stack
    return d


def _err(d):
    with pytest.raises(SpecError) as exc:
        parse_study_spec(d, "s")
    return exc.value


def _engine_normalize(raw):
    _ensure_engine_on_path()
    from pge.parameters.read_direction import normalize_read_direction

    return normalize_read_direction(raw)


# --- il dominio viene dall'engine -------------------------------------------

def test_discrete_domain_e_l_insieme_dell_engine():
    # Nessuna tabella copiata: l'insieme e' ``READ_DIRECTION_VALUES``.
    _ensure_engine_on_path()
    from pge.parameters.read_direction import READ_DIRECTION_VALUES

    dom = bounds.discrete_domain(AX)
    assert dom == frozenset(READ_DIRECTION_VALUES)
    assert dom == {-1, 1}
    for p in ("density", "grain.envelope", "grain.reverse", "non.esiste"):
        assert bounds.discrete_domain(p) is None, p
    # numeri, non nomi: il path non e' categoriale
    assert bounds.categorical_domain(AX) is None


def test_i_bounds_sono_l_inviluppo_dell_insieme():
    # Premessa della regola in ``_validate``: dopo l'insieme il confronto bounds
    # non ha piu' niente da dire, perche' ogni elemento sta nell'inviluppo. Se
    # l'engine allargasse l'insieme oltre i bounds, questo parlerebbe.
    for v in bounds.discrete_domain(AX):
        assert bounds.violation(AX, v) is None, v
        assert bounds.clamp(AX, v) == v, v


# --- i valori stanno nell'insieme --------------------------------------------

def test_i_due_versi_passano():
    spec = parse_study_spec(_study({"baseline": 1, "values": [-1, 1]}), "s")
    ax = spec.axis(AX)
    assert ax.values == [-1, 1]
    assert ax.baseline == 1


def test_la_grafia_float_dei_due_versi_passa():
    spec = parse_study_spec(_study({"baseline": -1.0, "values": [-1.0, 1.0]}), "s")
    assert spec.axis(AX).values == [-1.0, 1.0]


@pytest.mark.parametrize("bad", [0, 0.3, -0.5, 2, -3])
def test_un_valore_fuori_dall_insieme_e_errore(bad):
    # 0.3, 0 e -0.5 stanno dentro i bounds (-1, 1): e' l'insieme a rifiutarli,
    # come fa l'engine. 2 e -3 sono fuori da entrambi, e l'errore resta uno.
    e = _err(_study({"baseline": 1, "values": [-1, bad]}))
    assert e.key == ("axes", AX, "values")
    assert repr(bad) in e.msg
    # l'insieme si nomina una volta sola: l'hint lo scrive come dominio
    assert e.hint.count("-1, 1") == 1


def test_il_baseline_fuori_dall_insieme_e_errore():
    # Il baseline e' il valore degli assi fermi: finisce nei file dove l'asse
    # non si muove, dove l'engine lo rifiuterebbe allo stesso modo.
    e = _err(_study({"baseline": 0.5, "values": [-1, 1]}))
    assert e.key == ("axes", AX, "baseline")
    assert "0.5" in e.msg


def test_true_non_e_uno():
    # ``True == 1`` in Python: senza la guardia sul non-numero passerebbe il
    # confronto con l'insieme. L'engine lo rifiuta.
    e = _err(_study({"baseline": 1, "values": [-1, True]}))
    assert e.key == ("axes", AX, "values")


def test_senza_baseline_serve_dichiararlo():
    # Chiave assente = modalita' auto: l'engine non ha un default da cui
    # partire, e l'asse lo pretende come per density.
    e = _err(_study({"values": [-1, 1]}))
    assert e.key == ("axes", AX)
    assert "baseline" in e.msg


def test_il_dominio_e_del_path_non_del_nome_dell_asse():
    axis = {"path": AX, "baseline": 1, "values": [-1, 1]}
    assert parse_study_spec(_study(axis, name="verso"), "s").axis("verso").values == [-1, 1]
    axis = {"path": AX, "baseline": 1, "values": [0]}
    assert _err(_study(axis, name="verso")).key == ("axes", "verso", "values")


# --- si enumera, non si genera -----------------------------------------------

@pytest.mark.parametrize(
    "gen",
    [
        {"ramp": {"start": -1, "stop": 1, "step": 0.5}},
        # anche una rampa che cade sull'insieme: la regola e' sul generatore,
        # e il rimedio (``values``) e' lo stesso
        {"ramp": {"start": -1, "stop": 1, "step": 2}},
        {"base": -1, "range": 2, "n": 3},
    ],
    ids=["ramp", "ramp-sull-insieme", "banda"],
)
def test_ramp_e_banda_sono_errore(gen):
    e = _err(_study({"baseline": 1, **gen}))
    assert e.key == ("axes", AX)
    assert "values" in e.hint
    assert "-1, 1" in e.hint


def test_la_banda_della_camminata_x_e_errore_sul_generatore():
    # Con la camminata-X 'base' la Y e' una banda senza n, campionata ai tempi
    # della X: produrrebbe valori continui fra -1 e 1. L'errore dice il
    # generatore, non la n-ownership.
    d = _study(
        {"baseline": 1, "base": -1, "range": 2},
        stack={AX: {"base": 2, "range": 1}},
    )
    e = _err(d)
    assert e.key == ("axes", AX)
    assert "values" in e.hint


def test_camminata_x_con_values_non_suggerisce_la_banda():
    # Con 'values' la camminata-X 'base' (che possiede n) non ha una Y da
    # campionare: il rimedio generico proporrebbe la banda, che qui e' vietata.
    d = _study(
        {"baseline": 1, "values": [-1, 1]},
        stack={AX: {"base": 2, "range": 1}},
    )
    e = _err(d)
    assert e.key == ("stack", AX)
    assert "banda" not in e.hint
    assert f"stack.{AX}" in e.hint


# --- step e' l'interpolazione ------------------------------------------------

@pytest.mark.parametrize("interp", ["linear", "cubic"])
def test_un_interpolazione_non_step_e_errore(interp):
    axis = {"baseline": 1, "values": [-1, 1], "interpolation": interp}
    e = _err(_study(axis))
    assert e.key == ("axes", AX, "interpolation")
    assert "step" in e.msg


def test_l_interpolazione_ereditata_nomina_axes_interpolation():
    e = _err(_study({"baseline": 1, "values": [-1, 1]}, interpolation="linear"))
    assert e.key == ("axes", "interpolation")


def test_senza_interpolazione_dichiarata_vale_il_default_linear():
    d = _study({"baseline": 1, "values": [-1, 1]})
    del d["axes"]["interpolation"]
    e = _err(d)
    assert e.key == ("axes", AX)
    assert "default linear" in e.msg


# --- cio' che si genera, l'engine lo accetta ---------------------------------

def test_lo_stack_genera_un_envelope_step_che_l_engine_accetta():
    d = _study({"baseline": 1, "values": [-1, 1, -1]}, stack={})
    spec = parse_study_spec(d, "s")
    stream = build_stack_stream(spec)
    raw = stream["grain"]["read_direction"]
    assert raw["type"] == "step"
    assert {p[1] for p in raw["points"]} <= {-1, 1}
    _engine_normalize(raw)  # non solleva


@pytest.mark.parametrize("other_interp", ["step", "linear"])
def test_l_envelope_sweep_genera_un_envelope_che_l_engine_accetta(other_interp):
    # Con un altro asse lineare nello stesso file la griglia resta a plateau e
    # l'asse step tiene un punto per plateau (layout C); tutti step, collassa.
    d = _study({"baseline": 1, "values": [-1, 1]}, mode="envelope")
    d["axes"]["density"] = {
        "baseline": 20, "values": [10, 30], "interpolation": other_interp,
    }
    d["sweep"]["orders"] = [2]
    spec = parse_study_spec(d, "s")
    (ev,) = generate_envelope_variants(spec)
    points = ev.overrides(spec)[AX]
    assert ev.envelope_types(spec)[AX] == "step"
    assert {p[1] for p in points} <= {-1, 1}
    _engine_normalize({"type": "step", "points": points})  # non solleva
