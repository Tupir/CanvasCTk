from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable, Mapping
from typing import Any


class ListVar(tk.Variable):
    _default = ()

    def __init__(
        self,
        master: Any = None,
        value: Any = None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            master=master,
            value=[] if value is None else value,
            name=name,
        )

    @staticmethod
    def _normalize(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, (str, bytes, Mapping)):
            return [value]
        if isinstance(value, Iterable):
            return list(value)
        return [value]

    def set(self, value: Any) -> None:
        self._tk.globalsetvar(self._name, tuple(self._normalize(value)))

    initialize = set

    def get(self) -> list[Any]:
        value = self._tk.globalgetvar(self._name)
        if value in (None, ""):
            return []
        if isinstance(value, (tuple, list)):
            return list(value)
        if isinstance(value, str):
            try:
                return list(self._tk.splitlist(value))
            except tk.TclError:
                return [value]
        return [value]


__all__ = ["ListVar"]
