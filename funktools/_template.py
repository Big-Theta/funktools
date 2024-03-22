import inspect
from typing import Any, Callable

_template_funcs: dict[str, Callable] = {}


def _infer_types(func):
    annotations = inspect.get_annotations(func)
    args = inspect.getfullargspec(func).args
    return tuple([annotations[arg] for arg in args])


class _TemplateFunctionBase:
    def __init__(self, func, types):
        if not isinstance(types, tuple):
            types = tuple([types])
        self._funcs = {types: func}

    def __call__(self, *args, **kwargs):
        types = tuple([type(arg) for arg in args])
        return self._funcs[types](*args, **kwargs)

    def __getitem__(self, types):
        if not isinstance(types, tuple):
            types = tuple([types])
        return self._funcs[tuple(types)]

    def __setitem__(self, types, func):
        if not isinstance(types, tuple):
            types = (types,)
        self._funcs[types] = func

    def add(self, func):
        self[_infer_types(func)] = func


def _make_typed_template_function(name: str):
    """Create a _TemplateFunctionBase object with type `name`"""
    TemplateFuncMeta = type(name, (type,), {})
    return TemplateFuncMeta(name, (_TemplateFunctionBase,), {'__name__': name})


class _template:
    def __call__(self, func):
        name = func.__name__
        if template_func := _template_funcs.get(name):
            template_func[_infer_types(func)] = func
            return template_func

        typed_template_func = _make_typed_template_function(func.__name__)
        template_func = typed_template_func(func, _infer_types(func))
        _template_funcs[name] = template_func
        return template_func

    def __getitem__(self, types):
        def _trampoline(func):
            name = func.__name__
            if template_func := _template_funcs.get(name):
                template_func[types] = func
                return template_func

            typed_template_func = _make_typed_template_function(func.__name__)
            template_func = typed_template_func(func, types)
            _template_funcs[name] = template_func
            return template_func

        return _trampoline

