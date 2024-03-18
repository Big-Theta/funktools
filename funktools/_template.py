import inspect
from typing import Any, Callable

class TemplateFunc:
    _name_to_funcs: dict[str, dict[Any, Callable]] = {}

    @staticmethod
    def infer_types(func):
        annotations = inspect.get_annotations(func)
        args = inspect.getfullargspec(func).args
        return tuple([annotations[arg] for arg in args])

    def __init__(self, name, func, types):
        if name not in TemplateFunc._name_to_funcs:
            TemplateFunc._name_to_funcs[name] = {}
        self._funcs = TemplateFunc._name_to_funcs[name]
        if not isinstance(types, tuple):
            types = tuple([types])
        self._funcs[types] = func
        annotations = getattr(func, "__annotations__", None)

    def __call__(self, *args, **kwargs):
        types = tuple([type(arg) for arg in args])
        return self._funcs[types](*args, **kwargs)

    def __getitem__(self, types):
        if not isinstance(types, tuple):
            types = tuple([types])
        return self._funcs[tuple(types)]

    def add(self, func):
        self[TemplateFunc.infer_types(func)] = func

    def __setitem__(self, types, func):
        if not isinstance(types, tuple):
            types = (types,)
        self._funcs[types] = func


class _template:
    def __call__(self, func):
        return TemplateFunc(func.__name__, func, TemplateFunc.infer_types(func))

    def __getitem__(self, types):
        def _trampoline(func):
            return TemplateFunc(func.__name__, func, types)
        return _trampoline

