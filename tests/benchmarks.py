# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import math
from contextlib import contextmanager
from timeit import default_timer
from redis import StrictRedis

import six
from django.conf import settings
# noinspection PyUnresolvedReferences
from six.moves import xrange

from easy_cache import caches
from easy_cache.contrib.redis_cache import RedisCacheInstance
from easy_cache.decorators import ecached

from tests.conf import REDIS_HOST, MEMCACHED_HOST


settings.configure(
    DEBUG=True,
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:'
        }
    },
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'locmem',
            'KEY_PREFIX': 'custom_prefix',
        },
        'memcached': {
            'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
            'LOCATION': MEMCACHED_HOST,
            'KEY_PREFIX': 'memcached',
        },
        'redis': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': 'redis://{}/1'.format(REDIS_HOST),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    },
    ROOT_URLCONF='',
    INSTALLED_APPS=()
)


# adds custom redis client
redis_host, redis_port = REDIS_HOST.split(':')
caches['redis_client'] = RedisCacheInstance(
    StrictRedis(host=redis_host, port=redis_port),
    prefix='bench'
)


def ratio(a, b):
    if a > b:
        return a / b, 1
    elif a < b:
        return 1, b / a
    else:
        return 1, 1


class Stopwatch(object):

    def __init__(self, name):
        self.name = name
        self.t0 = default_timer()
        self.laps = []

    def __unicode__(self):
        m = self.mean()
        d = self.stddev()
        a = self.median()
        fmt = u'%-37s: mean=%0.5f, median=%0.5f, stddev=%0.5f, n=%3d, snr=%8.5f:%8.5f'
        return fmt % ((self.name, m, a, d, len(self.laps)) + ratio(m, d))

    def __str__(self):
        if six.PY2:
            return six.binary_type(self.__unicode__())
        else:
            return self.__unicode__()

    def mean(self):
        return sum(self.laps) / len(self.laps)

    def median(self):
        return sorted(self.laps)[int(len(self.laps) / 2)]

    def stddev(self):
        mean = self.mean()
        return math.sqrt(sum((lap - mean) ** 2 for lap in self.laps) / len(self.laps))

    def total(self):
        return default_timer() - self.t0

    def reset(self):
        self.t0 = default_timer()
        self.laps = []

    @contextmanager
    def timing(self):
        t0 = default_timer()
        try:
            yield
        finally:
            te = default_timer()
            self.laps.append(te - t0)

c = 0


def time_consuming_operation():
    global c
    c += 1
    a = sum(xrange(1000000))
    return str(a)


def test_no_cache():
    return time_consuming_operation()


@ecached(cache_alias='default')
def test_locmem_cache():
    return time_consuming_operation()


@ecached(cache_alias='memcached')
def test_memcached_cache():
    return time_consuming_operation()


@ecached(cache_alias='redis')
def test_redis_cache():
    return time_consuming_operation()


@ecached(cache_alias='redis_client')
def test_redis_client_cache():
    return time_consuming_operation()


@ecached(cache_alias='default', tags=['tag1', 'tag2'])
def test_locmem_cache_tags():
    return time_consuming_operation()


@ecached(cache_alias='memcached', tags=['tag1', 'tag2'])
def test_memcached_cache_tags():
    return time_consuming_operation()


@ecached(cache_alias='redis', tags=['tag1', 'tag2'])
def test_redis_cache_tags():
    return time_consuming_operation()


@ecached(cache_alias='redis_client', tags=['tag1', 'tag2'])
def test_redis_client_cache_tags():
    return time_consuming_operation()


def main():
    from django import get_version
    import sys

    print('=======', 'Python:', sys.version.replace('\n', ''), 'Django:', get_version(), '=======')

    global c
    n = 100

    benchmarks = (
        (test_no_cache, n),
        (test_locmem_cache, 1),
        (test_locmem_cache_tags, 1),
        (test_memcached_cache, 1),
        (test_memcached_cache_tags, 1),
        (test_redis_cache, 1),
        (test_redis_cache_tags, 1),
        (test_redis_client_cache, 1),
        (test_redis_client_cache_tags, 1),
    )

    def cleanup(function):
        if hasattr(function, 'invalidate_cache_by_key'):
            function.invalidate_cache_by_key()
        if hasattr(function, 'invalidate_cache_by_tags'):
            function.invalidate_cache_by_tags()

    for method, count in benchmarks:
        sw1 = Stopwatch('[cleanup] ' + method.__name__)
        cleanup(method)
        c = 0

        for _ in xrange(n):
            with sw1.timing():
                method()
            cleanup(method)

        assert c == n, c
        print(sw1)

        sw2 = Stopwatch('[ normal] ' + method.__name__)
        cleanup(method)
        c = 0

        for _ in xrange(n):
            # skip first time
            if _ == 0:
                method()
                continue
            with sw2.timing():
                method()

        assert c == count, c
        print(sw2)
        print('mean diff: {:.3} %, median diff: {:.3} %'.format(
            float(sw2.mean()) / sw1.mean() * 100,
            float(sw2.median()) / sw1.median() * 100,
        ))


if __name__ == '__main__':
    main()
