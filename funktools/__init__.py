import typing


def __getattr__(attr: str) -> typing.Callable:
    if attr == "CLI":
        from ._cli import Decorator as CLI
        return CLI
    elif attr == "Log":
        from ._log import Decorator as Log
        return Log
    elif attr == "LRUCache":
        from ._lru_cache import Decorator as LRUCache
        return LRUCache
    elif attr == "Retry":
        from ._retry import Decorator as Retry
        return Retry
    elif attr == "SQLiteCache":
        from ._sqlite_cache import Decorator as SQLiteCache
        return SQLiteCache
    elif attr == "Throttle":
        from ._throttle import Decorator as Throttle
        return Throttle
    elif attr == "Template":
        from ._template import Template
        return Template
    elif attr == "TemplateException":
        from ._template import TemplateException
        return TemplateException
    elif attr == "TemplateFunction":
        from ._template import TemplateFunction
        return TemplateFunction
    elif attr == "TemplatedClass":
        from ._template import TemplatedClass
        return TemplatedClass
    else:
        raise AttributeError(f"Module 'funktools' has no attribute '{attr}'")


__all__ = [
    'CLI',
    'Log',
    'LRUCache',
    'Retry',
    'SQLiteCache',
    'Throttle',
    'Template',
    'TemplateException',
    'TemplateFunction',
]

def __dir__():
    return __all__
