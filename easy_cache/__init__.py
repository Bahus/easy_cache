# -*- coding: utf-8 -*-

from easy_cache.core import (
    caches,
    create_cache_key,
    create_tag_cache_key,
    invalidate_cache_key,
    invalidate_cache_prefix,
    invalidate_cache_tags,
    get_default_cache_instance,
    set_global_cache_instance,
    set_cache_key_delimiter,
    set_tag_key_prefix,
    MetaCallable,
)

from easy_cache.decorators import ecached, ecached_property
