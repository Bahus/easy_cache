# -*- coding: utf-8 -*-
import json
from easy_cache import create_cache_key
from easy_cache.abc import AbstractCacheInstance
from easy_cache.compat import force_text, force_binary
from easy_cache.core import DEFAULT_TIMEOUT, NOT_FOUND


class RedisCacheInstance(AbstractCacheInstance):
    """Redis cache instance compatible with easy_cache.

    Instance of Redis or StrictRedis instance must be passed to init.
    See: https://pypi.python.org/pypi/redis
    """
    def __init__(self, redis, prefix=None, serializer=json):
        self.client = redis
        self.prefix = prefix
        self.serializer = serializer

    def make_key(self, key):
        if not self.prefix:
            return key
        return create_cache_key(self.prefix, key)

    def load_value(self, value):
        if isinstance(value, bytes):
            value = force_text(value)
        elif value is None:
            return value
        return self.serializer.loads(value)

    # noinspection PyMethodMayBeStatic
    def dump_value(self, value):
        if isinstance(value, bytes):
            return value

        return force_binary(self.serializer.dumps(value))

    def make_keys(self, keys):
        return [self.make_key(key) for key in keys]

    def get_many(self, keys):
        """
        :rtype dict:
        """
        return dict(
            zip(
                keys,
                map(self.load_value, self.client.mget(self.make_keys(keys)))
            )
        )

    def set(self, key, value, timeout=DEFAULT_TIMEOUT):
        """
            :param timeout: must be in seconds
        """
        if timeout is DEFAULT_TIMEOUT:
            timeout = None

        return self.client.set(
            self.make_key(key),
            self.dump_value(value),
            ex=timeout
        )

    def set_many(self, data_dict, timeout=DEFAULT_TIMEOUT):
        """
            :param timeout: must be in seconds
        """
        if timeout is DEFAULT_TIMEOUT:
            timeout = None

        pipe = self.client.pipeline()
        pipe.mset(
            {self.make_key(key): self.dump_value(value)
             for key, value in iter(data_dict.items())}
        )

        if timeout:
            for key in data_dict:
                pipe.expire(self.make_key(key), timeout)

        return pipe.execute()

    def delete(self, key):
        return self.client.delete(self.make_key(key))

    def get(self, key, default=NOT_FOUND):
        result = self.client.get(self.make_key(key))
        return default if result is None else self.load_value(result)
