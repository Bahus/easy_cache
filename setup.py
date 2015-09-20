# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import subprocess

import io
import os
from setuptools import setup


if sys.argv[-1] == 'test':
    # python-mock is required to run unit-tests
    import unittest
    os.environ['EASY_CACHE_LAZY_MODE_ENABLE'] = 'yes'
    unittest.main('easy_cache.tests', argv=sys.argv[:-1])


def get_long_description():
    with io.open('./README.md', encoding='utf-8') as f:
        readme = f.read()
    path = None
    pandoc_paths = ('/usr/local/bin/pandoc', '/usr/bin/pandoc')
    for p in pandoc_paths:
        if os.path.exists(p):
            path = p
            break

    if path is None:
        print('Pandoc not found, tried: {}'.format(pandoc_paths))
        return readme

    cmd = [path, '--from=markdown', '--to=rst']
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    doc = readme.encode('utf8', errors='replace')
    rst = p.communicate(doc)[0]

    if sys.version_info[0] > 2:
        # PY3
        return rst.decode()
    else:
        return rst

setup(
    name='easy-cache',
    packages=['easy_cache'],
    version='0.2.1',
    description='Useful cache decorators for methods and properties',
    author='Oleg Churkin',
    author_email='bahusoff@gmail.com',
    url='https://github.com/Bahus/easy_cache',
    keywords=['cache', 'decorator', 'invalidation',
              'memcached', 'redis', 'django'],
    platforms='Platform Independent',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License'
    ],
    long_description=get_long_description(),
    requires=['six'],
    install_requires=['six'],
    extras_require={
        'tests': [
            'Django==1.8.3',
            'django-redis==4.2.0',
            'memory-profiler==0.33',
            'mock==1.0.1',
            'psutil==3.1.1',
            'python-memcached==1.57',
            'redis==2.10.3',
            'pylibmc==1.5.0',
        ],
    },
)
