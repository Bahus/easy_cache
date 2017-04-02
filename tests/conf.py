# -*- coding: utf-8 -*-
"""
    Tests configuration options
"""
import os

# forced to be enabled in tests, since we need to change cache instance type dynamically
os.environ['EASY_CACHE_LAZY_MODE_ENABLE'] = 'yes'

# if enabled, you'll see additional logging from cache classes
DEBUG = os.environ.get('EASY_CACHE_DEBUG') == 'yes'

# host:port used in redis-live tests, see readme for docker commands
REDIS_HOST = os.environ.get('EASY_CACHE_REDIS_HOST', '192.168.99.100:6379')

# host:port used in memcached-live tests, see readme for docker commands
MEMCACHED_HOST = os.environ.get('EASY_CACHE_MEMCACHED_HOST', '192.168.99.100:11211')
