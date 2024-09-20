from funktools import Template, TemplateFunction, TemplatedClass


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


@Template
def funk():
    return "empty"


@Template[Foo]
def funk():
    return "Foo"


@Template[Bar]
def funk():
    return "Bar"


@Template[Baz]
def funk(baz: Baz):
    return "Baz"


@Template[Foo, Bar, Baz]
def funk(baz: Baz):
    return "Foo, Bar, Baz"


@Template
def funk(val: int):
    return "int"


@Template
def funk(val: int, val2: float):
    return "int, float"

@Template
def funk(a: int, b: int):
    return "int, int"

@Template
def funk(a: float, *, b: float):
    return "float, float"

@Template
def funk(*, a: str, b: str):
    return "str, str"

@Template
def funk(*, a: bool, b: bool = False):
    return "bool, bool"

@Template
def funk(b, a: bool):
    return "Any, bool"

@Template
def funk(a: bool, b):
    return "bool, Any"

@Template
def funk(a: str, b: int, c: float = 3.0):
    return "str, int, float"


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
    assert funk(1, 1) == "int, int"
    assert funk(1.0, b=1.0) == "float, float"
    assert funk(a="1", b="1") == "str, str"
    assert funk(a=True) == "bool, bool"
    assert funk(a=True, b=True) == "bool, bool"
    assert funk(True, a=True) == "Any, bool"
    assert funk(True, b=Foo()) == "bool, Any"
    assert funk("", 1) == "str, int, float"


@Template
def funky(a: int, b) -> str:
    return f"funky({a}: int, {b})"


@Template
def funky(a: int, c: float) -> str:
    return f"funky({a}: int, {c}: float)"


@Template
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


def test_types() -> None:
    assert isinstance(funky, TemplateFunction)
    assert type(funk) == type(funky)
    assert "funk" in str(funk)
    assert "funky" in str(funky)


def test_call_annotations() -> None:
    import typing

    type_hints = typing.get_type_hints(funk)
    assert type_hints["baz"] == None | Baz
    assert type_hints["val"] == None | int
    assert type_hints["fee"] == None | Fee


def test_get_annotations() -> None:
    import typing

    key_types = typing.get_type_hints(funk.get)["key"]
    assert key_types | tuple[int, float] == key_types
    assert key_types | int == key_types
    assert key_types | Foo == key_types
    assert key_types | Bar == key_types
    assert key_types | Qux == key_types
    assert key_types | Fee == key_types
    assert key_types | tuple[Foo, Bar, Baz] == key_types


def test_method_decorator() -> None:
    @TemplatedClass
    class Foo:
        def __init__(self, v):
            self._val = v

        @Template
        def val(self):
            return self._val

        @Template
        def val(self, v):
            self._val = v

        @Template
        def bar(self):
            return 1

        @Template
        def bar(self, a: int):
            return 10 + a

        @Template
        def bar(self, a: float):
            return 20.0 + a

        @Template
        def bar(self, a: str):
            return "30" + a

        @Template
        def bar(self, a: int, b: int):
            return 40 + a + b

        @Template
        def bar(self, a: float, *, b: float):
            return 50.0 + a + b

        @Template
        def bar(self, *, a: str, b: str):
            return "60" + a + b

        @Template
        def bar(self, *, a: bool, b: bool = False):
            return 70 + a + b

    uut = Foo(4)
    assert uut.val() == 4
    uut.val(5)
    assert uut.val() == 5

    assert uut.bar() == 1
    assert uut.bar(1) == 10 + 1
    assert uut.bar(1.0) == 20 + 1.0
    assert uut.bar("1") == "30" + "1"
    assert uut.bar(1, 1) == 40 + 1 + 1
    assert uut.bar(1.0, b=1.0) == 50 + 1.0 + 1.0
    assert uut.bar(a="1", b="1") == "60" + "1" + "1"
    assert uut.bar(a=True, b=True) == 70 + True + True
    assert uut.bar(a=True) == 70 + True
