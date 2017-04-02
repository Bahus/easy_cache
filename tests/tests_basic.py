# -*- coding: utf-8 -*-
import collections
import logging
import os
import random
import sys
import six

from functools import partial
from mock import Mock
from unittest import TestCase, skipIf

from tests.conf import DEBUG, REDIS_HOST, MEMCACHED_HOST


from easy_cache import ecached, ecached_property, meta_accepted
from easy_cache import (
    set_global_cache_instance,
    invalidate_cache_key,
    invalidate_cache_tags,
    invalidate_cache_prefix,
    get_default_cache_instance,
)
from easy_cache.core import (
    create_cache_key,
    create_tag_cache_key,
    DEFAULT_TIMEOUT,
    MetaCallable,
)
from easy_cache.compat import force_text


cache_mock = Mock()


class MethodProxy(object):
    log = logging.getLogger('method_proxy')
    log.setLevel(logging.DEBUG)
    log.addHandler(logging.StreamHandler(sys.stdout))

    def __init__(self, method_name, method, ref):
        self.method_name = method_name
        self.method = method
        self.ref = ref

    def __call__(self, *args, **kwargs):
        self.log.info('[%r] Cache-%s: args=%r, kwargs=%r', self.ref, self.method_name, args, kwargs)
        return self.method(*args, **kwargs)


# noinspection PyProtectedMember
class CacheProxy(object):

    def __init__(self, cache_instance, debug=False):
        """ :type cache_instance: django.core.cache.backends.locmem.LocMemCache|dict"""
        self._debug = debug
        self._cache = cache_instance
        self._timeouts = {}

    @property
    def is_dict(self):
        return isinstance(self._cache, dict)

    @property
    def is_locmem(self):
        return isinstance(getattr(self._cache, '_cache', None), collections.MutableMapping)

    @property
    def is_memcache(self):
        try:
            # noinspection PyUnresolvedReferences
            from memcache import Client
        except ImportError:
            return False

        return isinstance(getattr(self._cache, '_cache', None), Client)

    @property
    def is_pylibmc(self):
        try:
            # noinspection PyUnresolvedReferences
            from pylibmc import Client
        except ImportError:
            return False

        return isinstance(getattr(self._cache, '_cache', None), Client)

    @property
    def is_redis(self):
        try:
            # noinspection PyUnresolvedReferences
            from django_redis.client import DefaultClient
        except ImportError:
            return False
        return isinstance(getattr(self._cache, 'client', None), DefaultClient)

    def __getattribute__(self, item):
        value = object.__getattribute__(self, item)
        if callable(value) and self._debug:
            return MethodProxy(item, value, self)
        return value

    def set(self, key, value, timeout=DEFAULT_TIMEOUT):
        self._timeouts[key] = timeout

        if timeout is DEFAULT_TIMEOUT:
            timeout = None
        if self.is_dict:
            self._cache[key] = value
        else:
            self._cache.set(key, value, timeout)

    def get(self, key, default=None):
        return self._cache.get(key, default)

    def delete(self, key):
        if self.is_dict:
            if key in self._cache:
                del self._cache[key]
                del self._timeouts[key]
        else:
            del self._timeouts[key]
            self._cache.delete(key)

    def set_many(self, data, timeout=DEFAULT_TIMEOUT):
        self._timeouts.update({k: timeout for k in data})

        if timeout is DEFAULT_TIMEOUT:
            timeout = None

        if self.is_dict:
            self._cache.update(data)
        else:
            self._cache.set_many(data, timeout)

    def get_many(self, data):
        if self.is_dict:
            return {k: self.get(k) for k in data if k in self}
        else:
            return self._cache.get_many(data)

    def make_key(self, key, *args, **kwargs):
        if self.is_dict:
            return key
        return self._cache.make_key(key, *args, **kwargs)

    def get_timeout(self, key):
        return self._timeouts[key]

    def clear(self):
        self._cache.clear()
        self._timeouts.clear()

    def search_prefix(self, prefix):
        keys_list = self.get_all_keys()

        actual_prefix = prefix

        if self.is_locmem:
            # using real keys only for locmem cache
            actual_prefix = self.with_key_prefix(force_text(prefix))

        for key in keys_list:
            # force all keys to be unicode, since not all cache backends support it
            key = force_text(key)
            if key.startswith(force_text(actual_prefix)):
                return True
        return False

    def get_all_keys(self):
        if self.is_dict:
            return self._cache.keys()
        elif self.is_locmem:
            return self._cache._cache.keys()
        elif self.is_redis:
            # noinspection PyUnresolvedReferences
            return self._cache.client.keys('*')

        # fallback to saved keys, since there are some different problems
        # when receiving cache keys from memcached:
        # python-memcached - get_stats fails in Python3
        # pylibmc - get_stats does not work as expected
        return self._timeouts.keys()

    def with_key_prefix(self, value=''):
        if self.is_memcache or self.is_pylibmc:
            return self._cache.key_func(value, self._cache.key_prefix, self._cache.version)
        return ''

    def __len__(self):
        if self.is_dict:
            return len(self._cache)
        elif self.is_locmem:
            return len(self._cache._cache)
        elif self.is_memcache or self.is_pylibmc:
            # special case
            keys = self.get_all_keys()
            # prefix = self.with_key_prefix()
            # keys = [k[len(prefix):] for k in keys]
            return len(self._cache.get_many(keys))
        elif self.is_redis:
            return len(self.get_all_keys())
        return 0

    def __contains__(self, item):
        if self.is_dict:
            return item in self._cache
        else:
            return self._cache.has_key(item)

    def __repr__(self):
        name = type(self._cache)
        try:
            from django.core.cache import DEFAULT_CACHE_ALIAS, caches, DefaultCacheProxy
            if isinstance(self._cache, DefaultCacheProxy):
                name = type(caches[DEFAULT_CACHE_ALIAS])
        except Exception:
            pass
        return 'ThreadLocalCache {}'.format(name)


def custom_cache_key(*args, **kwargs):
    return create_cache_key('my_prefix', args[0].id, *args[1:])


def process_args(*args, **kwargs):
    final = list(args)
    for k, v in sorted(kwargs.items()):
        final.append(k)
        final.append(v)

    return ':'.join(force_text(i) for i in final)


def get_test_result(*args, **kwargs):
    result = process_args(*args, **kwargs)
    cache_mock(result)
    return result


def choose_timeout(self, a, b, c):
    if not isinstance(a, int):
        return DEFAULT_TIMEOUT
    return a * 100


# noinspection PyNestedDecorators
class User(object):
    name = 'user_name'
    prefixed_ecached = partial(ecached, prefix='USER:{self.id}', timeout=3600)

    def __init__(self, uid):
        self.id = uid

    @ecached('dyn_timeout:{a}', timeout=choose_timeout)
    def instance_dynamic_timeout(self, a, b, c):
        return get_test_result(a, b, c)

    @ecached()
    def instance_default_cache_key(self, a, b, c=8):
        return get_test_result(a, b, c)

    @ecached()
    @classmethod
    def class_method_default_cache_key(cls, a, b, c=9, d='HAHA'):
        return get_test_result(a, b, c)

    @ecached_property()
    def test_property(self):
        return get_test_result('property')

    @ecached('{self.id}:{a}:{b}:{c}')
    def instance_method_string(self, a, b, c=10):
        return get_test_result(a, b, c)

    @ecached(['self.id', 'a', 'b'])
    def instance_method_list(self, a, b, c=11):
        return get_test_result(a, b, c)

    @ecached(custom_cache_key)
    def instance_method_callable(self, a, b, c=12):
        return get_test_result(a, b, c)

    @ecached('{self.id}:{a}:{b}', 400)
    def instance_method_timeout(self, a, b, c=13):
        return get_test_result(a, b, c)

    @ecached('{self.id}:{a}:{b}', 500, ('tag1', 'tag2'))
    def instance_method_tags(self, a, b, c=14):
        return get_test_result(a, b, c)

    @staticmethod
    def generate_custom_tags(meta):
        """ :type meta: MetaCallable """
        if meta.has_returned_value:
            cache_mock.assert_called_with(meta.returned_value)

        self = meta.args[0]
        a = meta.args[1]
        return [create_cache_key(self.name, self.id, a), 'simple_tag']

    @meta_accepted
    @staticmethod
    def generate_key_based_on_meta(m, a=1):
        assert isinstance(m, MetaCallable)
        assert m.function is getattr(m['self'], 'instance_method_meta_test').function
        assert m.scope is m['self']
        assert a == 1

        return create_cache_key(m['a'], m['b'], m['c'])

    @ecached(generate_key_based_on_meta)
    def instance_method_meta_test(self, a, b, c=666):
        return get_test_result(a, b, c)

    @ecached('{a}:{b}', tags=generate_custom_tags)
    def instance_method_custom_tags(self, a, b, c=14):
        return get_test_result(a, b, c)

    @prefixed_ecached('p1:{a}:{b}:{c}', tags=['{self.id}:tag1'])
    def instance_method_prefixed(self, a, b, c=15):
        return get_test_result(a, b, c)

    @ecached_property('{self.id}:friends_count', timeout=100, prefix='USER_PROPERTY')
    def friends_count(self):
        cache_mock()
        return 15

    @ecached_property('static_key')
    def property_no_tags(self):
        cache_mock()
        return '42'

    @ecached(cache_key='{cls.name}:{c}')
    @classmethod
    def class_method_cache_key_string(cls, a, b, c=17):
        return get_test_result(a, b, c)

    @ecached(('cls.name', 'a'), 500, ['tag4', 'tag5:{cls.name}'],
             prefix=lambda cls, *args, **kwargs: create_cache_key('USER', args[0], args[1]))
    @classmethod
    def class_method_full_spec(cls, a, b, c=18):
        return get_test_result(a, b, c)

    @ecached('{hg}:{hg}:{test}', prefix=u'пользователь')
    @staticmethod
    def static_method(hg, test='abc', n=1.1):
        return get_test_result(hg, test, n)

    @ecached(tags=['ttt:{c}'], prefix='ppp:{b}')
    @staticmethod
    def static_method_default_key(a, b, c=11):
        return get_test_result(a, b, c)


@ecached(timeout=100)
def computation(a, b, c):
    return get_test_result(a, b, c)


@ecached(('kwargs[a]', 'kwargs[b]'), prefix=u'пользователь')
def ordinal_func(*args, **kwargs):
    return get_test_result(*args, **kwargs)


@ecached('second:{c}', timeout=450, tags=['{a}'])
def second_func(a, b, c=100):
    return get_test_result(a, b, c)


class ClassCachedDecoratorTest(TestCase):

    def get_cache_instance(self):
        return CacheProxy({}, DEBUG)

    def setUp(self):
        self.cache = cache_mock
        self.cache.reset_mock()
        self.user = User(random.randint(10, 1000))

        self.local_cache = self.get_cache_instance()
        """ :type local_cache: CacheProxy """
        set_global_cache_instance(self.local_cache)

        assert self.local_cache == get_default_cache_instance()

    def tearDown(self):
        self.local_cache.clear()

    def _check_base(self, method, param_to_change=None):
        self.cache.reset_mock()

        items = [u'тест', 'str', 100, 1.45]
        random.shuffle(items)

        a, b, c = items[:3]

        result = process_args(a, b, c)

        self.assertEqual(method(a, b, c), result)
        self.cache.assert_called_once_with(result)
        self.cache.reset_mock()

        # cached version (force convert to unicode)
        self.assertEqual(force_text(method(a, b, c)), force_text(result))
        self.assertFalse(self.cache.called)
        self.cache.reset_mock()

        if param_to_change == 'c':
            c = items[3]
        elif param_to_change == 'b':
            b = items[3]
        else:
            a = items[3]

        result = process_args(a, b, c)

        # different params, no cache
        self.assertEqual(method(a, b, c), result)
        self.cache.assert_called_once_with(result)
        self.cache.reset_mock()

    def _check_cache_key(self, _callable, cache_key, *args, **kwargs):
        self.local_cache.clear()
        self.assertNotIn(cache_key, self.local_cache)

        _callable(*args, **kwargs)
        self.assertIn(cache_key, self.local_cache)

        as_property = getattr(_callable, 'property', False)
        if as_property:
            invalidate_cache_key(cache_key)
        else:
            _callable.invalidate_cache_by_key(*args, **kwargs)

        self.assertNotIn(cache_key, self.local_cache)
        _callable(*args, **kwargs)

    def _check_cache_prefix(self, _callable, prefix, *args, **kwargs):
        self.local_cache.clear()
        self.cache.reset_mock()

        as_property = getattr(_callable, 'property', False)

        tag_prefix = create_tag_cache_key(prefix)
        self.assertNotIn(tag_prefix, self.local_cache)

        result = _callable(*args, **kwargs)
        self.assertIn(tag_prefix, self.local_cache)
        self.assertTrue(self.local_cache.search_prefix(prefix))

        if as_property:
            self.cache.assert_called_once_with()
        else:
            self.cache.assert_called_once_with(result)

        self.cache.reset_mock()

        _callable(*args, **kwargs)
        self.assertFalse(self.cache.called)

        _callable.invalidate_cache_by_prefix(*args, **kwargs)
        result = _callable(*args, **kwargs)

        if as_property:
            self.cache.assert_called_once_with()
        else:
            self.cache.assert_called_once_with(result)

        self.cache.reset_mock()

    def _check_timeout(self, cache_key, timeout):
        assert cache_key in self.local_cache, '_check_cache_key required to use this method'
        self.assertEqual(self.local_cache.get_timeout(cache_key), timeout)

    def _check_tags(self, _callable, tags, *args, **kwargs):
        self.local_cache.clear()
        self.cache.reset_mock()

        for tag in tags:
            self.assertNotIn(create_tag_cache_key(tag), self.local_cache)

        result = _callable(*args, **kwargs)

        for tag in tags:
            self.assertIn(create_tag_cache_key(tag), self.local_cache)

        self.cache.assert_called_once_with(result)
        self.cache.reset_mock()

        # invalidate by tag
        for tag in tags:
            invalidate_cache_tags(tag)
            result = _callable(*args, **kwargs)
            self.cache.assert_called_once_with(result)
            self.cache.reset_mock()

            _callable(*args, **kwargs)
            self.assertFalse(self.cache.called)

            _callable.invalidate_cache_by_tags(tag, *args, **kwargs)
            result = _callable(*args, **kwargs)
            self.cache.assert_called_once_with(result)
            self.cache.reset_mock()

    def test_default_cache_key(self):
        cache_callable = self.user.instance_default_cache_key
        cache_key = create_cache_key(
            __name__ + '.User.instance_default_cache_key', 1, 2, 8
        )
        self._check_base(cache_callable)
        self._check_cache_key(cache_callable, cache_key, 1, 2)
        self._check_timeout(cache_key, DEFAULT_TIMEOUT)

        cache_callable = User.class_method_default_cache_key
        cache_key = create_cache_key(
            __name__ + '.User.class_method_default_cache_key', 2, 3, 9, 'HAHA'
        )

        self._check_base(cache_callable)
        self._check_cache_key(cache_callable, cache_key, 2, 3)
        self._check_timeout(cache_key, DEFAULT_TIMEOUT)

        cache_callable = computation
        cache_key = create_cache_key(
            __name__ + '.computation', 'a', 'b', 'c'
        )

        self._check_base(cache_callable)
        self._check_cache_key(cache_callable, cache_key, 'a', 'b', 'c')
        self._check_timeout(cache_key, 100)

    def test_default_cache_key_for_property(self):
        self.assertEqual(self.user.test_property, 'property')

        cache_callable = lambda: getattr(self.user, 'test_property')
        cache_callable.property = True

        cache_key = create_cache_key(__name__ + '.User.test_property')

        self._check_cache_key(cache_callable, cache_key)

        self.local_cache.clear()
        self.cache.reset_mock()

        self.assertEqual(self.user.test_property, 'property')
        self.cache.assert_called_once_with('property')

        self.cache.reset_mock()
        self.assertEqual(self.user.test_property, 'property')
        self.assertFalse(self.cache.called)

        # invalidate cache
        User.test_property.invalidate_cache_by_key()
        self.assertEqual(self.user.test_property, 'property')
        self.cache.assert_called_once_with('property')

    def test_cache_key_as_string(self):
        cache_callable = self.user.instance_method_string
        cache_key = create_cache_key(self.user.id, 1, 2, 3)

        self._check_base(self.user.instance_method_string)
        self._check_cache_key(cache_callable, cache_key, 1, 2, c=3)
        self._check_timeout(cache_key, DEFAULT_TIMEOUT)
        self.assertEqual(len(self.local_cache), 1)

    def test_cache_key_as_list(self):
        cache_callable = self.user.instance_method_list
        cache_key = create_cache_key(self.user.id, 2, 3)

        self._check_base(cache_callable)
        self._check_cache_key(cache_callable, cache_key, 2, 3)
        self._check_timeout(cache_key, DEFAULT_TIMEOUT)

    def test_cache_key_as_list_unrelated_param_changed(self):
        # if we change only "c" parameter - data will be received from cache
        a = b = c = 10
        result = process_args(a, b, c)
        self.assertEqual(self.user.instance_method_list(a, b, c), result)
        self.cache.assert_called_once_with(result)
        self.cache.reset_mock()

        # still cached version
        self.assertEqual(self.user.instance_method_list(a, b, c + 10), result)
        self.assertFalse(self.cache.called)
        self.cache.reset_mock()

    def test_cache_key_as_callable(self):
        cache_callable = self.user.instance_method_callable
        cache_key = custom_cache_key(self.user, 5, 5)

        self._check_base(cache_callable)
        self._check_cache_key(cache_callable, cache_key, 5, 5)
        self._check_timeout(cache_key, DEFAULT_TIMEOUT)

    def test_not_default_timeout(self):
        cache_callable = self.user.instance_method_timeout
        cache_key = create_cache_key(self.user.id, 5, 5)

        self._check_base(cache_callable)
        self._check_cache_key(cache_callable, cache_key, 5, 5)
        self._check_timeout(cache_key, 400)

    def test_cache_tags(self):
        cache_callable = self.user.instance_method_tags
        cache_key = create_cache_key(self.user.id, 5, 5)

        self._check_base(cache_callable)
        self._check_cache_key(cache_callable, cache_key, 5, 5)
        self._check_timeout(cache_key, 500)
        self._check_tags(cache_callable, ['tag1', 'tag2'], 6, 7)

    def test_cache_custom_tags(self):
        cache_callable = self.user.instance_method_custom_tags
        cache_key = create_cache_key(10, 11)
        cache_tags = self.user.generate_custom_tags(MetaCallable(args=(self.user, 10)))

        self._check_cache_key(cache_callable, cache_key, 10, 11)
        self._check_tags(cache_callable, cache_tags, 10, 11)

    def test_method_prefixed(self):
        cache_callable = self.user.instance_method_prefixed
        cache_prefix = create_cache_key('USER', self.user.id)

        # prefix should ba attached
        cache_key = create_cache_key(cache_prefix, 'p1', 1, 2, 3)

        self._check_base(cache_callable)
        self._check_cache_key(cache_callable, cache_key, 1, 2, 3)
        self._check_timeout(cache_key, 3600)

        # prefix is a tag actually
        self._check_cache_prefix(cache_callable, cache_prefix, 1, 2, 3)
        self._check_tags(cache_callable, [create_cache_key(self.user.id, 'tag1')], 1, 2, 3)

    def test_property_friends_count(self):
        self.assertEqual(self.user.friends_count, 15)

        cache_callable = lambda: getattr(self.user, 'friends_count')
        cache_callable.property = True
        cache_callable.invalidate_cache_by_prefix = User.friends_count.invalidate_cache_by_prefix

        cache_prefix = 'USER_PROPERTY'
        cache_key = create_cache_key(cache_prefix, self.user.id, 'friends_count')

        self._check_cache_key(cache_callable, cache_key)
        self._check_timeout(cache_key, 100)
        # noinspection PyTypeChecker
        self._check_cache_prefix(cache_callable, cache_prefix)

    def test_property_no_tags(self):
        self.assertEqual(self.user.property_no_tags, '42')

        cache_callable = lambda: getattr(self.user, 'property_no_tags')
        cache_callable.property = True
        cache_key = create_cache_key('static_key')

        self._check_cache_key(cache_callable, cache_key)

    def test_class_method_key_string(self):
        cache_callable = User.class_method_cache_key_string
        cache_key = create_cache_key(User.name, 17)

        self._check_base(cache_callable, param_to_change='c')
        self._check_cache_key(cache_callable, cache_key, 1, 2)
        self._check_timeout(cache_key, DEFAULT_TIMEOUT)

        cache_callable = self.user.class_method_cache_key_string
        self._check_base(cache_callable, param_to_change='c')
        self._check_cache_key(cache_callable, cache_key, 4, 5)

    def test_class_method_full_spec(self):
        cache_callable = User.class_method_full_spec
        a = u'a'
        b = u'b'
        c = 10

        cache_prefix = create_cache_key('USER', a, b)
        cache_key = create_cache_key(cache_prefix, User.name, a)

        self._check_base(cache_callable)
        self._check_cache_key(cache_callable, cache_key, a, b, c)
        self._check_timeout(cache_key, 500)
        self._check_tags(
            cache_callable,
            ['tag4', create_cache_key(u'tag5', User.name)],
            a, b, c
        )
        self._check_cache_prefix(cache_callable, cache_prefix, a, b, c)

    def test_static_method(self):
        cache_callable = User.static_method
        hg = 123
        test = u'ЫЫЫЫ'

        cache_prefix = cache_callable.prefix
        cache_key = create_cache_key(cache_prefix, hg, hg, test)

        self._check_base(cache_callable)
        self._check_cache_key(cache_callable, cache_key, hg, test)
        self._check_timeout(cache_key, DEFAULT_TIMEOUT)
        self._check_cache_prefix(cache_callable, cache_prefix, hg, test)

    def test_static_method_default_key(self):
        cache_callable = User.static_method_default_key
        cache_prefix = create_cache_key('ppp', 2)
        cache_key = create_cache_key(
            cache_prefix, __name__ + '.User.static_method_default_key', 1, 2, 11
        )

        self._check_base(cache_callable, param_to_change='b')
        self._check_cache_key(cache_callable, cache_key, a=1, b=2)

        # check partial invalidation
        self.cache.reset_mock()
        cache_callable(1, 2, 3)
        self.assertTrue(self.cache.called)

        self.cache.reset_mock()
        cache_callable(1, 2, 3)
        self.assertFalse(self.cache.called)

        self.cache.reset_mock()
        cache_callable.invalidate_cache_by_tags(c=3)
        cache_callable(1, 2, 3)
        self.assertTrue(self.cache.called)

        self.cache.reset_mock()
        cache_callable.invalidate_cache_by_prefix(b=2)
        cache_callable(1, 2, 3)
        self.assertTrue(self.cache.called)

        self.cache.reset_mock()
        cache_callable.invalidate_cache_by_key(1, b=2, c=3)
        cache_callable(1, 2, 3)
        self.assertTrue(self.cache.called)

    def test_ordinal_func(self):
        cache_callable = ordinal_func
        cache_prefix = ordinal_func.prefix
        cache_key = create_cache_key(cache_prefix, 10, 20)

        self.cache.reset_mock()

        result = process_args(a=10, b=10)

        self.assertEqual(cache_callable(a=10, b=10), result)
        self.cache.assert_called_once_with(result)
        self.cache.reset_mock()

        # cached version
        self.assertEqual(cache_callable(a=10, b=10), result)
        self.assertFalse(self.cache.called)
        self.cache.reset_mock()

        result = process_args(a=10, b=22)

        # different params, no cache
        self.assertEqual(cache_callable(a=10, b=22), result)
        self.cache.assert_called_once_with(result)
        self.cache.reset_mock()

        self._check_cache_key(cache_callable, cache_key, a=10, b=20)
        self._check_cache_prefix(cache_callable, cache_prefix, a=10, b=20)

    def test_second_func(self):
        cache_callable = second_func
        cache_key = create_cache_key('second', 100)

        self._check_base(cache_callable, param_to_change='c')
        self._check_cache_key(cache_callable, cache_key, 1, 2, c=100)
        self._check_timeout(cache_key, 450)
        self._check_tags(cache_callable, ['yyy'], 'yyy', 111)

    def test_invalidators(self):
        a, b = u'a', u'b'
        cache_callable = ordinal_func
        cache_prefix = ordinal_func.prefix
        cache_key = create_cache_key(cache_prefix, a, b)

        self.cache.reset_mock()

        result = process_args(a=a, b=b)

        self.assertEqual(cache_callable(a=a, b=b), result)
        self.cache.assert_called_once_with(result)
        self.cache.reset_mock()

        # cached version
        self.assertEqual(cache_callable(a=a, b=b), result)
        self.assertFalse(self.cache.called)
        self.cache.reset_mock()

        # invalidate cache via cache key
        invalidate_cache_key(cache_key)
        self.assertEqual(cache_callable(a=a, b=b), result)
        self.cache.assert_called_once_with(result)
        self.cache.reset_mock()

        # cached version
        self.assertEqual(cache_callable(a=a, b=b), result)
        self.assertFalse(self.cache.called)
        self.cache.reset_mock()

        # invalidate cache via prefix
        invalidate_cache_prefix(cache_prefix)
        self.assertEqual(cache_callable(a=a, b=b), result)
        self.cache.assert_called_once_with(result)
        self.cache.reset_mock()

        # cached version
        self.assertEqual(cache_callable(a=a, b=b), result)
        self.assertFalse(self.cache.called)
        self.cache.reset_mock()

        # invalidate cache via attached invalidator
        cache_callable.invalidate_cache_by_key(a=a, b=b)
        self.assertEqual(cache_callable(a=a, b=b), result)
        self.cache.assert_called_once_with(result)
        self.cache.reset_mock()

    def test_instance_method_and_meta_accepted_decorator(self):
        cache_callable = self.user.instance_method_meta_test

        cache_key = create_cache_key(1, 2, 5)

        self._check_base(cache_callable)
        self._check_cache_key(cache_callable, cache_key, 1, 2, c=5)
        self._check_timeout(cache_key, DEFAULT_TIMEOUT)
        self.assertEqual(len(self.local_cache), 1)

    def test_instance_method_dynamic_timeout(self):
        cache_callable = self.user.instance_dynamic_timeout

        self._check_base(cache_callable)

        cache_key = create_cache_key('dyn_timeout', 2)
        self._check_cache_key(cache_callable, cache_key, 2, 3, 4)
        self._check_timeout(cache_key, 2 * 100)

        self.cache.reset_mock()

        cache_key = create_cache_key('dyn_timeout', 4)
        self._check_cache_key(cache_callable, cache_key, 4, 5, 6)
        self._check_timeout(cache_key, 4 * 100)


# Django-related part
from django.conf import settings
from django.test import SimpleTestCase
from django.test.utils import override_settings

settings.configure(
    DEBUG=True,
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:'
        }
    },
    ROOT_URLCONF='',
    INSTALLED_APPS=()
)


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'locmem',
            'KEY_PREFIX': 'custom_prefix',
        }
    }
)
class DjangoLocMemCacheTest(ClassCachedDecoratorTest, SimpleTestCase):
    """ Uses django LocMem cache """

    def get_cache_instance(self):
        from django.core.cache import cache
        return CacheProxy(cache, DEBUG)


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
            'LOCATION': MEMCACHED_HOST,
            'KEY_PREFIX': 'memcached',
        }
    }
)
class LiveMemcachedTest(DjangoLocMemCacheTest):
    """ Uses local memcached instance as cache backend """


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.memcached.PyLibMCCache',
            'LOCATION': MEMCACHED_HOST,
            'KEY_PREFIX': 'pylibmc',
        }
    }
)
class LivePyLibMCTest(DjangoLocMemCacheTest):
    """ Uses local memcached instance as cache backend """


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': 'redis://{}/1'.format(REDIS_HOST),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }
)
class LiveRedisTest(DjangoLocMemCacheTest):
    """ Uses local redis instance and django-redis as cache backend """


class MiscellaneousTest(TestCase):

    @skipIf(six.PY3, 'This test should only be executed in Python 2')
    def test_class_repr_py2(self):
        self.assertEqual(
            repr(User.class_method_full_spec),
            '<TaggedCached: '
            'callable="' + __name__ + '.User.class_method_full_spec", '
            'cache_key="{cls.name}:{a}", tags="[\'tag4\', \'tag5:{cls.name}\']", '
            'prefix="' + __name__ + '.<lambda>", timeout=500>'
        )

        self.assertEqual(
            repr(User.class_method_default_cache_key),
            '<Cached: '
            'callable="' + __name__ + '.User.class_method_default_cache_key", '
            'cache_key="easy_cache.core.Cached.create_cache_key", timeout=DEFAULT_TIMEOUT>'
        )

        self.assertEqual(
            repr(User.static_method),
            '<TaggedCached: '
            'callable="' + __name__ + '.User.static_method", '
            'cache_key="{hg}:{hg}:{test}", tags="()", '
            'prefix="пользователь", timeout=DEFAULT_TIMEOUT>'
        )

        self.assertEqual(
            repr(User.property_no_tags),
            '<Cached: '
            'callable="' + __name__ + '.User.property_no_tags", '
            'cache_key="static_key", timeout=DEFAULT_TIMEOUT>'
        )

        self.assertEqual(
            repr(User.instance_method_custom_tags),
            '<TaggedCached: '
            'callable="' + __name__ + '.User.instance_method_custom_tags", '
            'cache_key="{a}:{b}", tags="' + __name__ + '.generate_custom_tags", '
            'prefix="None", timeout=DEFAULT_TIMEOUT>'
        )

        self.assertEqual(
            repr(ordinal_func),
            '<TaggedCached: '
            'callable="' + __name__ + '.ordinal_func", '
            'cache_key="{kwargs[a]}:{kwargs[b]}", tags="()", '
            'prefix="пользователь", timeout=DEFAULT_TIMEOUT>'
        )

    @skipIf(six.PY2, 'This test should only be executed in Python 3')
    def test_class_repr_py3(self):
        self.assertEqual(
            repr(User.class_method_full_spec),
            '<TaggedCached: '
            'callable="' + __name__ + '.User.class_method_full_spec", '
            'cache_key="{cls.name}:{a}", tags="[\'tag4\', \'tag5:{cls.name}\']", '
            'prefix="' + __name__ + '.User.<lambda>", timeout=500>'
        )

        self.assertEqual(
            repr(User.class_method_default_cache_key),
            '<Cached: '
            'callable="' + __name__ + '.User.class_method_default_cache_key", '
            'cache_key="easy_cache.core.Cached.create_cache_key", timeout=DEFAULT_TIMEOUT>'
        )

        self.assertEqual(
            repr(User.static_method),
            '<TaggedCached: '
            'callable="' + __name__ + '.User.static_method", '
            'cache_key="{hg}:{hg}:{test}", tags="()", '
            'prefix="пользователь", timeout=DEFAULT_TIMEOUT>'
        )

        self.assertEqual(
            repr(User.property_no_tags),
            '<Cached: '
            'callable="' + __name__ + '.User.property_no_tags", '
            'cache_key="static_key", timeout=DEFAULT_TIMEOUT>'
        )

        self.assertEqual(
            repr(User.instance_method_custom_tags),
            '<TaggedCached: '
            'callable="' + __name__ + '.User.instance_method_custom_tags", '
            'cache_key="{a}:{b}", tags="' + __name__ + '.User.generate_custom_tags", '
            'prefix="None", timeout=DEFAULT_TIMEOUT>'
        )

        self.assertEqual(
            repr(ordinal_func),
            '<TaggedCached: '
            'callable="' + __name__ + '.ordinal_func", '
            'cache_key="{kwargs[a]}:{kwargs[b]}", tags="()", '
            'prefix="пользователь", timeout=DEFAULT_TIMEOUT>'
        )
