# -*- coding: utf-8 -*-
"""Modelo de dados normalizado para mídias de qualquer plataforma."""

from dataclasses import dataclass, field
from typing import Literal, Optional

MediaType = Literal["photo", "video", "gif"]


@dataclass
class MediaItem:
    """Uma única mídia a ser baixada (imagem, vídeo ou gif)."""

    source_id: str
    media_type: MediaType
    url: Optional[str] = None
    index: int = 0
    date: Optional[str] = None
    referer: Optional[str] = None
    extra: dict = field(default_factory=dict)
