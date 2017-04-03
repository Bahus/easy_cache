# -*- coding: utf-8 -*-
from __future__ import print_function
import io
import os
import sys
import subprocess

from setuptools import setup, find_packages
import versioneer


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


tests_require = [
    'pytest==3.0.4',
    'Django',
    'django-redis==4.2.0',
    'memory-profiler==0.33',
    'mock==1.0.1',
    'psutil==3.1.1',
    'python-memcached==1.57',
    'redis==2.10.3',
    'pylibmc==1.5.0',
    'tox-pyenv==1.0.3',
]


setup(
    name='easy-cache',
    packages=find_packages(exclude=('tests', )),
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description='Useful cache decorators for methods and properties',
    author='Oleg Churkin',
    author_email='bahusoff@gmail.com',
    url='https://github.com/Bahus/easy_cache',
    keywords=['cache', 'decorator', 'invalidation',
              'memcached', 'redis', 'django'],
    platforms='Platform Independent',
    license='MIT',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License'
    ],
    long_description=get_long_description(),
    requires=['six'],
    install_requires=['six'],
    tests_require=tests_require,
    extras_require={
        'tests': tests_require,
    },
)
