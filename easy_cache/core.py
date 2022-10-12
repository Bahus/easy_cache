# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import abc
import inspect
import logging
import os
import threading
from time import time

import six

from .compat import force_text, force_binary, getargspec
from .utils import get_function_path, cached_property


try:
    # noinspection PyUnresolvedReferences
    import django

    # noinspection PyUnresolvedReferences
    def _get_cache_by_alias(alias):
        if alias == DEFAULT_CACHE_ALIAS:
            from django.core.cache import cache
        else:
            try:
                from django.core.cache import caches
                cache = caches[alias]
            except ImportError:
                from django.core.cache import get_cache
                cache = get_cache(alias)
        return cache

except ImportError:

    class ImproperlyConfigured(Exception):
        pass

    def _get_cache_by_alias(alias):
        raise ImproperlyConfigured('Cache instance not found for alias "%s"' % alias)


logger = logging.getLogger(__name__)


class Value(object):

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


NOT_FOUND = Value('NOT_FOUND')
NOT_SET = Value('NOT_SET')
DEFAULT_TIMEOUT = Value('DEFAULT_TIMEOUT')
CACHE_KEY_DELIMITER = force_text(':')
TAG_KEY_PREFIX = force_text('tag')

LAZY_MODE = os.environ.get('EASY_CACHE_LAZY_MODE_ENABLE', '') == 'yes'
DEFAULT_CACHE_ALIAS = 'default-easy-cache'
META_ACCEPTED_ATTR = '_easy_cache_meta_accepted'
META_ARG_NAME = 'meta'


class CacheHandler(object):
    """ Inspired by Django """

    def __init__(self):
        self._caches = threading.local()

    # noinspection PyMethodMayBeStatic
    def get_default_cache(self, alias):
        return _get_cache_by_alias(alias)

    def __getitem__(self, alias):
        try:
            return self._caches.caches[alias]
        except AttributeError:
            self._caches.caches = {}
        except KeyError:
            pass

        cache = self.get_default_cache(alias)
        self._caches.caches[alias] = cache
        return cache

    def __setitem__(self, key, value):
        try:
            self._caches.caches
        except AttributeError:
            self._caches.caches = {}

        self._caches.caches[key] = value

    def get_default(self):
        return self[DEFAULT_CACHE_ALIAS]

    def set_default(self, cache_instance):
        self[DEFAULT_CACHE_ALIAS] = cache_instance


caches = CacheHandler()


# setters
def set_cache_key_delimiter(delimiter):
    if not isinstance(delimiter, str):
        raise TypeError('Invalid delimiter type, string required')

    global CACHE_KEY_DELIMITER
    CACHE_KEY_DELIMITER = force_text(delimiter)


def set_tag_key_prefix(prefix):
    if not isinstance(prefix, str):
        raise TypeError('Invalid tag prefix type, string required')

    global TAG_KEY_PREFIX
    TAG_KEY_PREFIX = force_text(prefix)


def set_global_cache_instance(cache_instance):
    caches.set_default(cache_instance)


def get_default_cache_instance():
    return caches.get_default()


def invalidate_cache_key(cache_key, cache_instance=None, cache_alias=None):
    _cache = cache_instance or caches[cache_alias or DEFAULT_CACHE_ALIAS]
    return _cache.delete(cache_key)


def invalidate_cache_prefix(prefix, cache_instance=None, cache_alias=None):
    return invalidate_cache_tags(prefix, cache_instance, cache_alias)


def invalidate_cache_tags(tags, cache_instance=None, cache_alias=None):
    if isinstance(tags, str):
        tags = [tags]

    _cache = TaggedCacheProxy(cache_instance or caches[cache_alias or DEFAULT_CACHE_ALIAS])
    return _cache.invalidate(tags)


def create_cache_key(*parts):
    """ Generate cache key using global delimiter char """
    if len(parts) == 1:
        parts = parts[0]
        if isinstance(parts, str):
            parts = [parts]

    return CACHE_KEY_DELIMITER.join(force_text(p) for p in parts)


def create_tag_cache_key(*parts):
    return create_cache_key(TAG_KEY_PREFIX, *parts)


def get_timestamp():
    return int(time() * 1000000)


def compare_dicts(d1, d2):
    """Use simple comparison"""
    return dict(d1) == dict(d2)


class MetaCallable(abc.Mapping):
    """ Object contains meta information about method or function decorated with ecached,
        passed arguments, returned results, signature description and so on.
    """

    def __init__(self, args=(), kwargs=None, returned_value=NOT_SET, call_args=None):
        self.args = args
        self.kwargs = kwargs or {}
        self.returned_value = returned_value
        self.call_args = call_args or {}
        self.function = None
        self.scope = None

    def __contains__(self, item):
        return item in self.call_args

    def __iter__(self):
        return iter(self.call_args)

    def __len__(self):
        return len(self.call_args)

    def __getitem__(self, item):
        return self.call_args[item]

    @property
    def has_returned_value(self):
        return self.returned_value is not NOT_SET


class TaggedCacheProxy(object):
    """ Each cache key/value pair can have additional tags to check
        if cached values is still valid.
    """
    def __init__(self, cache_instance):
        """
            :param cache_instance: should support `set_many` and
            `get_many` operations
        """
        self._cache_instance = cache_instance

    def make_value(self, key, value, tags):
        data = {}
        tags = [create_tag_cache_key(_) for _ in tags]

        # get tags and their cached values (if exists)
        tags_dict = self._cache_instance.get_many(tags)

        # set new timestamps for missed tags
        for tag_key in tags:
            if tags_dict.get(tag_key) is None:
                # this should be sent to cache as separate key-value
                data[tag_key] = get_timestamp()

        tags_dict.update(data)

        data[key] = {
            'value': value,
            'tags': tags_dict,
        }

        return data

    def __getattr__(self, item):
        return getattr(self._cache_instance, item)

    def set(self, key, value, *args, **kwargs):
        value_dict = self.make_value(key, value, kwargs.pop('tags'))
        return self._cache_instance.set_many(value_dict, *args, **kwargs)

    def get(self, key, default=None, **kwargs):
        value = self._cache_instance.get(key, default=NOT_FOUND, **kwargs)

        # not found in cache
        if value is NOT_FOUND:
            return default

        tags_dict = value.get('tags')
        if not tags_dict:
            return value

        # check if it has valid tags
        cached_tags_dict = self._cache_instance.get_many(tags_dict.keys())

        # compare dicts
        if not compare_dicts(cached_tags_dict, tags_dict):
            # cache is invalid - return default value
            return default

        return value.get('value', default)

    def invalidate(self, tags):
        """ Invalidates cache by tags """
        ts = get_timestamp()
        return self._cache_instance.set_many({create_tag_cache_key(tag): ts for tag in tags})


class Cached(object):

    def __init__(self,
                 function,
                 cache_key=None,
                 timeout=DEFAULT_TIMEOUT,
                 cache_instance=None,
                 cache_alias=None,
                 as_property=False):

        self.cache_key = cache_key
        self.function = function
        self.as_property = as_property
        self.timeout = timeout
        self.instance = None
        self.klass = None

        self._scope = None
        self._cache_instance = cache_instance
        self._cache_alias = cache_alias or DEFAULT_CACHE_ALIAS

    @cached_property
    def cache_key_template(self):
        # processing different types of cache_key parameter
        if self.cache_key is None:
            return self.create_cache_key
        elif isinstance(self.cache_key, (list, tuple)):
            return create_cache_key(
                force_text(key).join(('{', '}')) for key in self.cache_key
            )
        else:
            return self.cache_key

    @property
    def scope(self):
        return self.instance or self.klass or self._scope

    @scope.setter
    def scope(self, value):
        self._scope = value

    def get_timeout(self, callable_meta):
        if isinstance(self.timeout, int) or self.timeout is DEFAULT_TIMEOUT:
            return self.timeout

        return self._format(self.timeout, callable_meta)

    if LAZY_MODE:
        def _get_cache_instance(self):
            if self._cache_instance is None:
                return caches[self._cache_alias]
            return self._cache_instance
    else:
        def _get_cache_instance(self):
            if self._cache_instance is None:
                self._cache_instance = caches[self._cache_alias]
            return self._cache_instance

    cache_instance = property(_get_cache_instance)

    def __call__(self, *args, **kwargs):
        callable_meta = self.collect_meta(args, kwargs)
        cache_key = self.generate_cache_key(callable_meta)
        cached_value = self.get_cached_value(cache_key)

        if cached_value is NOT_FOUND:
            logger.debug('MISS cache_key="%s"', cache_key)
            value = self.function(*callable_meta.args, **callable_meta.kwargs)
            callable_meta.returned_value = value
            self.set_cached_value(cache_key, callable_meta)
            return value

        logger.debug('HIT cache_key="%s"', cache_key)
        return cached_value

    def create_cache_key(self, *args, **kwargs):
        """ if cache_key parameter is not specified we use default algorithm """
        scope = self.scope
        prefix = get_function_path(self.function, scope)

        args = list(args)
        if scope:
            try:
                args.remove(scope)
            except ValueError:
                pass

        for k in sorted(kwargs):
            args.append(kwargs[k])
        return create_cache_key(prefix, *args)

    def update_arguments(self, args, kwargs):
        # if we got instance method or class method - modify positional arguments
        if self.instance:
            # first argument in args is "self"
            args = (self.instance, ) + args
        elif self.klass and not type(self.function) == staticmethod:
            # firs argument in args is "cls"
            args = (self.klass, ) + args

        return args, kwargs

    def _clone(self, **kwargs):
        cached = self.__class__(function=self.function, **kwargs)

        cached.cache_key = self.cache_key
        cached.as_property = self.as_property
        cached.timeout = self.timeout

        cached._cache_instance = self._cache_instance
        cached._cache_alias = self._cache_alias
        return cached

    def __get__(self, instance, klass):
        cached = self._clone()

        if cached.as_property and instance is None and klass is not None:
            # special case – calling property as class
            # attr means that we want to run invalidation, so we out of any scope
            return cached

        if instance:
            cached.instance = instance
        if klass:
            cached.klass = klass

        if cached.as_property and instance is not None:
            return cached()

        return cached

    def get_cached_value(self, cache_key):
        logger.debug('Get cache_key="%s"', cache_key)
        return self.cache_instance.get(cache_key, NOT_FOUND)

    def set_cached_value(self, cache_key, callable_meta, **extra):
        timeout = self.get_timeout(callable_meta)

        if timeout is not DEFAULT_TIMEOUT:
            extra['timeout'] = timeout

        logger.debug('Set cache_key="%s" timeout="%s"', cache_key, extra.get('timeout'))
        self.cache_instance.set(cache_key, callable_meta.returned_value, **extra)

    @staticmethod
    def _check_if_meta_required(callable_template):
        """
        Checks if we need to provide `meta` arg into cache key constructor,
        there are two way to get this right.

            1. Use single `meta` argument:

            def construct_key(meta):
                ...

            2. User `meta_accepted` decorator:

            from easy_cache import meta_accepted

            @meta_accepted
            def construct_key(m):
                ...

        """
        if getattr(callable_template, META_ACCEPTED_ATTR, False):
            return True

        arg_spec = getargspec(callable_template)

        if (arg_spec.varargs is None and
                arg_spec.keywords is None and
                arg_spec and arg_spec.args[0] == META_ARG_NAME):
            return True

        return False

    def _format(self, template, meta):
        if isinstance(template, (staticmethod, classmethod)):
            template = template.__func__

        if isinstance(template, abc.Callable):
            if self._check_if_meta_required(template):
                return template(meta)
            else:
                return template(*meta.args, **meta.kwargs)

        if not self.function:
            return template

        try:
            if isinstance(template, str):
                return force_text(template).format(**meta.call_args)
            elif isinstance(template, (list, tuple, set)):
                return [force_text(t).format(**meta.call_args) for t in template]
        except KeyError as ex:
            raise ValueError('Parameter "%s" is required for "%s"' % (ex, template))

        raise TypeError(
            'Unsupported type for key template: {!r}'.format(type(template))
        )

    def collect_meta(self, args, kwargs, returned_value=NOT_SET):
        """ :returns: MetaCallable """
        args, kwargs = self.update_arguments(args, kwargs)

        meta = MetaCallable(args=args, kwargs=kwargs, returned_value=returned_value)

        if not self.function:
            return meta

        # default arguments are also passed to template function
        arg_spec = getargspec(self.function)
        diff_count = len(arg_spec.args) - len(args)

        # do not provide default arguments which were already passed
        if diff_count > 0 and arg_spec.defaults:
            # take minimum here
            diff_count = min(len(arg_spec.defaults), diff_count)
            default_kwargs = dict(zip(arg_spec.args[-diff_count:],
                                      arg_spec.defaults[-diff_count:]))
        else:
            default_kwargs = {}

        default_kwargs.update(kwargs)
        meta.kwargs = default_kwargs
        meta.function = self.function
        meta.scope = self.scope

        try:
            signature = inspect.signature(self.function)
            bound_args = signature.bind(*args, **kwargs).arguments
            bound_args.update(default_kwargs)
            meta.call_args = bound_args
        except TypeError:
            # sometimes not all required parameters are provided, just ignore them
            meta.call_args = meta.kwargs
        return meta

    def generate_cache_key(self, callable_meta):
        return self._format(self.cache_key_template, callable_meta)

    def invalidate_cache_by_key(self, *args, **kwargs):
        callable_meta = self.collect_meta(args, kwargs)
        cache_key = self.generate_cache_key(callable_meta)
        return self.cache_instance.delete(cache_key)

    def refresh_cache(self, *args, **kwargs):
        callable_meta = self.collect_meta(args, kwargs)
        cache_key = self.generate_cache_key(callable_meta)

        logger.debug('REFRESH cache_key="%s"', cache_key)
        value = self.function(*callable_meta.args, **callable_meta.kwargs)
        callable_meta.returned_value = value
        self.set_cached_value(cache_key, callable_meta)
        return value

    def __str__(self):
        return (
            '<Cached: callable="{}", cache_key="{}", timeout={}>'.format(
                get_function_path(self.function, self.scope),
                get_function_path(self.cache_key_template),
                self.timeout)
        )

    def __repr__(self):
        try:
            return self.__str__()
        except (UnicodeEncodeError, UnicodeDecodeError):
            return '[Bad Unicode data]'


class TaggedCached(Cached):
    """ Cache with tags and prefix support """

    def __init__(self,
                 function,
                 cache_key=None,
                 timeout=None,
                 cache_instance=None,
                 cache_alias=None,
                 as_property=False,
                 tags=(),
                 prefix=None):

        super(TaggedCached, self).__init__(
            function=function,
            cache_key=cache_key,
            cache_instance=cache_instance,
            cache_alias=cache_alias,
            timeout=timeout,
            as_property=as_property,
        )
        assert tags or prefix
        self.tags = tags
        self.prefix = prefix

        if self._cache_instance:
            self._cache_instance = TaggedCacheProxy(self.cache_instance)

    if LAZY_MODE:
        @property
        def cache_instance(self):
            if self._cache_instance is None:
                return TaggedCacheProxy(caches[self._cache_alias])
            return self._cache_instance
    else:
        @property
        def cache_instance(self):
            if self._cache_instance is None:
                self._cache_instance = TaggedCacheProxy(caches[self._cache_alias])
            return self._cache_instance

    def _clone(self, **kwargs):
        return super(TaggedCached, self)._clone(tags=self.tags, prefix=self.prefix)

    def invalidate_cache_by_tags(self, tags=(), *args, **kwargs):
        """ Invalidate cache for this method or property by one of provided tags
            :type tags: str | list | tuple | callable
        """
        if not self.tags:
            raise ValueError('Tags were not specified, nothing to invalidate')

        def to_set(obj):
            return set([obj] if isinstance(obj, str) else obj)

        callable_meta = self.collect_meta(args, kwargs)
        all_tags = to_set(self._format(self.tags, callable_meta))

        if not tags:
            tags = all_tags
        else:
            tags = to_set(self._format(tags, callable_meta))
            if all_tags:
                tags &= all_tags

        return self.cache_instance.invalidate(tags)

    def invalidate_cache_by_prefix(self, *args, **kwargs):
        if not self.prefix:
            raise ValueError('Prefix was not specified, nothing to invalidate')

        callable_meta = self.collect_meta(args, kwargs)
        prefix = self._format(self.prefix, callable_meta)
        return self.cache_instance.invalidate([prefix])

    def generate_cache_key(self, callable_meta):
        cache_key = super(TaggedCached, self).generate_cache_key(callable_meta)
        if self.prefix:
            prefix = self._format(self.prefix, callable_meta)
            cache_key = create_cache_key(prefix, cache_key)
        return cache_key

    def set_cached_value(self, cache_key, callable_meta, **extra):
        # generate tags and prefix only after successful execution
        tags = self._format(self.tags, callable_meta)

        if self.prefix:
            prefix = self._format(self.prefix, callable_meta)
            tags = set(tags) | {prefix}

        return super(TaggedCached, self).set_cached_value(cache_key, callable_meta, tags=tags)

    def __str__(self):
        return str(
            '<TaggedCached: callable="{}", cache_key="{}", tags="{}", prefix="{}", '
            'timeout={}>'.format(
                get_function_path(self.function, self.scope),
                get_function_path(self.cache_key_template),
                get_function_path(self.tags),
                get_function_path(self.prefix),
                self.timeout)
        )
