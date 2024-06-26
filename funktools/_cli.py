"""Provides `CLI` decorator class and sane-default instantiated `cli` decorator instance.

The decorator may be used to simplify generation of a CLI based entirely on decorated entrypoint function signature.

Single-entrypoint example:

    - file: foo.py
        from funktools.cli import CLI


        @CLI()  # This will add `.cli` decoration to `entrypoint`.
        def entrypoint(a: int, /, b: str, c: bool = True, *, d: float, e: tuple = tuple()) -> ...:
            ...


        if __name__ == '__main__':
            # This will parse `sys.argv[1:]` and run entrypoint with parsed arguments.
            entrypoint.cli.run()

    - Command line executions:
        $ ./foo.py 1 "this is b" --d 0.1"
        $ ./foo.py 1 "this is b" --no-c --d 0.1 --e "t0" "t1" "t2"

Multiple-entrypoint example:

    - file: prog/__init__.py
        import funktools


        @funktools.CLI(submodules=True)  # This will find entrypoints in submodules named `entrypoint`.
        def entrypoint(a: int, /, b: str, c: bool = True, *, d: float, e: tuple = tuple()) -> ...:
            ...

    - file: prog/foo.py
        def entrypoint

    - file: __main__.py
        if __name__ == '__main__':
            # This will parse `sys.argv[1:]` and run entrypoint with parsed arguments.
            entrypoint.cli.run()

"""
from __future__ import annotations

import annotated_types
import argparse
import ast
import asyncio
import builtins
import dataclasses
import enum
import inspect
import itertools
import logging
import pprint
import re
import sys
import types
import typing

from . import _base


class _Exception(Exception):
    ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class ParseOne[T]:
    t: type[T]

    type _Arg = bool | float | int | str | list | dict | set | None

    def _parse_arg(self, arg: _Arg, /) -> T:
        match self.t if (origin := typing.get_origin(self.t)) is None else (origin, typing.get_args(self.t)):
            case types.NoneType | None:
                assert arg is None, f'{self} expected `None`, got `{arg}`.'
            case builtins.bool | builtins.int | builtins.float | builtins.str:
                assert isinstance(arg, self.t), f'{self} expected `{self.t}`, got `{arg}`'
            case (builtins.frozenset | builtins.list | builtins.set), (Value,):
                assert isinstance(arg, (list, set))
                arg = origin([ParseOne(t=Value)._parse_arg(value) for value in arg])
            case builtins.dict, (Key, Value):
                assert isinstance(arg, dict)
                arg = {
                    ParseOne(t=Key)._parse_arg(key): ParseOne(t=Value)._parse_arg(value) for key, value in arg.items()
                }

            case builtins.tuple, ():
                assert arg == tuple()
            case builtins.tuple, (Value,):
                assert isinstance(arg, tuple) and len(arg) == 1
                arg = tuple([ParseOne(t=Value)._parse_arg(arg[0])])
            case builtins.tuple, (Value, builtins.Ellipsis):
                assert isinstance(arg, tuple)
                arg = tuple([ParseOne(t=Value)._parse_arg(value) for value in arg])
            case builtins.tuple, (Value, *Values):
                assert isinstance(arg, tuple) and len(arg) > 0
                arg = (ParseOne(t=Value)._parse_arg(arg[0]), *ParseOne(t=tuple[*Values])._parse_arg(arg[1:]))

            case (typing.Union | types.UnionType), Values:
                assert type(arg) in Values
            case typing.Literal, Values:
                assert arg in Values

            case (Value, _) | Value if issubclass(Value, enum.Enum):
                assert isinstance(arg, str) and hasattr(Value, arg)
                arg = getattr(Value, arg)

            case (Value, _) | Value:
                arg = Value(arg)

        return arg

    def parse_arg(self, arg: str, /) -> T:
        """Returns a T parsed from given arg or throws an _Exception upon failure."""

        if self.t != str:
            try:
                arg: ParseOne._Arg = ast.literal_eval(arg)
            except (SyntaxError, ValueError,):
                pass

        try:
            value = self._parse_arg(arg)
        except AssertionError as e:
            raise _Exception(f'Could not parse {arg=!r}. {e}.')

        return value


@dataclasses.dataclass(frozen=True, kw_only=True)
class _AddArgument[T]:
    """Generates and collects sane argument defaults intended for argparse.ArgumentParser.add_argument(...).

    Any _Annotation fields that are not `Ellipses` should be passed to <parser instance>.add_argument(...) to add a
    flag.
    """
    name_or_flags: list[str] = ...
    action: typing.Type[argparse.Action] | typing.Literal[
        'store',
        'store_const',
        'store_true',
        'store_false',
        'append',
        'append_const',
        'count',
        'help',
        'version',
    ] = ...
    choices: typing.Iterable[T] = ...
    const: T = ...
    default: T = ...
    dest: str = ...
    help: str = ...
    metavar: str | None = ...
    nargs: typing.Annotated[int, annotated_types.Ge(0)] | typing.Literal[
        '?',
        '*',
        '+'
    ] = ...
    required: bool = ...
    type: typing.Callable[[str], T] = ...

    @staticmethod
    def of_parameter(parameter: inspect.Parameter, /) -> _AddArgument[T]:
        """Returns an _Annotation converted from given `parameter`.

        `parameter.annotation` may be of `typing.Annotated[T, <annotations>...]`. If an _Annotation instance is included
        in the annotations, non-Ellipses fields will override anything this method would normally generate. This is
        useful if special argparse behavior for the argument is desired.

        ref. https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument
        """

        assert not isinstance(parameter.annotation, str), (
            f'{parameter.annotation=!r} is not evaluated. You may need to manually evaluate this annotation.'
            f' See https://peps.python.org/pep-0563/#resolving-type-hints-at-runtime.'
        )

        add_argument = _AddArgument()
        t = parameter.annotation

        help_lines = []
        if typing.get_origin(t) is typing.Annotated:
            t, *args = typing.get_args(t)
            help_lines += [*filter(lambda arg: isinstance(arg, str), args)]
            for override_add_arguments in filter(lambda arg: isinstance(arg, _AddArgument), args):
                add_argument = dataclasses.replace(
                    add_argument,
                    **dict(filter(
                        lambda item: item[1] is not ...,
                        dataclasses.asdict(override_add_arguments).items(),
                    )),
                )

        if add_argument.name_or_flags is ...:
            match parameter.kind, parameter.default == parameter.empty:
                case (
                    (parameter.POSITIONAL_ONLY, _)
                    | ((parameter.VAR_POSITIONAL | parameter.POSITIONAL_OR_KEYWORD), True)
                ):
                    add_argument = dataclasses.replace(add_argument, name_or_flags=[parameter.name])
                case (parameter.KEYWORD_ONLY, _) | (parameter.POSITIONAL_OR_KEYWORD, False):
                    add_argument = dataclasses.replace(
                        add_argument, name_or_flags=[f'--{parameter.name.replace('_', '-')}']
                    )

        if add_argument.action is ...:
            match parameter.kind:
                case inspect.Parameter.VAR_POSITIONAL:
                    add_argument = dataclasses.replace(add_argument, action='append')

        if add_argument.choices is ...:
            match typing.get_origin(t) or type(t):
                case typing.Literal:
                    add_argument = dataclasses.replace(add_argument, choices=typing.get_args(t))
                case enum.EnumType:
                    add_argument = dataclasses.replace(add_argument, choices=tuple(t))

        # No automatic actions needed for 'const'.

        if add_argument.default is ...:
            if parameter.default != parameter.empty:
                add_argument = dataclasses.replace(add_argument, default=parameter.default)

        if add_argument.help is ...:
            if add_argument.default is not ...:
                help_lines.append(f'default: {add_argument.default!r}')
            if add_argument.choices is not ...:
                match typing.get_origin(t) or type(t):
                    case enum.EnumType:
                        choice_names = tuple(map(lambda value: value.name, t))
                    case _:
                        choice_names = tuple(map(str, add_argument.choices))
                show_choice_names = tuple(filter(lambda choice_name: not choice_name.startswith('_'), choice_names))
                help_lines.append(
                    f'choices: {pprint.pformat(show_choice_names, compact=True, width=60)}'
                )
            help_lines.append(f'type: {typing.Literal if typing.get_origin(t) is typing.Literal else t!r}')
            add_argument = dataclasses.replace(add_argument, help='\n'.join(help_lines))

        if add_argument.metavar is ...:
            if add_argument.choices is not ...:
                add_argument = dataclasses.replace(add_argument, metavar=f'{{{parameter.name}}}')

        if add_argument.nargs is ...:
            match add_argument.action, parameter.kind, parameter.default == parameter.empty:
                case builtins.Ellipsis, (parameter.POSITIONAL_ONLY | parameter.POSITIONAL_OR_KEYWORD), False:
                    add_argument = dataclasses.replace(add_argument, nargs='?')
                case 'append', (parameter.VAR_POSITIONAL | parameter.VAR_KEYWORD), True:
                    add_argument = dataclasses.replace(add_argument, nargs='*')

        if add_argument.required is ...:
            if (parameter.kind == parameter.KEYWORD_ONLY) and (parameter.default == parameter.empty):
                add_argument = dataclasses.replace(add_argument, required=True)

        if add_argument.type is ...:
            if add_argument.action not in {'count', 'store_false', 'store_true'}:
                add_argument = dataclasses.replace(add_argument, type=lambda arg: ParseOne(t=t).parse_arg(arg))

        return add_argument


# Override __init__ so that we can make `_side_effect` positional-only while instantiating.
@dataclasses.dataclass(frozen=True, init=False)
class _SideEffect[T]:
    _side_effect: typing.Callable[[T], T]

    def __init__(self, _side_effect: typing.Callable[[T], T], /) -> None:
        object.__setattr__(self, '_side_effect', _side_effect)


_LogLevelInt = typing.Annotated[int, annotated_types.Interval(ge=10, le=60)]
_LogLevelStr = typing.Literal['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET']
_LogLevel = _LogLevelInt | _LogLevelStr


@dataclasses.dataclass(frozen=True, kw_only=True)
class _Annotated:

    LogLevelStr: typing.ClassVar[type[_LogLevelStr]] = _LogLevelStr
    LogLevelInt: typing.ClassVar[type[_LogLevelInt]] = _LogLevelInt
    LogLevel: typing.ClassVar[type[_LogLevel]] = _LogLevel

    @staticmethod
    def quiet(logger_or_name: logging.Logger | str, /) -> type[_LogLevelInt]:
        logger = logger_or_name if isinstance(logger_or_name, logging.Logger) else logging.getLogger(logger_or_name)

        class QuietAction(argparse.Action):
            def __call__(
                self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values: list[object],
                option_string=None
            ) -> None:
                logger.setLevel(level := min(getattr(namespace, self.dest) + 10, logging.CRITICAL + 10))
                setattr(namespace, self.dest, level)

        return typing.Annotated[
            _LogLevelInt,
            _AddArgument[_LogLevelInt](name_or_flags=['-q', '--quiet'], action=QuietAction, nargs=0),
            _SideEffect[_LogLevelInt](lambda verbose: logger.setLevel(verbose))
        ]

    @staticmethod
    def verbose(logger_or_name: logging.Logger | str, /) -> type[_LogLevelInt]:
        logger = logger_or_name if isinstance(logger_or_name, logging.Logger) else logging.getLogger(logger_or_name)

        class VerboseAction(argparse.Action):
            def __call__(
                self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values: list[object],
                option_string=None
            ) -> None:
                logger.setLevel(level := max(getattr(namespace, self.dest) - 10, logging.DEBUG))
                setattr(namespace, self.dest, level)

        return typing.Annotated[
            _LogLevelInt,
            _AddArgument[_LogLevelInt](name_or_flags=['-v', '--verbose'], action=VerboseAction, nargs=0),
            _SideEffect[_LogLevelInt](lambda verbose: logger.setLevel(verbose))
        ]

    @staticmethod
    def log_level(logger_or_name: logging.Logger | str, /) -> type[_LogLevelStr]:
        logger = logger_or_name if isinstance(logger_or_name, logging.Logger) else logging.getLogger(logger_or_name)

        return typing.Annotated[
            _LogLevelStr,
            _AddArgument[_LogLevelStr](name_or_flags=['-l', '--log-level']),
            _SideEffect[_LogLevelStr](lambda log_level: logger.setLevel(log_level))
        ]


@dataclasses.dataclass(frozen=True, kw_only=True)
class _Persist[** Params, Return]:
    ...
    # TODO: Make a sticky flag that memoizes a flag.


class ArgumentParser[** Params, Return](argparse.ArgumentParser):
    ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class Decorator[** Params, Return](_base.Decorator[Params, Return]):
    """Decorate a function, adding `.cli` attribute.

    The `.cli.run` function parses command line arguments (e.g. `sys.argv[1:]`) and executes the decorated function with
    the parsed arguments.

    When created, setting `submodules` to True indicates that the decorator should create a hierarchical parser with
    subcommand structure corresponding to submodule structure starting with the decorated function's module. Any module
    with a function name matching given `entrypoint` name have a corresponding CLI subcommand generated with an
    equivalent CLI signature.

    Parser subcommand documentation is generated from corresponding module docstrings.

    Given a program with the following file structure (column 1), python entrypoints (column 2), the generated CLI
    signature follows (column 3).

              1. Structure          2. entrypoint signature             3. generated CLI signature
        (a)   |- __main__.py                                            prog [-h] {.|foo|baz|quux}
              |- prog
        (b)      |- __init__.py     entrypoint()                        prog . [-h]
                 |- foo.py          entrypoint(pos: int, /)             prog foo [-h] POS
        (a)      |- _bar.py         entrypoint(pos: int = 42, /)        prog _bar [-h] [POS]
                 |- baz
        (c)      |  |- __init__.py  entrypoint(pos_or_kwd: str)         prog baz . [-h] --pos-or-kwd POS_OR_KWD
                 |  |- qux.py       entrypoint(pos_or_kwd: str = 'hi')  prog baz qux [-h] [--pos-or-kwd POS_OR_KWD]
                 |- quux
        (d)         |- __init__.py  entrypoint(*args: list)             Decoration fails with RuntimeError!
        (d)         |- corge.py     entrypoint(**kwargs: dict)          Decoration fails with RuntimeError!

    Note for the diagram above:
        (a) Subcommands that start with underscores are hidden in the CLI signature. They are, however, valid.
        (b) The only `entrypoint` that needs to be decorated is in the toplevel __init__.py.
        (c) Entrypoints in an __init__.py correspond to a `.` CLI subcommand.
        (d) Variadic args and kwargs are unsupported.

    Args (Keyword):
        submodules: If True, subcommands are generated for every submodule in the module hierarchy. CLI bindings are
            generated for each submodule top-level function with name matching decorated entrypoint name.
    """

    register: typing.ClassVar[_base.Register] = _base.Register()

    AddArgument: typing.ClassVar = _AddArgument
    Annotated: typing.ClassVar = _Annotated
    Exception: typing.ClassVar = _Exception
    type Key = str | _base.Register.Key | _base.Decorated | _base.Decoratee

    def __call__(
        self,
        decoratee: _base.Decoratee[Params, Return] | _base.Decorated[Params, Return],
        /,
    ) -> _base.Decorated[Params, Return]:
        decoratee = super().__call__(decoratee)

        # We really do intend to return the decoratee here. The only point of CLI is to register the decoratee. We don't
        # make a parser unless asked via CLI().get_argument_parser() or run unless asked via CLI().main().
        return decoratee

    def gen_decorated(self, key: Key) -> _base.Decorated[Params, Return]:
        match key:
            case str(name):
                register_key = _base.Register.Key([*re.sub(r'.<.*>', '', name).split('.')])
            case tuple(register_key):
                ...
            case _base.Decorated() as decorated:
                register_key = decorated.register_key
            case _base.Decoratee() as decoratee:
                register_key = _base.Register.Key([
                    *re.sub(r'.<.*>', '', '.'.join([decoratee.__module__, decoratee.__qualname__])).split('.')
                ])
            case _: assert False, 'Unreachable'  # pragma: no cover

        if (decorated := self.register.decorateds.get(register_key)) is None:
            def decoratee(subcommand: typing.Literal[*sorted(self.register.links.get(register_key, set()))]) -> None:  # noqa
                self.get_argument_parser(register_key).print_usage()

            # Using the local variables in function signature converts the entire annotation to a string without
            #  evaluating it. Force evaluation of the annotation.
            #  ref. https://peps.python.org/pep-0563/#resolving-type-hints-at-runtime
            decoratee.__annotations__['subcommand'] = eval(decoratee.__annotations__['subcommand'], None, locals())

            decorated = self(decoratee)

        return decorated

    def get_argument_parser(self, key: Key) -> ArgumentParser[Params, Return]:
        decorated = self.gen_decorated(key)

        argument_parser = ArgumentParser(
            description='\n'.join(filter(None, [
                decorated.__doc__,
                f'return type: {pprint.pformat(decorated.signature.return_annotation, compact=True, width=75)}'
            ])),
            formatter_class=argparse.RawTextHelpFormatter
        )

        for parameter in decorated.signature.parameters.values():
            if parameter.kind is inspect.Parameter.VAR_KEYWORD:
                # Var keywords will are parsed on a second pass.
                continue
            add_argument_params = dict(filter(
                lambda item: not isinstance(item[1], typing.Hashable) or item[1] is not ...,
                dataclasses.asdict(_AddArgument().of_parameter(parameter)).items()
            ))
            argument_parser.add_argument(*add_argument_params.pop('name_or_flags'), **add_argument_params)

        return argument_parser

    def run(self, decorated_or_key: _base.Decorated | _base.Register.Key | str, args: list[str] = ...) -> None:
        match decorated_or_key:
            case str():
                register_key = _base.Register.Key([*re.sub(r'.<.*>', '', decorated_or_key).split('.')])
            case _base.Decorated():
                register_key = decorated_or_key.register_key
            case tuple():
                register_key = _base.Register.Key(decorated_or_key)
            case _: assert False, 'Unreachable'

        args = sys.argv[1:] if args is ... else args

        while args and (_base.Register.Key([*register_key, args[0]]) in self.register.links):
            register_key = _base.Register.Key([*register_key, args.pop(0)])

        argument_parser = self.get_argument_parser(register_key)
        parsed_ns, remainder_args = argument_parser.parse_known_args(args)
        parsed_args = vars(parsed_ns)

        decorated = self.gen_decorated(register_key)

        # Note that this may be the registered entrypoint of a submodule, not the entrypoint that is decorated.
        args, kwargs = [], {}
        for _parameter in decorated.signature.parameters.values():
            side_effects = []
            if typing.get_origin(_parameter.annotation) is typing.Annotated:
                for annotation in typing.get_args(_parameter.annotation):
                    match annotation:
                        case _SideEffect(side_effect):
                            side_effects.append(side_effect)

            side_effect = [
                *itertools.accumulate(side_effects, func=lambda x, y: lambda z: x(y(z)), initial=lambda x: x)
            ][-1]

            values = []
            match _parameter.kind:
                case inspect.Parameter.POSITIONAL_ONLY:
                    values = [parsed_args.pop(_parameter.name)]
                    args.append(side_effect(values[0]))
                case inspect.Parameter.POSITIONAL_OR_KEYWORD | inspect.Parameter.KEYWORD_ONLY:
                    values = [parsed_args.pop(_parameter.name)]
                    kwargs[_parameter.name] = values[0]
                case inspect.Parameter.VAR_POSITIONAL:
                    values = [parsed_args.pop(_parameter.name)][0][0]
                    args += values
                case inspect.Parameter.VAR_KEYWORD:
                    parser = argparse.ArgumentParser()
                    for remainder_arg in remainder_args:
                        if remainder_arg.startswith('--'):
                            parser.add_argument(
                                remainder_arg, type=lambda arg: ParseOne(t=_parameter.annotation).parse_arg(arg)
                            )
                    remainder_ns = parser.parse_args(remainder_args)
                    remainder_args = []
                    remainder_kwargs = dict(vars(remainder_ns).items())

                    values = remainder_kwargs.values()
                    kwargs.update(remainder_kwargs)

            [side_effect(value) for side_effect in side_effects for value in values]

        assert not parsed_args, f'Unrecognized args: {parsed_args!r}.'
        assert not remainder_args, f'Unrecognized args: {remainder_args!r}.'

        return_ = decorated(*args, **kwargs)
        match decorated:
            case _base.AsyncDecorated():
                return asyncio.run(return_)
            case _base.MultiDecorated():
                return return_
            case _: assert False, 'Unreachable'
