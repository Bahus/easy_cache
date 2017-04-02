# -*- coding: utf-8 -*-
import redis
from django.test.utils import override_settings

from easy_cache.contrib.redis_cache import RedisCacheInstance
from easy_cache import caches

from tests.conf import REDIS_HOST
from tests.tests_basic import CacheProxy, DjangoLocMemCacheTest as Base, DEBUG


class RedisCacheProxy(CacheProxy):
    @property
    def is_redis(self):
        return True

    def clear(self):
        self._cache.client.flushall()

    def __contains__(self, item):
        return self._cache.client.exists(item)


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }
)
class RedisCacheInstanceTest(Base):

    def get_cache_instance(self):
        host, port = REDIS_HOST.split(':')
        cache = RedisCacheInstance(redis.StrictRedis(host=host, port=port))
        caches.set_default(cache)
        proxy = RedisCacheProxy(cache, DEBUG)
        return proxy
