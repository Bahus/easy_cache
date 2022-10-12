# -*- coding: utf-8 -*-
from collections import abc
from functools import update_wrapper

from easy_cache.core import Cached, TaggedCached, DEFAULT_TIMEOUT, META_ACCEPTED_ATTR


# noinspection PyPep8Naming
class ecached(object):
    """ Caches result of decorated callable.
        Possible use-cases are:

        @cached()
        def func(...):

        @cached('cache_key')  # cache key only
        def func(...):

        @cached('cache_key', 300)  # cache key and timeout in seconds
        def func(...):

        @cached('cache_key', 300, ('user', 'books'))  # + tags
        def func(...):

        @cached('{a}:{b}')
        def func(a, b):  # cache keys based on method parameters

        @cached(['a', 'b'])
        def func(a, b):  # cache keys based on method parameters

        @cached(callable_with_parameters)
        def func(a, b):  # cache_key = callable_with_parameters(a, b)

    """
    def __init__(self, cache_key=None, timeout=DEFAULT_TIMEOUT, tags=(), prefix=None,
                 cache_instance=None, cache_alias=None):
        if tags or prefix:
            self.cache = TaggedCached(
                function=None,
                cache_key=cache_key,
                tags=tags,
                timeout=timeout,
                prefix=prefix,
                cache_instance=cache_instance,
                cache_alias=cache_alias,
            )
        else:
            self.cache = Cached(
                function=None,
                cache_key=cache_key,
                timeout=timeout,
                cache_instance=cache_instance,
                cache_alias=cache_alias,
            )

        self._instance = None
        self._class = None
        self._func = None
        self._wrapped = False

    def __get__(self, instance, owner):
        self._instance = instance
        self._class = owner
        return self.wrapper()

    def wrapper(self):
        if not self._wrapped:
            if self._instance or self._class:
                wrapped = self._func.__get__(self._instance, self._class)

                if isinstance(self._func, staticmethod):
                    # we don't need instance or class, however we need scope
                    self.cache.scope = self._instance or self._class
                    self._instance = None
                    self._class = None
                else:
                    wrapped = wrapped.__func__
            else:
                wrapped = self._func

            update_wrapper(self.cache, wrapped)
            self.cache.function = wrapped
            self.cache.instance = self._instance
            self.cache.klass = self._class
            self._wrapped = True

        return self.cache

    def __call__(self, func):
        self._func = func

        if isinstance(func, abc.Callable):
            return self.wrapper()

        return self

    def __repr__(self):
        return repr(self.cache)


def ecached_property(cache_key=None, timeout=DEFAULT_TIMEOUT, tags=(), prefix=None,
                     cache_instance=None, cache_alias=None):
    """ Works the same as `cached` decorator, but intended to use
        for properties, e.g.:

        class User(object):

            @cached_property('{self.id}:friends_count', 120)
            def friends_count(self):
                return <calculated friends count>

    """
    def wrapper(func):
        if tags or prefix:
            cache = TaggedCached(
                function=func,
                cache_key=cache_key,
                tags=tags,
                timeout=timeout,
                prefix=prefix,
                cache_instance=cache_instance,
                cache_alias=cache_alias,
                as_property=True,
            )
        else:
            cache = Cached(
                function=func,
                cache_key=cache_key,
                timeout=timeout,
                cache_instance=cache_instance,
                cache_alias=cache_alias,
                as_property=True,
            )

        return cache

    return wrapper


def meta_accepted(func):

    if isinstance(func, (staticmethod, classmethod)):
        _func = func.__func__
    else:
        _func = func
    setattr(_func, META_ACCEPTED_ATTR, True)

    return func
