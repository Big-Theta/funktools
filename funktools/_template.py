import inspect
import typing
import functools

__all__ = [
    "TemplateException",
    "TemplateFunction",
    "Template",
    "TemplatedClass",
]


class TemplateException(Exception):
    pass


class TemplateFunction:
    def __init__(
        self,
        name: str,
        annotations: dict,
        types2funcs: dict[tuple, typing.Callable],
        func_arg_infos: list["_FuncArgInfo"],
        instance: typing.Any,
    ):
        self.__name__ = name
        self.__annotations__ = annotations
        self._types2funcs = types2funcs
        self._func_arg_infos = func_arg_infos
        self._instance = instance

    @staticmethod
    def new(name):
        return TemplateFunction(
            name=name, annotations={}, types2funcs={}, func_arg_infos=[], instance=None
        )

    def with_instance(self, instance):
        return TemplateFunction(
            name=self.__name__,
            annotations=self.__annotations__,
            types2funcs=self._types2funcs,
            func_arg_infos=self._func_arg_infos,
            instance=instance,
        )

    def __repr__(self):
        return f"<funktools.TemplateFunction {self.__name__} at 0x{id(self):x}>"

    def __call__(self, *args, **kwargs):
        if self._instance is not None:
            args = (self._instance,) + args

        val_types = [type(arg) for arg in args]

        # The logic in this loop would be more natural in a
        # _FuncArgInfo.is_match method, but that has about a 30% overhead on
        # every call to a templated function.
        for info in self._func_arg_infos:
            not_a_match = False
            argspec = info._fullargspec

            num_matched = 0
            if defaults := argspec.defaults:
                num_matched = len(
                    set(argspec.args[-len(defaults) :]).difference(set(kwargs.keys()))
                )

            if kwonlydefaults := argspec.kwonlydefaults:
                num_matched += len(
                    set(kwonlydefaults.keys()).difference(set(kwargs.keys()))
                )

            if info._num_args_to_match != len(args) + len(kwargs) + num_matched:
                continue

            for name in argspec.args[: len(val_types)]:
                if name in kwargs:
                    not_a_match = True
                    break
            if not_a_match:
                continue

            for name, val_type, want_type in zip(
                argspec.args, val_types, info._parg_types
            ):
                # _FuncArgInfo instance is the sentinal for "no annotation"
                if want_type is not info and val_type != want_type:
                    not_a_match = True
                    break

                num_matched += 1
            if not_a_match:
                continue

            annotations = argspec.annotations
            legal_arg_names = info._legal_arg_names
            for name, val in kwargs.items():
                if (want_type := annotations.get(name, info)) is not info:
                    if type(val) != want_type:
                        not_a_match = True
                        break
                elif name not in legal_arg_names:
                    not_a_match = True
                    break

                num_matched += 1
            if not_a_match:
                continue

            if num_matched == info._num_args_to_match:
                return info._func(*args, **kwargs)

        raise TemplateException("Cannot find templated function matching signature")

    def __getitem__(self, types):
        try:
            return self._types2funcs[types]
        except KeyError:
            raise TemplateException(
                f"Cannot find templated function with types: {types}"
            )

    def __setitem__(self, types: typing.Hashable, func: typing.Callable):
        self._types2funcs[types] = func

        annotations = self.get.__annotations__

        if isinstance(types, tuple):
            types = tuple[types]

        annotations["key"] = typing.Union[types, annotations.get("key", types)]

        self._append_func_arg_info(func)

    def add(self, func: typing.Callable):
        func_arg_info = self._append_func_arg_info(func)
        argspec = func_arg_info._fullargspec

        annotations = argspec.annotations
        if argspec and set(argspec.args) == set(annotations.keys()):
            types = tuple([annotations[arg] for arg in argspec.args])

            if len(types) == 1:
                types = types[0]

            self[types] = func

    def get(self, key) -> typing.Callable:
        return self[key]

    def _append_func_arg_info(
        self,
        func: typing.Callable,
        fullargspec: inspect.FullArgSpec = None,
    ):
        arg_info = _FuncArgInfo(func, fullargspec)

        if annotation_keys := arg_info.annotation_keys():
            annotations = self.__annotations__
            former_args = set(annotations.keys())

            for arg in former_args.union(annotation_keys):
                arg_type = arg_info.annotations().get(arg, None)
                former_arg_type = annotations.get(
                    arg, arg_type if not self._func_arg_infos else None
                )

                if former_arg_type is None and arg_type is None:
                    annotations[arg] = None
                else:
                    annotations[arg] = former_arg_type | arg_type

        self._func_arg_infos.append(arg_info)
        return arg_info


class _FuncArgInfo:
    """Information about the arguments for a function."""

    def __init__(
        self,
        func: typing.Callable,
        fullargspec: inspect.FullArgSpec = None,
    ):
        self._func = func
        self._fullargspec = inspect.getfullargspec(self._func)
        self._legal_arg_names = set(
            self._fullargspec.args + self._fullargspec.kwonlyargs
        )
        self._num_args_to_match = len(self._legal_arg_names)
        self._parg_types = [
            self._fullargspec.annotations.get(arg, self)
            for arg in self._fullargspec.args
        ]

    def annotation_keys(self) -> set[str]:
        argspec = self._fullargspec
        return set(argspec.args).union(argspec.annotations.keys())

    def annotations(self) -> dict:
        return self._fullargspec.annotations


class _Template:
    def __call__(self, func):
        """Add a func to the TemplateFunction.

        If all arguments of func are annotated, this will allow the function to
        be retrieved from the TemplateFunction using square brackets and the
        specified types.

        The function can also be found by matching argument types and names at a
        callsite.

        >>> template = _Template() # Use `from funktools import template`
        >>> @template
        ... def foo(a: int, b: str):
        ...     return "foo(a: int, b: str)"
        >>>
        >>> @template
        ... def foo(a: float, b: int):
        ...     return "foo(a: float, b: int)"
        ...
        >>> @template
        ... def foo(a, *, c):
        ...     return "foo(a, *, c)"
        ...
        >>> foo(1, "b")
        "foo(a: int, b: str)"
        >>> foo(2.2, 1)
        "foo(a: float, b: int)"
        >>> foo(None, c="c")
        "foo(a, *, c)"
        """
        name = func.__name__

        # Check the surrounding scope for an object with this name -- if
        # it exists and it's a TemplateFunction, we avoid making a new one.
        if (
            template_func := inspect.stack()[1].frame.f_locals.get(name)
        ) and isinstance(template_func, TemplateFunction):
            template_func.add(func)
            return template_func

        typed_template_func = TemplateFunction.new(func.__name__)
        typed_template_func.add(func)
        return typed_template_func

    def __getitem__(self, types):
        """Adds a function using types as a lookup key."""

        def _trampoline(func):
            name = func.__name__

            if (
                template_func := inspect.stack()[1].frame.f_locals.get(name)
            ) and isinstance(template_func, TemplateFunction):
                template_func[types] = func
                return template_func

            typed_template_func = TemplateFunction.new(func.__name__)
            typed_template_func[types] = func
            return typed_template_func

        return _trampoline


def decorate__getattribute__(orig__getattribute__, templated_attributes):
    @functools.wraps(orig__getattribute__)
    def __getattribute__(self, attribute):
        if attr := templated_attributes.get(attribute):
            return attr.with_instance(self)
        return orig__getattribute__(self, attribute)

    return __getattribute__


def TemplatedClass(cls):
    templated_attributes = {}
    for name, attr in cls.__dict__.items():
        if isinstance(attr, TemplateFunction):
            templated_attributes[name] = attr

    cls.__getattribute__ = decorate__getattribute__(
        cls.__getattribute__, templated_attributes=templated_attributes
    )

    return cls


Template = _Template()
