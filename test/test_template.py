from funktools import template


class Foo:
    pass


class Bar:
    pass


class Baz:
    pass


class Qux:
    pass


class Fee:
    pass


@template
def funk():
    return "empty"


@template[Foo]
def funk():
    return "Foo"


@template[Bar]
def funk():
    return "Bar"


@template[Baz]
def funk(baz: Baz):
    return "Baz"


@template[Foo, Bar, Baz]
def funk(baz: Baz):
    return "Foo, Bar, Baz"


@template
def funk(val: int):
    return "int"


def foo_qux():
    return "Qux"


funk[Qux] = foo_qux


def foo_fee(fee: Fee):
    return "Fee"


funk.add(foo_fee)


def test_typed_calls() -> None:
    assert funk() == "empty"
    assert funk[()]() == "empty"
    assert funk[Foo]() == "Foo"
    assert funk[Bar]() == "Bar"
    assert funk[Baz](Baz()) == "Baz"
    assert funk(Baz()) == "Baz"
    assert funk[Foo, Bar, Baz](Baz()) == "Foo, Bar, Baz"
    assert funk[int](31) == "int"
    assert funk(42) == "int"
    assert funk[Qux]() == "Qux"
    assert funk[Fee](Fee()) == "Fee"
    assert funk(Fee()) == "Fee"


@template
def funky(a: int, b) -> str:
    return f"funky({a}: int, {b})"


@template
def funky(a: int, c: float) -> str:
    return f"funky({a}: int, {c}: float)"


@template
def funky(a: int, b: float, *, c: str, d: tuple = (1,)) -> str:
    return f"funky({a}: int, {b}: float, *, {c}: str, {d}: tuple)"


def test_arg_calls() -> None:
    assert funky(1, 2.3) == "funky(1: int, 2.3)"
    assert funky(1, b=2.3) == "funky(1: int, 2.3)"
    assert funky(a=1, b=2.3) == "funky(1: int, 2.3)"
    assert funky(b=2.3, a=1) == "funky(1: int, 2.3)"

    assert funky(1, c=3.4) == "funky(1: int, 3.4: float)"
    assert funky(a=1, c=3.4) == "funky(1: int, 3.4: float)"
    assert funky(c=3.4, a=1) == "funky(1: int, 3.4: float)"

    assert (
        funky(1, 2.3, d=(1, 2), c="abc")
        == "funky(1: int, 2.3: float, *, abc: str, (1, 2): tuple)"
    )
    assert (
        funky(a=1, b=2.3, c="abc")
        == "funky(1: int, 2.3: float, *, abc: str, (1,): tuple)"
    )
