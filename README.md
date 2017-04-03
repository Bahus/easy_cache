# Easy caching decorators

[![Build Status](https://travis-ci.org/Bahus/easy_cache.svg?branch=master)](https://travis-ci.org/Bahus/easy_cache)

This package is intended to simplify caching and invalidation process in python-based (primarily) web applications. It's possible to cache execution results of functions; *instance*, *class* and *static* methods; properties. Cache keys may be constructed in various different ways and may depend on any number of parameters.

The package supports tag-based cache invalidation and better works with Django, however any other frameworks can be used – see examples below.

# Requirements

Library was tested in the following environments:

 * Python 2.7, 3.5, 3.6
 * Django 1.8, 1.9, 1.10

Feel free to try it in yours, but it's not guaranteed it will work. Submit an issue if you think it should.

# Installation

```
pip install easy_cache
```

# Introduction

### Different ways to cache something

```python
# classic way
from django.core.cache import cache

def time_consuming_operation(n):
    """Calculate sum of number from 1 to provided n"""
    cache_key = 'time_consuming_operation_{}'.format(n)
    result = cache.get(cache_key, None)

    if result is None:
        # not found in cache
        result = sum(range(n + 1))
        # cache result for one hour
        cache.set(cache_key, result, 3600)

    return result

def invalidate_cache(n):
    cache.delete('time_consuming_operation_{}'.format(n))
```

Now let's take a look how `easy_cache` can help:

```python
# easy way
from easy_cache import ecached

@ecached('time_consuming_operation_{n}', 3600)
def time_consuming_operation(n):
    return sum(range(n + 1))

def invalidate_cache(n):
    time_consuming_operation.invalidate_cache_by_key(n)
```

Heart of the package is two decorators with the similar parameters:

### ecached

Should be used to decorate any callable and cache returned result.

Parameters:

 * `cache_key` – cache key generator, default value is `None` so the key will be composed automatically based on function name, namespace and passed parameters. Also supports the following parameter types:
   * **string** – may contain [Python advanced string formatting syntax](https://docs.python.org/2/library/string.html#formatstrings), later this value will be formatted with dict of parameters provided to decorated function, see examples below.
   * **sequence of strings** – each string must be function parameter name.
   * **callable** – used to generate cache key, decorated function parameters will be passed to this callable and returned value will be used. Also one additional signature is available: `callable(meta)`, where `meta` is
   dict-like object with some additional attributes – see below.

 * `timeout` – value will be cached with provided timeout, basically it should be number of seconds, however it depends on cache backend type. Default value is `DEFAULT_VALUE` – internal constant means that actually no value is provided to cache backend and thus backend should decide what timeout to use. Callable is also supported.
 * `tags` – sequence of strings or callable. Should provide or return list of tags added to cached value, so cache may be invalidated later with any tag name. Tag may support advanced string formatting syntax. See `cache_key` docs and examples for more details.
 * `prefix` – this parameter works both: as regular tag and also as cache key prefix, as usual advanced string formatting and callable are supported here.
 * `cache_alias` – cache backend alias name, it can also be [Django cache backend alias  name](https://docs.djangoproject.com/en/1.10/ref/settings/#std:setting-CACHES).
 * `cache_instance` – cache backend instance may be provided directly via this parameter.

### ecached_property

 Should be used to create so-called cached properties, has signature exactly the same as for `ecached`.

# Simple examples

Code examples is the best way to show the power of this package.

### Decorators can be simply used with default parameters only

```python
from easy_cache import ecached, create_cache_key

# default parameters
# cache key will be generated automatically:
#
# <__module__>.<__class__>.<function name> + function parameters converted to strings,
#
# so be careful when using complex objects, it's
# better to write custom cache key generator in such cases.
#
# timeout will be default for specified cache backend
# "default" cache backend will be used if you use Django
@ecached()
def time_consuming_operation(*args, **kwargs):
    pass

# simple static cache key and cache timeout 100 seconds
@ecached('time_consuming_operation', 100)
def time_consuming_operation():
    pass

# cache key with advanced string formatting syntax
@ecached('key:{kwargs[param1]}:{kwargs[param2]}:{args[0]}')
def time_consuming_operation(*args, **kwargs):
    pass

# use specific cache alias, see "caches framework" below
from functools import partial

memcached = partial(ecached, cache_alias='memcached')

# equivalent to cache_key='{a}:{b}'
@memcached(['a', 'b'], timeout=600)
def time_consuming_operation(a, b, c='default'):
    pass
```

### Using custom cache key generators

```python
# working with parameters provided to cached function
# cache key generator must have the same signature as decorated function
def custom_cache_key(self, a, b, c, d):
    return create_cache_key(self.id, a, d)

# working with `meta` object
def custom_cache_key_meta(meta):
    return '{}:{}:{}'.format(meta['self'].id, meta['a'], meta['d'])

# or equivalent
from easy_cache import meta_accepted

@meta_accepted
def custom_cache_key_meta(parameter_with_any_name):
    meta = parameter_with_any_name
    return '{}:{}:{}'.format(meta['self'].id, meta['a'], meta['d'])


class A(object):
    id = 1

    @ecached(custom_cache_key)
    def time_consuming_operation(self, a, b, c=10, d=20):
        pass

    @ecached(custom_cache_key_meta)
    def time_consuming_opeartion(self, a, b, c=10, d=20):
        pass
```

### How to cache `staticmethod` and `classmethod` correctly

```python
# ecached decorator always comes topmost
class B(object):

    # cache only for each different year
    @ecached(lambda start_date: 'get_list:{}'.format(start_date.year))
    @staticmethod
    def get_list_by_date(start_date):
        pass

    CONST = 'abc'

    @ecached('info_cache:{cls.CONST}', 3600, cache_alias='redis_cache')
    @classmethod
    def get_info(cls):
        pass
```

### MetaCallable object description

Meta object has the following parameters:

 * `args` – tuple with positional arguments provided to decorated function
 * `kwargs` – dictionary with keyword arguments provided to decorated function
 * `returned_value` – value returned from decorated function, available only
 when meta object is handled in `tags` or `prefix` generators. You have to check `has_returned_value` property before using this parameter:

 ```python
 def generate_cache_key(meta):
     if meta.has_returned_value:
         # ... do something with meta.returned_value ...
 ```

 * `call_args` - dictionary with all positional and keyword arguments provided
 to decorated function, you may also access them via `__getitem__` dict interface, e. g. `meta['param1']`.
 * `function` - decorated callable
 * `scope` - object to which decorated callable is attached, `None` otherwise. Usually it's an instance or a class.

# Tags invalidation and cached properties

More complex examples introducing Django models and effective tags usage.
Check code comments and doc-strings for detailed description.

```python
from django.db import models
from easy_cache import ecached, ecached_property, create_cache_key


class Book(models.Model):
    title = models.CharField(max_length=250)

    def __unicode__(self):
        return self.title


class User(models.Model):
    name = models.CharField(max_length=100)
    state = models.CharField(
        max_length=15,
        choices=(('active', 'active'), ('deleted', 'deleted')),
    )
    friends = models.ManyToManyField('self', symmetrical=True)
    favorite_books = models.ManyToManyField('Book')

    def __unicode__(self):
        return self.name

    @ecached('users_by_state:{state}', 60, ['users_by_states'])
    @classmethod
    def get_users_by_state(cls, state):
        """
            Caches user list by provided state parameter: there will be separate
            cached value for every different state parameter. Note that `ecached`
            decorator always comes topmost.

            To invalidate concrete cached state call the following method
            with required `state`, e.g.:
            >> User.get_users_by_state.invalidate_cache_by_key('active')
            or
            >> User.get_users_by_state.invalidate_cache_by_key(state='active')

            If you'd like to invalidate all caches for all states call:
            >> User.get_users_by_state.invalidate_cache_by_tags('users_by_states')

            `invalidate_cache_by_tags` supports both string and list parameter types.
        """
        return cls.objects.filter(state=state)

    @ecached_property('user_friends_count:{self.id}', timeout=3600)
    def friends_count(self):
        """
            Caches friends count of each user for 1 hour.

            Call the following method, to invalidate cache:
            >> User.friends_count.invalidate_cache_by_key(user)
            or
            >> type(self).friends_count.invalidate_cache_by_key(user)
            or
            >> self.__class__.friends_count.invalidate_cache_by_key(user)

            Where `user` is desired User instance to invalidate friends count of.
            Note that class object is used here instead of the instance.
        """
        return self.friends.count()

    @staticmethod
    def get_books_tags(meta):
        """
            Add one tag for every book in function response
        """
        if not meta.has_returned_value:
            return []

        favorite_books = meta.returned_value
        # yes, it may occupy a lot of cache keys
        return [create_cache_key('book', book.pk) for book in favorite_books]

    @ecached('user_favorite_books:{self.id}', 600, get_books_tags)
    def get_favorite_books(self):
        """
            Caches list of related books by user id. So in code you will use:

            >> favorite_books = request.user.get_favorite_books() # cached for user

            You may want to invalidate this cache in two cases:

            1. User adds new book to favorites:
                >> User.get_favorite_books.invalidate_cache_by_key(user)
                or
                >> User.get_favorite_books.invalidate_cache_by_key(self=user)
                or
                >> from easy_cache import invalidate_cache_key, create_cache_key
                >> invalidate_cache_key(create_cache_key('user_favorite_books', user.id))
                or
                >> invalidate_cache_key('user_favorite_books:{}'.format(user.id))

            2. Some information about favorite book was changed, e.g. its title:
                >> from easy_cache import invalidate_cache_tags, create_tag_cache_key
                >> tag_cache_key = create_tag_cache_key('book', changed_book_id)
                >> User.get_favorite_books.invalidate_cache_by_tags(tag_cache_key)
                or
                >> invalidate_cache_tags(tag_cache_key)
        """
        return self.favorite_books.filter(user=self)


```
# Prefix usage

Commonly `prefix` is used to invalidate all cache-keys in one namespace, e. g.:

```python
from functools import partial

class Shop(models.Model):
    single_shop_cache = partial(ecached, prefix='shop:{self.id}')

    @single_shop_cache('goods_list')
    def get_all_goods_list(self):
        return [...]

    @single_shop_cache('prices_list')
    def get_all_prices_list(self):
        return [...]


# if you have `shop` object you are able to use the following invalidation
# strategies:

# Invalidate cached list of goods for concrete shop
Shop.get_all_goods_list.invalidate_cache_by_key(shop)

# Invalidate cached list of prices for concrete shop
Shop.get_all_prices_list.invalidate_cache_by_key(shop)

# Invalidate all cached items for concrete shop
Shop.get_all_goods_list.invalidate_cache_by_prefix(shop)
# or
Shop.get_all_prices_list.invalidate_cache_by_prefix(shop)
# or
from easy_cache import invalidate_cache_prefix
invalidate_cache_prefix('shop:{self.id}'.format(self=shop))
```

# Invalidation summary

There are two ways to invalidate cache objects: use ivalidation methods bound to
decorated function and separate functions-invalidators.

```python
<decorated>.invalidate_cache_by_key(*args, **kwargs)
<decorated>.invalidate_cache_by_tags(tags=(), *args, **kwargs)
<decorated>.invalidate_cache_by_prefix(*args, **kwargs)

# <decorated> should be used with class instance if it is used in class namespace:
class A:
    @ecached()
    def method(self):
        pass

    @ecached_property()
    def obj_property(self):
        pass

A.method.invalidate_cache_by_key()
# or
A().method.invalidate_cache_by_key()
# only one variant is possible for a property
A.obj_property.invalidate_cache_by_key()

# and
from easy_cache import (
    invalidate_cache_key,
    invalidate_cache_tags,
    invalidate_cache_prefix,
    create_cache_key,
)

# Note that `cache_instance` and `cache_alias` may be passed
# to the following invalidators
invalidate_cache_key(cache_key)
invalidate_cache_tags(tags)
invalidate_cache_prefix(prefix)
```

Here `tags` can be as string (single tag) or list of tags. Bound methods
should be provided with parameters if they are used in cache key/tag/prefix:

```python

@ecached('key:{a}:value:{c}', tags=['tag:{a}'], prefix='pre:{b}', cache_alias='memcached')
def time_consuming_operation(a, b, c=100):
    pass

time_consuming_operation.invalidate_cache_by_key(a=1, c=11)
time_consuming_operation.invalidate_cache_by_tags(a=10)
time_consuming_operation.invalidate_cache_by_prefix(b=2)

# or using `create_cache_key` helper
invalidate_cache_key(
    create_cache_key('key', 1, 'value', 11), cache_alias='memcached'
)
invalidate_cache_tags(create_cache_key('tag', 10), cache_alias='memcached')
invalidate_cache_prefix('pre:{}'.format(2), cache_alias='memcached')
```


# Internal caches framework

Easy-cache uses build-in Django cache framework by default, so you can
choose what cache storage to use on every decorated function, e.g.:

```python
# Django settings
CACHES={
    'local_memory': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'locmem',
        'KEY_PREFIX': 'custom_prefix',
    },
    'memcached': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': '127.0.0.1:11211',
        'KEY_PREFIX': 'memcached',
    }
}

# then in somewhere code
@ecached(..., cache_alias='memcached')
# or
@ecached(..., cache_alias='local_memory')
# or even
from django.core.cache import caches
another_cache = caches['another_cache']
@ecached(..., cache_instance=another_cache)
```

However if you don't use Django, there is cache framework build into
easy-cache package, it may be used in the same fashion as Django caches:

```python
# Custom cache instance class must implement AbstractCacheInstance interface:
from easy_cache.abc import AbstractCacheInstance
from easy_cache.core import DEFAULT_TIMEOUT, NOT_FOUND

class CustomCache(AbstractCacheInstance):

    def get(self, key, default=NOT_FOUND):
        ...

    def get_many(self, keys):
        ...

    def set(self, key, value, timeout=DEFAULT_TIMEOUT):
        ...

    def set_many(self, data_dict, timeout=DEFAULT_TIMEOUT):
        ...

    def delete(self, key):
        ...

from easy_cache import caches

custom_cache = CustomCache()
caches['new_cache'] = custom_cache
caches.set_default(CustomCacheDefault())

# and then
@ecached(..., cache_alias='new_cache')
# or
@ecached(..., cache_instance=custom_cache)
# will use `default` alias
@ecached(...)
```

There is already implemented redis cache instance class, based on [redis-py client](https://pypi.python.org/pypi/redis):

```python
from redis import StrictRedis
from easy_cache.contrib.redis_cache import RedisCacheInstance
from easy_cache import caches

redis_cache = RedisCacheInstance(StrictRedis(host='...', port='...'))
caches.set_default(redis_cache)

# will use `default` alias
@ecached(...)
```

# Dynamic timeout example

You may need to provide cache timeout dynamically depending on
function parameters:

```python
def dynamic_timeout(group):
    if group == 'admins':
        timeout = 10
    else:
        timeout = 100
    return timeout

@ecached('key:{group}', timeout=dynamic_timeout)
def get_users_by_group(group):
    ...
```

# Development and contribution

Live instances of Redis and Memcached are required for few tests to pass, so it's recommended to use docker to setup necessary environment:

```shell
> docker-machine ip default
[IP] <- your DOCKER_HOST ip address

> docker container create --name=easy_cache-redis -p 6379:6379 redis:latest
> docker container start easy_cache-redis

export EASY_CACHE_REDIS_HOST=[IP]:6379

> docker container create --name=easy_cache-memcached -p 11211:11211 memcached:latest
> docker container start easy_cache-memcached

export EASY_CACHE_MEMCACHED_HOST=[IP]:11211

# to enable debug logs
# export EASY_CACHE_DEBUG="yes"

# install package localy
pip install -e .[tests]

# run tests with pytest or tox
pytest
tox
```

# Performance and overhead

Benchmarking may be executed with `tox` command and it shows that decorators give
about 4% of overhead in worst case and about 1-2% overhead on the average.

If you don't use tags or prefix you will get one cache request for
`get` and one request for `set` if result not found in cache, otherwise two
consecutive requests will be made: `get` and `get_many` to receive actual
value from cache and validate its tags (prefix). Then one `set_many` request will be
performed to save a data to cache storage.
