# -*- coding: utf-8 -*-
"""
    Compatibility between Python versions
"""
from collections import namedtuple
import inspect
import sys
import six


PY3 = six.PY3
PY34 = sys.version_info[0:2] == (3, 4)
PY35 = sys.version_info[0:2] >= (3, 5)


def force_text(obj, encoding='utf-8'):
    if isinstance(obj, six.text_type):
        return obj
    elif not isinstance(obj, six.binary_type):
        return six.text_type(obj)

    try:
        return six.text_type(obj, encoding=encoding)
    except UnicodeDecodeError:
        return obj.decode(encoding)


def force_binary(obj, encoding='utf-8'):
    if isinstance(obj, six.binary_type):
        return obj
    elif not isinstance(obj, six.text_type):
        return six.binary_type(obj)

    try:
        if PY3:
            return six.binary_type(obj, encoding=encoding)
        return six.binary_type(obj)
    except UnicodeEncodeError:
        return obj.encode(encoding)


if PY3:
    ArgSpec = namedtuple('ArgSpec', 'args varargs keywords defaults')
    from inspect import Parameter

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
else:
    def getargspec(func):
        return inspect.getargspec(func)
