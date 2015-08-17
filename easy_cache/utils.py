# -*- coding: utf-8 -*-
import six


def get_function_path(function, bound_to=None):
    """Get received function path (as string), to import function later
    with `import_string`.
    """
    if isinstance(function, six.string_types):
        return function

    if not callable(function):
        return function

    func_path = []

    module = getattr(function, '__module__', '__main__')
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

    func_path.append(function.__name__)
    return '.'.join(func_path)
