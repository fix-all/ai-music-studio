"""Generation engines use independent HTTP services, never import model dependencies here."""
from typing import Protocol


class GenerationEngine(Protocol):
    def health(self) -> dict: ...
    def generate(self, plan: dict, output: str) -> dict: ...
