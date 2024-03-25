import inspect
import typing


class TemplateException(Exception):
    pass


class TemplateFunction:
    pass


class _FuncArgInfo:
    """Information about the arguments for a function."""

    def __init__(
        self,
        func: typing.Callable,
        fullargspec: inspect.FullArgSpec = None,
    ):
        self._func = func

        try:
            self._fullargspec = inspect.getfullargspec(self.get_func())
        except TypeError as ex:
            self._fullargspec = None

        self._arg2type = None

    def get_func(self) -> typing.Callable:
        return self._func

    def annotations(self) -> dict:
        return self.fullargspec().annotations

    def fullargspec(self) -> None | inspect.FullArgSpec:
        return self._fullargspec

    def is_match(self, *args, **kwargs) -> bool:
        """Check if this function can handle the provided arguments.

        This checks argument names as well as types provided in annotations.
        """
        argspec = self.fullargspec()
        if argspec is None:
            return False

        matched = set()

        matched_via_default = 0
        if argspec.kwonlydefaults:
            matched.update(set(argspec.kwonlydefaults.keys()))
            matched_via_default = len(matched.difference(set(kwargs.keys())))

        if (
            len(argspec.args) + len(argspec.kwonlyargs)
            != len(args) + len(kwargs) + matched_via_default
        ):
            return False

        for name, val in zip(argspec.args, args):
            if want_type := argspec.annotations.get(name):
                if not isinstance(val, want_type):
                    return False

            matched.add(name)

        legal_names = set(argspec.args + argspec.kwonlyargs)
        for name, val in kwargs.items():
            if name not in legal_names:
                return False

            if want_type := argspec.annotations.get(name):
                if not isinstance(val, want_type):
                    return False

            matched.add(name)

        if len(matched) != len(argspec.args) + len(argspec.kwonlyargs):
            return False

        return True


class _template:
    def __call__(self, func):
        """Add a func to the TemplateFunction.

        If all arguments of func are annotated, this will allow the function to
        be retrieved from the TemplateFunction using square brackets and the
        specified types.

        The function can also be found by matching argument types and names at a
        callsite.

        >>> template = _template() # Use `from funktools import template`
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

        typed_template_func = self.make(func.__name__)
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

            typed_template_func = self.make(func.__name__)
            typed_template_func[types] = func
            return typed_template_func

        return _trampoline

    @staticmethod
    def make(name: str):
        """Create a TemplateFunction object with type `name`."""

        def __init__(self):
            self._types2funcs = {}
            self._func_arg_infos = []

        def __call__(self, *args, **kwargs):
            for func_arg_info in self._func_arg_infos:
                if func_arg_info.is_match(*args, **kwargs):
                    return func_arg_info.get_func()(*args, **kwargs)

            if len(args) == 1:
                types = type(args[0])
            else:
                types = tuple([type(arg) for arg in args])

            if func := self._types2funcs.get(types):
                return func(*args, **kwargs)

            raise TemplateException("Cannot find templated function matching signature")

        __call__.__annotations__ = {}

        def __getitem__(self, types):
            try:
                return self._types2funcs[types]
            except KeyError:
                raise TemplateException(
                    f"Cannot find templated function with types: {types}"
                )

        __getitem__.__annotations__ = {}

        def __setitem__(self, types: typing.Type | tuple, func: typing.Callable):
            self._types2funcs[types] = func

            annotations = self.__class__.__getitem__.__annotations__

            if isinstance(types, tuple):
                types = typing.Tuple[types]

            annotations["types"] = typing.Union[types, annotations.get("types", types)]

            for param, types in inspect.get_annotations(func).items():
                annotations[param] = typing.Union[types, annotations.get(param, types)]

            annotations["return"] = typing.Callable

            self._append_func_arg_info(func)

        def add(self, func: typing.Callable):
            func_arg_info = self._append_func_arg_info(func)
            argspec = func_arg_info.fullargspec()

            annotations = argspec.annotations
            args_annotated = len(annotations)
            if "return" in annotations:
                args_annotated = args_annotated - 1

            types = None
            if argspec and args_annotated == len(argspec.args):
                types = tuple([annotations[arg] for arg in argspec.args])

                if len(types) == 1:
                    types = types[0]

                self[types] = func

        def _append_func_arg_info(
            self,
            func: typing.Callable,
            fullargspec: inspect.FullArgSpec = None,
        ):
            arg_info = _FuncArgInfo(func, fullargspec)

            call_annotations = self.__class__.__call__.__annotations__
            if argspec := arg_info.fullargspec():
                all_args = (
                    arg_info.fullargspec().args + arg_info.fullargspec().kwonlyargs
                )
                for arg in all_args:
                    arg_type = arg_info.annotations().get(arg, typing.Any)
                    call_annotations[arg] = arg_type | call_annotations.get(
                        arg, arg_type
                    )

            self._func_arg_infos.append(arg_info)
            return arg_info

        TemplateFuncMeta = type(name, (type,), {})
        return TemplateFuncMeta(
            name,
            (TemplateFunction,),
            {
                "__init__": __init__,
                "__call__": __call__,
                "__getitem__": __getitem__,
                "__setitem__": __setitem__,
                "__name__": name,
                "__annotations__": {},
                "add": add,
                "_append_func_arg_info": _append_func_arg_info,
            },
        )()
