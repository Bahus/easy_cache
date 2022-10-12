# -*- coding: utf-8 -*-
from collections import namedtuple
import inspect
from inspect import Parameter


def force_text(obj, encoding='utf-8'):
    if isinstance(obj, str):
        return obj
    elif not isinstance(obj, bytes):
        return str(obj)

    try:
        return str(obj, encoding=encoding)
    except UnicodeDecodeError:
        return obj.decode(encoding)


def force_binary(obj, encoding='utf-8'):
    if isinstance(obj, bytes):
        return obj
    elif not isinstance(obj, str):
        return bytes(obj)

    try:
        return bytes(obj, encoding=encoding)
    except UnicodeEncodeError:
        return obj.encode(encoding)


ArgSpec = namedtuple('ArgSpec', 'args varargs keywords defaults')


def getargspec(func):
    signature = inspect.signature(func)

    args = []
    varargs = None
    keywords = None
    defaults = []

    for param in signature.parameters.values():  # type: Parameter
        if param.kind == Parameter.VAR_POSITIONAL:
            varargs = param.name
        elif param.kind in (
                Parameter.POSITIONAL_ONLY,
                Parameter.KEYWORD_ONLY,
                Parameter.POSITIONAL_OR_KEYWORD):
            args.append(param.name)
        elif param.kind == Parameter.VAR_KEYWORD:
            keywords = param.name

        # noinspection PyProtectedMember
        if param.default is not inspect._empty:
            defaults.append(param.default)

    return ArgSpec(args, varargs, keywords, tuple(defaults))
