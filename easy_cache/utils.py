# -*- coding: utf-8 -*-


def get_function_path(function, bound_to=None):
    """Get received function path (as string), to import function later
    with `import_string`.
    """
    if isinstance(function, str):
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
            bound_to = function.__self__
        except AttributeError:
            pass

    if bound_to:
        if isinstance(bound_to, type):
            func_path.append(bound_to.__name__)
        else:
            func_path.append(bound_to.__class__.__name__)
        func_path.append(real_function.__name__)
    else:
        # qualname is available in Python 3 only
        func_path.append(getattr(real_function, '__qualname__', real_function.__name__))

    return '.'.join(func_path)


class cached_property(object):
    """A property that is only computed once per instance and then replaces
       itself with an ordinary attribute. Deleting the attribute resets the
       property.

       Source: https://github.com/bottlepy/bottle/blob/0.11.5/bottle.py#L175
    """

    def __init__(self, func):
        self.__doc__ = getattr(func, '__doc__')
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            # We're being accessed from the class itself, not from an object
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value
