# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import
from abc import ABCMeta, abstractmethod
import six

from easy_cache.core import DEFAULT_TIMEOUT, NOT_FOUND


@six.add_metaclass(ABCMeta)
class AbstractCacheInstance(object):
    """All custom cache instances (clients) should
    inherit this class.
    """

    @abstractmethod
    def get(self, key, default=NOT_FOUND):
        """
            :type key: str | basestring
            :rtype Any | None
        """
        pass

    @abstractmethod
    def get_many(self, keys):
        """
            :type keys: list | tuple
            :rtype dict:
        """
        pass

    @abstractmethod
    def set(self, key, value, timeout=DEFAULT_TIMEOUT):
        """
            :type key: str | basestring
        """
        pass

    @abstractmethod
    def set_many(self, data_dict, timeout=DEFAULT_TIMEOUT):
        """
            :type data_dict: dict
        """
        pass

    @abstractmethod
    def delete(self, key):
        """
            :type key: str | basestring
        """
        pass
