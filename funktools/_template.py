import inspect
from typing import Any, Callable


class _template:
    _name_to_funcs: dict[str, dict[Any, Callable]] = {}

    class Function:
        @staticmethod
        def infer_types(func):
            annotations = inspect.get_annotations(func)
            args = inspect.getfullargspec(func).args
            return tuple([annotations[arg] for arg in args])

        def __init__(self, name, func, types):
            if name not in _template._name_to_funcs:
                _template._name_to_funcs[name] = {}
            self._funcs = _template._name_to_funcs[name]
            if not isinstance(types, tuple):
                types = tuple([types])
            self._funcs[types] = func

        def __call__(self, *args, **kwargs):
            types = tuple([type(arg) for arg in args])
            return self._funcs[types](*args, **kwargs)

        def __getitem__(self, types):
            if not isinstance(types, tuple):
                types = tuple([types])
            return self._funcs[tuple(types)]

        def add(self, func):
            self[_template.Function.infer_types(func)] = func

        def __setitem__(self, types, func):
            if not isinstance(types, tuple):
                types = (types,)
            self._funcs[types] = func


    def __call__(self, func):
        return _template.Function(func.__name__, func, _template.Function.infer_types(func))

    def __getitem__(self, types):
        def _trampoline(func):
            return _template.Function(func.__name__, func, types)
        return _trampoline

