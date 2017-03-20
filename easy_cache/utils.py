# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import six


def get_function_path(function, bound_to=None):
    """Get received function path (as string), to import function later
    with `import_string`.
    """
    if isinstance(function, six.string_types):
        return function

    # static and class methods
    if hasattr(function, '__func__'):
        real_function = function.__func__
    elif callable(function):
        real_function = function
    else:
        return function

    func_path = []

    module = getattr(real_function, '__module__', '__main__')
    if module:
        func_path.append(module)

    if not bound_to:
        try:
            bound_to = six.get_method_self(function)
        except AttributeError:
            pass

    if bound_to:
        if isinstance(bound_to, six.class_types):
            func_path.append(bound_to.__name__)
        else:
            func_path.append(bound_to.__class__.__name__)
        func_path.append(real_function.__name__)
    else:
        # qualname is available in Python 3 only
        func_path.append(getattr(real_function, '__qualname__', real_function.__name__))

    return '.'.join(func_path)
