from funktools import template


class Foo: pass
class Bar: pass
class Baz: pass
class Qux: pass
class Fee: pass

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

def test_calls() -> None:
    assert funk() == "empty"
    assert funk[()]() == "empty"
    assert funk[Foo]() == "Foo"
    assert funk[Bar]() == "Bar"
    assert funk[Baz](Baz()) == "Baz"
    assert funk(Baz()) == "Baz"
    # TODO(lpe): Should this one eventually allow
    # funk[Foo, Bar](Baz()) as an equivalent call?
    assert funk[Foo, Bar, Baz](Baz()) == "Foo, Bar, Baz"
    assert funk[int](31) == "int"
    assert funk(42) == "int"
    assert funk[Qux]() == "Qux"
    assert funk[Fee](Fee()) == "Fee"
    assert funk(Fee()) == "Fee"

