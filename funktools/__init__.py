import typing

def __getattr__(attr: str) -> typing.Callable:
    if attr == "CLI":
        from ._cli import CLI
        return CLI
    elif attr == "Key":
        from ._key import Decorator as Key
        return Key
    elif attr == "Memoize":
        from ._memoize import Decorator as Memoize
        return Memoize
    elif attr == "rate":
        from ._rate_decorator import rate
        return rate
    elif attr == "Register":
        from ._register import Decorator as Register
        return Register
    elif attr == "Throttle":
        from ._throttle import Throttle
        return Throttle
    elif attr == "template":
        from ._template import _template
        return _template()
    elif attr == "TemplateException":
        from ._template import TemplateException
        return TemplateException
    else:
        raise AttributeError(f"Module 'funktools' has no attribute '{attr}'")

__all__ = [
    'CLI',
    'Memoize',
    'Key',
    'rate',
    'Register',
    'Throttle',
    'template',
    'TemplateException',
]

def __dir__():
    return __all__
