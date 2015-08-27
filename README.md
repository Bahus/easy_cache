# Easy caching decorators

This package is intended to simplify caching and invalidation process in python-based (primarily) web applications. It's possible to cache execution results of functions; *instance*, *class* and *static* methods; properties. Cache keys may be constructed in various different ways and may depend on any number of parameters.

The package supports tag-based cache invalidation and better works with Django, however any other frameworks can be used – see examples below.

# Requirements

Library was tested in the following environments:
 * Python 2.7, 3.4
 * Django 1.7, 1.8

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

def time_consuming_operation(count):
    cache_key = 'time_consuming_operation_{}'.format(count)
    result = cache.get(cache_key, None)

    if result is None:
        # not found in cache
        result = sum(range(count))
        cache.set(cache_key, result, 3600)

    return result

def invalidate_cache(count):
    cache.delete('time_consuming_operation_{}'.format(count))
```

Now let's take a look how `easy_cache` can help:

```python
# easy way
from easy_cache import ecached

@ecached('time_consuming_operation_{count}', 3600)
def time_consuming_operation(count):
    return sum(range(count))

def invalidate_cache(count):
    time_consuming_operation.invalidate_cache_by_args(count)
```

Heart of the package is two decorators with the similar parameters:

### ecached

Should be used to decorate any callable and cache returned result.

Parameters:

 * `cache_key` – cache key generator, default value is `None` so the key will be composed automatically based on function name and namespace. Also supports the following parameter types:
   * **string** – can contain [Python advanced string formatting syntax](https://docs.python.org/2/library/string.html#formatstrings), later this value will be formatted with dict of parameters provided to decorated function, see examples below.
   * **sequence of strings** – each string must be function parameter name.
   * **callable** – decorated function parameters will be passed to this callable and returned cache key will be used. Only two possible callable signatures are supported: callable(\*args, \*\*kwargs) and callable(meta), where `meta` is
   dict-like object with some additional fields – see examples.
 * `timeout` – value will be cached with provided timeout, basically it should be number of seconds, however it depends on cache backend type. Default value is `DEFAULT_VALUE` – internal constant means that actually no value is provided to cache backend and thus backend should decide what timeout to use.
 * `tags` – sequence of strings or callable. Should provide or return list of tags added to cached value, so cache may be invalidated later with any tag name. Tag may support advanced string formatting syntax. See `cache_key` docs and examples for more details.
 * `prefix` – this parameter works both: as regular tag and also as cache key prefix, as usual advanced string formatting and callable are supported here.
 * `cache_alias` – cache backend alias name, it can also be [Django cache backend alias  name](https://docs.djangoproject.com/en/1.8/ref/settings/#std:setting-CACHES).
 * `cache_instance` – cache backend instance may be provided directly via this parameter.

### ecached_property

 Should be used to create so-called cached properties, signature exactly the same as for `ecached`.

# Examples

Code examples is the best way to show power of the package.
Decorator can be simply used with default parameters only:

```python
from easy_cache import ecached

# default parameters, cache key will be generated automatically:
# <__module__>.<__class__>.<function name> + function parameters
# timeout will be default for specified cache backend
# "default" cache backend will be used if you use Django
@ecached()
def time_consuming_operation(*args, **kwargs):
    pass

# simple static cache key
@ecached('time_consuming_operation')
def time_consuming_operation():
    pass

# cache key with advanced string formatting syntax
@ecached('key:{kwargs[param1]}:{kwargs[param2]}:{args[0]}')
def time_consuming_operation(*args, **kwargs):
    pass

# use specific cache alias
from functools import partial

memcached = partial(ecached, cache_alias='memcached')

@memcached(['a', 'b'], timeout=600)
def time_consuming_operation(a, b, c='default'):
    pass

# working with `meta` object
def custom_cache_key(meta):
    return '{}:{}'.format(meta['self'].id, meta['a'])

class A(object):
    id = 1

    @ecached(custom_cache_key)
    def time_consuming_operation(self, a, b, c=10, d=20):
        pass

```

More complex examples introducing Django models and effective tags usage.

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

    @staticmethod
    def get_books_tags(meta):
        """
            Add one tag for every book in function response
        """
        # yes, it may occupy a lot of cache keys
        if not meta.has_returned_value:
            return []

        favorite_books = meta.returned_value
        return [create_cache_key('book', book.pk) for book in favorite_books]

    @ecached('user_favorite_books:{self.id}', 600, get_books_tags)
    def get_favorite_books(self):
        """
            Caches list of related books by user id. So in code you will use:

            >> favorite_books = request.user.get_favorite_books() # cached for user

            You may want to invalidate this cache in two cases:

            1. User adds new book to favorites:
                >> from easy_cache import invalidate_cache_key, create_cache_key
                >> invalidate_cache_key(create_cache_key('user_favorite_books', user.id))
                or
                >> invalidate_cache_key('user_favorite_books:{}'.format(user.id))
            2. Some information about favorite book was changed, e.g. its title:
                >> from easy_cache import invalidate_cache_tags, create_tag_cache_key
                >> invalidate_cache_tags(create_tag_cache_key('book', changed_book_id))
        """
        return self.favorite_books.filter(user=self)

    @ecached('users_by_state:{state}', 60, ['users_by_states'])
    @classmethod
    def get_users_by_state(cls, state):
        """
            Caches user list by provided state parameter: there will be separate
            cached value for every different state parameter. Note that `ecached` decorator
            always comes topmost.

            To invalidate concrete cached state call the following method
            with required `state`, e.g.:
            >> User.get_users_by_state.invalidate_cache_by_args('active')

            If you'd like to invalidate all caches for all states call:
            >> User.get_users_by_state.invalidate_cache_by_tags('users_by_states')

            `invalidate_cache_by_tags` supports both string and list parameter types.
        """
        return cls.objects.filter(state=state)

    @ecached()
    @staticmethod
    def get_books_group_by_users():
        return {
            user: user.favorite_books.all() for user in
            User.objects.prefetch_related('favorite_books')
        }

    @ecached_property(timeout=3600)
    def friends_count(self):
        """
            Caches friends count for 1 hour.

            To invalidate cache call the following method:
            >> User.friends_count.invalidate_cache_by_args()

            Note that class object is used here instead of the instance.
        """
        return self.friends.count()
```

# Performance

TBA
