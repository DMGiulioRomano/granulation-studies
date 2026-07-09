import pytest

from granstudies.expr import eval_expr, is_expr_node, parse_expr_node


# --- scalari -----------------------------------------------------------------

def test_precedence_and_parens():
    assert eval_expr("2 + 3 * 4", {}) == 14
    assert eval_expr("(2 + 3) * 4", {}) == 20


def test_names_resolve_in_scope():
    assert eval_expr("a * (i + 1)", {"a": 50, "i": 3}) == 200


def test_unary_minus_and_pow():
    assert eval_expr("-a ** 2", {"a": 3}) == -9   # precedenza python: -(3**2)
    assert eval_expr("(-a) ** 2", {"a": 3}) == 9


def test_progress_fraction():
    assert eval_expr("i / (n - 1)", {"i": 2, "n": 5}) == 0.5


def test_no_free_names_empty_scope():
    assert eval_expr("1 + 2", {}) == 3


def test_result_rounded_9_decimals():
    assert eval_expr("1 / 3", {}) == round(1 / 3, 9)


# --- Env ⊙ scalare -----------------------------------------------------------

def test_env_breakpoints_times_scalar_scales_y_keeps_t():
    env = [[0, 1], [0.1583, 1.5]]
    assert eval_expr("env * 50", {"env": env}) == [[0, 50], [0.1583, 75]]


def test_env_plus_scalar_shifts_y():
    env = [[0, 0], [0.1583, 0.5]]
    assert eval_expr("env + 50", {"env": env}) == [[0, 50], [0.1583, 50.5]]


def test_env_shorthand_two_scalars():
    assert eval_expr("env * 2", {"env": [10, 20]}) == [20, 40]


def test_env_dict_form_preserves_type_and_curve():
    env = {"type": "linear", "points": [[0, 1], [1, 2]], "curve": 2}
    out = eval_expr("env * 10", {"env": env})
    assert out == {"type": "linear", "points": [[0, 10], [1, 20]], "curve": 2}


def test_scalar_minus_env_respects_order():
    env = [[0, 10], [1, 20]]
    assert eval_expr("100 - env", {"env": env}) == [[0, 90], [1, 80]]


def test_env_div_scalar():
    env = [[0, 10], [1, 20]]
    assert eval_expr("env / 2", {"env": env}) == [[0, 5], [1, 10]]


def test_unary_minus_on_env():
    assert eval_expr("-env", {"env": [[0, 1], [1, 2]]}) == [[0, -1], [1, -2]]


def test_env_result_does_not_alias_scope():
    env = [[0, 1], [1, 2]]
    out = eval_expr("env", {"env": env})
    assert out == env
    out[0][1] = 99
    assert env[0][1] == 1


def test_compound_env_expression():
    env = [[0, 1], [0.1583, 1.5]]
    out = eval_expr("env * a * (i + 1)", {"env": env, "a": 50, "i": 1})
    assert out == [[0, 100], [0.1583, 150]]


# --- operatori % e // ----------------------------------------------------------

def test_modulo_and_floordiv():
    assert eval_expr("10 % 3", {}) == 1
    assert eval_expr("7 // 2", {}) == 3
    assert eval_expr("-7 % 3", {}) == 2   # semantica Python: segno del divisore


def test_modulo_on_env_elementwise():
    env = [[0, 5], [1, 7]]
    assert eval_expr("env % 4", {"env": env}) == [[0, 1], [1, 3]]


def test_modulo_by_zero():
    with pytest.raises(ValueError, match="zero"):
        eval_expr("10 % 0", {})


# --- funzioni primitive e costanti ----------------------------------------------

def test_rounding_functions():
    assert eval_expr("floor(2.7)", {}) == 2
    assert eval_expr("ceil(2.1)", {}) == 3
    assert eval_expr("abs(0 - 3)", {}) == 3


def test_sqrt_exp_log():
    assert eval_expr("sqrt(9)", {}) == 3
    assert eval_expr("exp(0)", {}) == 1
    assert eval_expr("log(e)", {}) == 1
    assert eval_expr("log(8, 2)", {}) == 3


def test_trig_and_constants():
    import math

    assert eval_expr("sin(0)", {}) == 0
    assert eval_expr("cos(0)", {}) == 1
    assert eval_expr("tan(0)", {}) == 0
    assert eval_expr("atan(1)", {}) == round(math.pi / 4, 9)
    assert eval_expr("pi", {}) == round(math.pi, 9)
    assert eval_expr("cos(2 * pi)", {}) == 1


def test_scope_shadows_constants():
    assert eval_expr("pi", {"pi": 3}) == 3


def test_min_max_scalars():
    assert eval_expr("min(3, i)", {"i": 1}) == 1
    assert eval_expr("max(1, 2, 3)", {}) == 3


def test_nested_calls():
    assert eval_expr("floor(sqrt(10))", {}) == 3


def test_function_on_env_maps_y():
    env = [[0, 0], [1, 9]]
    assert eval_expr("sqrt(env)", {"env": env}) == [[0, 0], [1, 3]]


def test_min_clamps_env_y():
    env = [[0, 5], [1, 20]]
    assert eval_expr("min(env, 10)", {"env": env}) == [[0, 5], [1, 10]]


def test_max_on_env_shorthand():
    assert eval_expr("max(env, 0)", {"env": [-5, 5]}) == [0, 5]


def test_function_preserves_env_dict_form():
    env = {"type": "linear", "points": [[0, 1.7], [1, 2.2]], "curve": 2}
    out = eval_expr("floor(env)", {"env": env})
    assert out == {"type": "linear", "points": [[0, 1], [1, 2]], "curve": 2}


def test_unknown_function_lists_available():
    with pytest.raises(ValueError) as exc:
        eval_expr("foo(1)", {})
    assert "foo" in str(exc.value)
    assert "sin" in str(exc.value)


def test_wrong_arity_raises():
    with pytest.raises(ValueError, match="argoment"):
        eval_expr("sqrt(1, 2)", {})
    with pytest.raises(ValueError, match="argoment"):
        eval_expr("min(1)", {})


def test_keyword_args_rejected():
    with pytest.raises(ValueError, match="keyword"):
        eval_expr("log(8, base=2)", {})


def test_math_domain_error_is_clear():
    with pytest.raises(ValueError, match="dominio"):
        eval_expr("sqrt(0 - 1)", {})
    with pytest.raises(ValueError, match="dominio"):
        eval_expr("log(0)", {})


def test_call_with_two_envs_rejected():
    envs = {"e1": [[0, 1], [1, 2]], "e2": [[0, 3], [1, 4]]}
    with pytest.raises(ValueError, match="Env"):
        eval_expr("min(e1, e2)", envs)


def test_starred_args_rejected():
    with pytest.raises(ValueError):
        eval_expr("min(*e)", {"e": [[0, 1], [1, 2]]})


def test_complex_result_rejected():
    with pytest.raises(ValueError, match="compless"):
        eval_expr("(0 - 1) ** 0.5", {})


# --- errori ------------------------------------------------------------------

def test_unknown_name_lists_scope():
    with pytest.raises(ValueError) as exc:
        eval_expr("a * b", {"a": 1, "x": 2})
    assert "b" in str(exc.value)
    assert "a" in str(exc.value) and "x" in str(exc.value)


def test_env_times_env_rejected():
    envs = {"e1": [[0, 1], [1, 2]], "e2": [[0, 3], [1, 4]]}
    with pytest.raises(ValueError, match="Env"):
        eval_expr("e1 * e2", envs)


def test_call_on_non_name_rejected():
    with pytest.raises(ValueError):
        eval_expr("(1)(2)", {})


def test_subscript_rejected():
    with pytest.raises(ValueError):
        eval_expr("e[0]", {"e": [[0, 1], [1, 2]]})


def test_comparison_rejected():
    with pytest.raises(ValueError):
        eval_expr("1 < 2", {})


def test_bool_constant_rejected():
    with pytest.raises(ValueError):
        eval_expr("True", {})


def test_string_constant_rejected():
    with pytest.raises(ValueError):
        eval_expr("'x'", {})


def test_division_by_zero():
    with pytest.raises(ValueError, match="zero"):
        eval_expr("1 / 0", {})


def test_env_division_by_zero():
    with pytest.raises(ValueError, match="zero"):
        eval_expr("env / 0", {"env": [[0, 1], [1, 2]]})


def test_broken_syntax():
    with pytest.raises(ValueError):
        eval_expr("a *", {"a": 1})


def test_unrecognized_scope_form():
    with pytest.raises(ValueError, match="forma"):
        eval_expr("v * 2", {"v": {"ramp": {"start": 0, "step": 1}}})


def test_bool_in_scope_rejected():
    with pytest.raises(ValueError):
        eval_expr("v * 2", {"v": True})


# --- nodo-expr: riconoscimento e validazione ----------------------------------

def test_is_expr_node():
    assert is_expr_node({"expr": "a * 2", "let": {"a": 1}})
    assert is_expr_node({"expr": "1 + 1"})
    assert not is_expr_node({"ramp": {"start": 0}})
    assert not is_expr_node([[0, 1]])
    assert not is_expr_node(3)


def test_parse_expr_node_returns_text_and_let():
    text, let = parse_expr_node({"expr": "a * 2", "let": {"a": 1}})
    assert text == "a * 2"
    assert let == {"a": 1}


def test_parse_expr_node_let_optional():
    assert parse_expr_node({"expr": "1 + 1"}) == ("1 + 1", {})


def test_parse_expr_node_extra_keys_raise():
    with pytest.raises(ValueError, match="seed"):
        parse_expr_node({"expr": "1", "let": {}, "seed": 3})


def test_parse_expr_node_expr_not_string_raises():
    with pytest.raises(ValueError):
        parse_expr_node({"expr": 42})


def test_parse_expr_node_let_not_dict_raises():
    with pytest.raises(ValueError):
        parse_expr_node({"expr": "1", "let": [1, 2]})


def test_parse_expr_node_generator_in_let_raises():
    node = {"expr": "v * 2", "let": {"v": {"ramp": {"start": 0, "step": 1}}}}
    with pytest.raises(ValueError, match="statiche"):
        parse_expr_node(node)
