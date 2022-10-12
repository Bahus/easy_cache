# -*- coding: utf-8 -*-
import io

from setuptools import setup, find_packages
import versioneer


def get_long_description():
    with io.open('./README.md', encoding='utf-8') as f:
        readme = f.read()
    return readme


tests_require = [
    'pytest',
    'Django',
    'django-redis',
    'memory-profiler',
    'mock',
    'psutil',
    'python-memcached',
    'pymemcache',
    'redis',
    'pylibmc',
    'tox-pyenv',
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
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License'
    ],
    long_description=get_long_description(),
    long_description_content_type='text/markdown',
    tests_require=tests_require,
    extras_require={
        'tests': tests_require,
    },
)
