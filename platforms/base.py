# -*- coding: utf-8 -*-
"""Contratos base para adapters de plataforma."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from core.models import MediaItem


@dataclass
class Action:
    key: str
    label: str
    folder: str
    fetch: Callable[..., AsyncIterator[MediaItem]]


class PlatformAdapter(ABC):
    name: str = ""
    display_name: str = ""

    def __init__(self, config: dict, history: dict):
        self.config = config
        self.history = history

    @abstractmethod
    async def authenticate(self) -> bool:
        """Autentica e prepara o adapter. Retorna True em caso de sucesso."""

    @abstractmethod
    def actions(self) -> list[Action]:
        """Ações próprias (curtidas, postagens próprias etc.)."""

    async def extra_actions(self) -> list[Action]:
        """Ações opcionais/avançadas (ex.: baixar de outro perfil)."""
        return []

    async def summary(self) -> list[str]:
        """Linhas com estatísticas da conta, exibidas logo após autenticar."""
        return []

    async def close(self) -> None:
        """Libera recursos (clientes HTTP etc.) quando necessário."""
