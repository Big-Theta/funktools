import annotated_types
import dataclasses
import enum
import logging
import shlex
import types
import typing

import pytest

import funktools


class FooEnum(enum.Enum):
    a = 'a'
    b = 'b'
    c = 'c'


class FooTuple(tuple):

    def __eq__(self, other) -> bool:
        return super().__eq__(other) and isinstance(other, type(self))


@dataclasses.dataclass(frozen=True)
class Arg[T]:
    arg: str = ...
    t: type[T] = ...
    default: T = ...
    expect: T = ...


args = [*map(lambda _args: Arg(*_args), [
    ('42', int, 0, 42),
    ('42', str, '0', '42'),
    ('3.14', float, 0.0, 3.14),
    ('True', bool, False, True),
    ('True', str, 'False', 'True'),
    ('False', bool, True, False),
    ('Hi!', str, 'Bye!', 'Hi!'),
    ('None', None, None, None),
    ('None', types.NoneType, None, None),
    ('"()"', tuple[()], (), ()),
    ('"()"', typing.Tuple[()], (), ()),
    ('"(1,)"', tuple[int], (0,), (1,)),
    ('"[1, 2, 3, 4]"', list[int], [], [1, 2, 3, 4]),
    ('"[1, 2, 3, 4]"', typing.List[int], [], [1, 2, 3, 4]),
    ('"(3.14, \'Hi!\', \'Bye!\')"', tuple[float, str, ...], (0.0, 'Meh!'), (3.14, 'Hi!', 'Bye!')),
    ('42', int | float | bool | str | None, 0, 42),
    ('3.14', int | float | bool | str | None, 0.0, 3.14),
    ('True', int | float | bool | str | None, False, True),
    ('False', int | float | bool | str | None, True, False),
    ('"\'Hi!\'"', int | float | bool | str | None, 'Bye!', 'Hi!'),
    ("None", int | float | bool | str | None, 42, None),
    ("42", typing.Optional[int], None, 42),
    ("None", typing.Optional[int], 42, None),
    ('"{True: {4.0: {42: \'yes!\'}}}"', dict[bool, dict[float, dict[int, str]]], {}, {True: {4.0: {42: 'yes!'}}}),
    ('"{1, 2, 3, 4}"', frozenset[int], frozenset(), frozenset({1, 2, 3, 4})),
    ('"{1, 2, 3, 4}"', set[int], set(), {1, 2, 3, 4}),
    ('b', FooEnum, FooEnum.a, FooEnum.b),
    ('\'(\"hi!\", \"bye!\")\'', FooTuple[str, ...], FooTuple(('Meh!',)), FooTuple(('hi!', 'bye!'))),
    ('42', typing.Annotated[int, 'foo annotation'], 0, 42),
])]


@pytest.mark.parametrize('arg', args)
def test_parses_positional_only(arg) -> None:

    @funktools.CLI()
    def entrypoint(foo: arg.t, /) -> dict[str, arg.t]:
        return locals()

    assert funktools.CLI().run(entrypoint, shlex.split(arg.arg)) == {'foo': arg.expect}


@pytest.mark.parametrize('arg', args)
def test_parses_positional_only_with_default(arg) -> None:

    @funktools.CLI()
    def entrypoint(foo: arg.t = arg.default, /) -> dict[str, arg.t]:
        return locals()

    assert funktools.CLI().run(entrypoint, []) == {'foo': arg.default}
    assert funktools.CLI().run(entrypoint, shlex.split(arg.arg)) == {'foo': arg.expect}


@pytest.mark.parametrize('arg', args)
def test_parses_positional_or_keyword(arg) -> None:

    @funktools.CLI()
    def entrypoint(foo: arg.t) -> dict[str, arg.t]:
        return locals()

    with pytest.raises(SystemExit):
        funktools.CLI().run(entrypoint, [])
    assert funktools.CLI().run(entrypoint, shlex.split(arg.arg)) == {'foo': arg.expect}


@pytest.mark.parametrize('arg', args)
def test_parses_positional_or_keyword_with_default(arg) -> None:

    @funktools.CLI()
    def entrypoint(foo: arg.t = arg.default) -> dict[str, arg.t]:
        return locals()

    assert funktools.CLI().run(entrypoint, []) == {'foo': arg.default}
    assert funktools.CLI().run(entrypoint, shlex.split(f'--foo {arg.arg}')) == {'foo': arg.expect}


@pytest.mark.parametrize('arg', args)
def test_parses_keyword_only(arg) -> None:

    @funktools.CLI()
    def entrypoint(*, foo: arg.t) -> dict[str, arg.t]:
        return locals()

    with pytest.raises(SystemExit):
        assert funktools.CLI().run(entrypoint, [])
    assert funktools.CLI().run(entrypoint, shlex.split(f'--foo {arg.arg}')) == {'foo': arg.expect}


@pytest.mark.parametrize('arg', args)
def test_parses_keyword_only_with_default(arg) -> None:

    @funktools.CLI()
    def entrypoint(*, foo: arg.t = arg.default) -> dict[str, arg.t]:
        return locals()

    assert funktools.CLI().run(entrypoint, []) == {'foo': arg.default}
    assert funktools.CLI().run(entrypoint, shlex.split(f'--foo {arg.arg}')) == {'foo': arg.expect}


@pytest.mark.parametrize('arg0,arg1', zip(args, [*args[1:], *args[:1]]))
def test_parses_positional_only_2(arg0, arg1) -> None:
    @funktools.CLI()
    def entrypoint(foo: arg0.t, bar: arg1.t, /) -> dict[str, arg0.t | arg1.t]:
        return locals()

    assert funktools.CLI().run(
        entrypoint, shlex.split(f'{arg0.arg} {arg1.arg}')
    ) == {'foo': arg0.expect, 'bar': arg1.expect}


@pytest.mark.parametrize('arg0,arg1', zip(args, [*args[1:], *args[:1]]))
def test_parses_positional_only_with_default_2(arg0, arg1) -> None:
    @funktools.CLI()
    def entrypoint(foo: arg0.t = arg0.default, bar: arg1.t = arg1.default, /) -> dict[str, arg0.t | arg1.t]:
        return locals()

    assert funktools.CLI().run(entrypoint, []) == {'foo': arg0.default, 'bar': arg1.default}
    assert funktools.CLI().run(entrypoint, shlex.split(arg0.arg)) == {'foo': arg0.expect, 'bar': arg1.default}
    assert funktools.CLI().run(
        entrypoint, shlex.split(f'{arg0.arg} {arg1.arg}')
    ) == {'foo': arg0.expect, 'bar': arg1.expect}


@pytest.mark.parametrize('arg0,arg1', zip(args, [*args[1:], *args[:1]]))
def test_parses_positional_or_keyword_2(arg0, arg1) -> None:
    @funktools.CLI()
    def entrypoint(foo: arg0.t, bar: arg1.t) -> dict[str, arg0.t | arg1.t]:
        return locals()

    assert funktools.CLI().run(
        entrypoint, shlex.split(f'{arg0.arg} {arg1.arg}')
    ) == {'foo': arg0.expect, 'bar': arg1.expect}


@pytest.mark.parametrize('arg0,arg1', zip(args, [*args[1:], *args[:1]]))
def test_parses_positional_or_keyword_with_default_2(arg0, arg1) -> None:
    @funktools.CLI()
    def entrypoint(foo: arg0.t = arg0.default, bar: arg1.t = arg1.default) -> dict[str, arg0.t | arg1.t]:
        return locals()

    assert funktools.CLI().run(entrypoint, []) == {'foo': arg0.default, 'bar': arg1.default}
    assert funktools.CLI().run(entrypoint, shlex.split(f'--foo {arg0.arg}')) == {'foo': arg0.expect, 'bar': arg1.default}
    assert funktools.CLI().run(entrypoint, shlex.split(
        f'--foo {arg0.arg} --bar {arg1.arg}'
    )) == {'foo': arg0.expect, 'bar': arg1.expect}


@pytest.mark.parametrize('arg0,arg1', zip(args, [*args[1:], *args[:1]]))
def test_parses_keyword_only_2(arg0, arg1) -> None:

    @funktools.CLI()
    def entrypoint(*, foo: arg0.t, bar: arg1.t) -> dict[str, arg0.t | arg1.t]:
        return locals()

    assert funktools.CLI().run(entrypoint, shlex.split(
        f'--foo {arg0.arg} --bar {arg1.arg}'
    )) == {'foo': arg0.expect, 'bar': arg1.expect}


@pytest.mark.parametrize('arg0,arg1', zip(args, [*args[1:], *args[:1]]))
def test_parses_keyword_only_with_default_2(arg0, arg1) -> None:

    @funktools.CLI()
    def entrypoint(*, foo: arg0.t = arg0.default, bar: arg1.t = arg1.default) -> dict[str, arg0.t | arg1.t]:
        return locals()

    assert funktools.CLI().run(entrypoint, []) == {'foo': arg0.default, 'bar': arg1.default}
    assert funktools.CLI().run(entrypoint, shlex.split(f'--foo {arg0.arg}')) == {'foo': arg0.expect, 'bar': arg1.default}
    assert funktools.CLI().run(entrypoint, shlex.split(
        f'--foo {arg0.arg} --bar {arg1.arg}'
    )) == {'foo': arg0.expect, 'bar': arg1.expect}


@pytest.mark.parametrize(
    'arg', [Arg(*_args) for _args in [
        ('42', float),
        ('3.14', int),
        ('Hi!', bool),
        ('None', bool),
        ('"[1, 2, 3, 4]"', list[float]),
        ('"(42, False, 3.14, \'Hi!\')"', tuple[int, bool, float]),
        ('"(3.14, \'Hi!\', \'Bye!\')"', tuple[str, ...]),
        ('42', float | bool | str | None),
        ('3.14', int | bool | str | None),
        ('True', int | float | str | None),
        ('False', int | float | str | None),
        ('"\'Hi!\'"', int | float | bool | None),
        ("None", int | float | bool | str),
        ("42", typing.Optional[str]),
        ("3.14", typing.Optional[int]),
        ('"{True: {4.0: {42: \'yes!\'}}}"', dict[bool, dict[float, dict[int, int]]]),
        ('"{1, 2, 3, 4}"', frozenset[bool]),
        ('"{1, 2, 3, 4}"', set[str]),
        ('42', typing.Annotated[float, 'foo annotation']),
    ]])
def test_bad_arg_does_not_parse(arg: Arg) -> None:

    @funktools.CLI()
    def entrypoint(foo: arg.t) -> ...: ...

    with pytest.raises(funktools.CLI.Exception):
        funktools.CLI().run(entrypoint, shlex.split(arg.arg))


def test_execute_hidden_subcommand_works() -> None:

    @funktools.CLI()
    def _foo(foo: str) -> dict[str, str]:
        return locals()

    assert '_foo' not in funktools.CLI().get_argument_parser(_foo.register_key[:-1]).format_help()
    assert funktools.CLI().run(
        _foo.register_key[:-1], shlex.split('_foo hidden_subcommand_works')
    ) == {'foo': 'hidden_subcommand_works'}


def test_async_entrypoint_works() -> None:

    @funktools.CLI()
    async def entrypoint(foo: int) -> dict[str, int]:
        return locals()

    assert funktools.CLI().run(entrypoint, shlex.split('42')) == {'foo': 42}


def test_dash_help_prints_parameter_annotation() -> None:
    @funktools.CLI()
    def entrypoint(foo: typing.Annotated[int, 'This is my comment.']) -> ...: ...

    assert 'This is my comment.' in funktools.CLI().get_argument_parser(entrypoint).format_help()


def test_positional_only_without_default_works() -> None:
    @funktools.CLI()
    def entrypoint(
        foo: typing.Annotated[int, 'Help text for foo.'],
        /,
    ) -> dict[str, int]:
        return locals()

    with pytest.raises(SystemExit):
        funktools.CLI().run(entrypoint, shlex.split(''))
    assert funktools.CLI().run(entrypoint, shlex.split('42')) == {'foo': 42}


def test_dash_help_prints_entrypoint_doc() -> None:
    @funktools.CLI()
    def entrypoint(foo: int) -> ...:
        """What's up, Doc?"""

    assert """What's up, Doc?""" in funktools.CLI().get_argument_parser(entrypoint).format_help()


def test_annotation_log_level_of_logger_sets_choices() -> None:
    logger = logging.getLogger('test_annotated_of_logger_sets_choices')

    @funktools.CLI()
    def entrypoint(foo: funktools.CLI.Annotated.log_level(logger) = 'DEBUG') -> ...: ...

    for choice in typing.get_args(funktools.CLI.Annotated.LogLevelStr):
        assert choice in funktools.CLI().get_argument_parser(entrypoint).format_help()


def test_annotation_log_level_of_logger_sets_log_level() -> None:
    logger = logging.getLogger('test_annotation_log_level_of_logger_sets_log_level')
    logger.setLevel(logging.NOTSET)

    @funktools.CLI()
    def entrypoint(
        log_level: funktools.CLI.Annotated.log_level(logger) = 'NOTSET',
    ) -> dict[str, funktools.CLI.Annotated.LogLevel]:
        return locals()

    assert logger.level == logging.NOTSET

    assert funktools.CLI().run(entrypoint, shlex.split('--log-level CRITICAL')) == {'log_level': 'CRITICAL'}
    assert logger.level == logging.CRITICAL

    assert funktools.CLI().run(entrypoint, shlex.split('--log-level INFO')) == {'log_level': 'INFO'}
    assert logger.level == logging.INFO

    assert funktools.CLI().run(entrypoint, shlex.split('')) == {'log_level': 'NOTSET'}
    assert logger.level == logging.NOTSET


def test_annotation_log_level_of_name_sets_log_level() -> None:
    logger = logging.getLogger('test_annotation_log_level_of_name_sets_log_level')
    logger.setLevel(logging.NOTSET)

    @funktools.CLI()
    def entrypoint(
        log_level: funktools.CLI.Annotated.log_level('test_annotation_log_level_of_name_sets_log_level') = 'NOTSET',
    ) -> dict[str, funktools.CLI.Annotated.LogLevel]:
        return locals()

    assert logger.level == logging.NOTSET

    assert funktools.CLI().run(entrypoint, shlex.split('--log-level CRITICAL')) == {'log_level': 'CRITICAL'}
    assert logger.level == logging.CRITICAL

    assert funktools.CLI().run(entrypoint, shlex.split('--log-level INFO')) == {'log_level': 'INFO'}
    assert logger.level == logging.INFO

    assert funktools.CLI().run(entrypoint, shlex.split('')) == {'log_level': 'NOTSET'}
    assert logger.level == logging.NOTSET


def test_annotation_verbose_sets_log_level() -> None:
    logger = logging.getLogger('test_annotation_verbose_sets_log_level')
    logger.setLevel(logging.NOTSET)

    @funktools.CLI()
    def entrypoint(
        verbose: funktools.CLI.Annotated.verbose(logger) = logging.CRITICAL + 10,
    ) -> dict[str, funktools.CLI.Annotated.LogLevel]:
        return locals()

    assert logger.level == logging.NOTSET
    assert funktools.CLI().run(entrypoint, shlex.split('')) == {'verbose': logging.CRITICAL + 10}
    assert logger.level == logging.CRITICAL + 10
    assert funktools.CLI().run(entrypoint, shlex.split('-v')) == {'verbose': logging.CRITICAL}
    assert logger.level == logging.CRITICAL


def test_annotation_with_count_action_counts() -> None:
    @funktools.CLI()
    def entrypoint(
        foo: typing.Annotated[
            int,
            annotated_types.Ge(0),
            funktools.CLI.AddArgument[int](name_or_flags=['-f', '--foo'], action='count'),
        ] = 0,
    ) -> dict[str, int]:
        return locals()

    assert funktools.CLI().run(entrypoint, shlex.split('')) == {'foo': 0}
    assert funktools.CLI().run(entrypoint, shlex.split('--foo')) == {'foo': 1}
    assert funktools.CLI().run(entrypoint, shlex.split('--foo --foo')) == {'foo': 2}
    assert funktools.CLI().run(entrypoint, shlex.split('-f --foo')) == {'foo': 2}
    assert funktools.CLI().run(entrypoint, shlex.split('-ff')) == {'foo': 2}


def test_enum_help_text_shows_choices() -> None:

    @funktools.CLI()
    def entrypoint(foo: FooEnum) -> dict[str, FooEnum]: ...

    assert '(\'a\', \'b\', \'c\')' in funktools.CLI().get_argument_parser(entrypoint).format_help()


def test_literal_help_text_shows_choices() -> None:

    @funktools.CLI()
    def entrypoint(foo: typing.Literal[1, 2, 3]) -> dict[str, typing.Literal[1, 2, 3]]: ...

    assert '(\'1\', \'2\', \'3\')' in funktools.CLI().get_argument_parser(entrypoint).format_help()


def test_help_shows_type_annotation() -> None:

    @funktools.CLI()
    def entrypoint(foo: dict[str, int]) -> ...: ...

    assert str(dict[str, int]) in funktools.CLI().get_argument_parser(entrypoint).format_help()


def test_enum_enforces_choices() -> None:

    @funktools.CLI()
    def entrypoint(foo: FooEnum) -> dict[str, FooEnum]:
        return locals()

    with pytest.raises(funktools.CLI.Exception):
        funktools.CLI().run(entrypoint, ['d'])
    assert funktools.CLI().run(entrypoint, ['a']) == {'foo': FooEnum.a}


def test_literal_enforces_choices() -> None:

    @funktools.CLI()
    def entrypoint(foo: typing.Literal[1, 2, 3]) -> dict[str, typing.Literal[1, 2, 3]]:
        return locals()

    with (pytest.raises(funktools.CLI.Exception)):
        funktools.CLI().run(entrypoint, ['0'])
    assert funktools.CLI().run(entrypoint, ['1']) == {'foo': 1}


def test_cli_names_enforce_subcommand_structure() -> None:
    class foo:

        @staticmethod
        @funktools.CLI()
        def bar(): ...

        @staticmethod
        @funktools.CLI()
        def baz(): ...

    @funktools.CLI()
    def qux(): ...

    assert 'foo' in funktools.CLI().get_argument_parser(test_cli_names_enforce_subcommand_structure).format_help()
    assert 'bar' in funktools.CLI().get_argument_parser(foo).format_help()
    assert 'baz' in funktools.CLI().get_argument_parser(foo).format_help()
    assert 'qux' in funktools.CLI().get_argument_parser(test_cli_names_enforce_subcommand_structure).format_help()


def test_unresolved_annotation_raises_assertion_error() -> None:
    choices = ['a', 'b', 'c']

    @funktools.CLI()
    def entrypoint(foo: 'typing.Annotated[str, funktools.CLI.AddArgument[str](choices=choices)]') -> ...: ...

    with pytest.raises(AssertionError):
        funktools.CLI().run(entrypoint, ['a'])

    def entrypoint(foo: 'typing.Annotated[str, funktools.CLI.AddArgument[str](choices=choices)]') -> ...: ...
    entrypoint.__annotations__['foo'] = eval(entrypoint.__annotations__['foo'], globals(), locals())
    entrypoint = funktools.CLI()(entrypoint)
    funktools.CLI().run(entrypoint, ['a'])


def test_missing_entrypoint_generates_blank_entrypoint() -> None:
    assert '-h' in funktools.CLI().get_argument_parser(test_missing_entrypoint_generates_blank_entrypoint).format_help()


def test_var_positional_args_are_parsed() -> None:

    @funktools.CLI()
    def entrypoint(*foo: int) -> dict[str, tuple[int, ...]]:
        return locals()

    assert funktools.CLI().run(entrypoint, shlex.split('1 2 3')) == {'foo': (1, 2, 3)}


def test_var_keyword_args_are_parsed() -> None:

    @funktools.CLI()
    def entrypoint(**foo: int) -> dict[str, dict[str, int]]:
        return locals()

    assert funktools.CLI().run(
        entrypoint, shlex.split('--foo 1 --bar 2 --baz 3')
    ) == {'foo': {'foo': 1, 'bar': 2, 'baz': 3}}
