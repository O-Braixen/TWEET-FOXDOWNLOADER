# -*- coding: utf-8 -*-
"""Registro dos adapters de plataforma disponíveis."""

from .twitter import TwitterAdapter
from .pixiv import PixivAdapter
from .pinterest import PinterestAdapter

ADAPTERS = [TwitterAdapter, PixivAdapter, PinterestAdapter]
