from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from lead_finder.config import get_settings


class Scanner(BaseModel):
    id: str
    name: str
    full_name: str
    url: str
    class_: str = Field(default="", alias="class")
    specs: dict[str, str] = Field(default_factory=dict)
    best_for: list[str] = Field(default_factory=list)
    buyers: str = ""
    pick_when: str = ""
    avoid_when: str = ""
    proof: str = ""


class ScannerCatalog(BaseModel):
    scanners: list[Scanner]

    def names(self) -> list[str]:
        return [scanner.name for scanner in self.scanners]

    def canonical(self, value: object) -> str | None:
        """Map a model-written product name ("FJD Trion T1", "t1") onto a catalog name."""
        text = " ".join(str(value or "").split()).casefold()
        if not text:
            return None
        for scanner in self.scanners:
            options = {scanner.name.casefold(), scanner.full_name.casefold(), scanner.id}
            if text in options:
                return scanner.name
        padded = f" {text} "
        for scanner in sorted(self.scanners, key=lambda item: -len(item.name)):
            if f" {scanner.name.casefold()} " in padded:
                return scanner.name
        return None

    def get(self, name: str | None) -> Scanner | None:
        return next((item for item in self.scanners if item.name == name), None)

    def prompt_text(self) -> str:
        blocks: list[str] = []
        for item in self.scanners:
            specs = "; ".join(f"{key}: {value}" for key, value in item.specs.items())
            lines = [
                f"### {item.name} ({item.full_name}, {item.class_})",
                f"Specs: {specs}",
                f"Best for: {'; '.join(item.best_for)}",
                f"Typical buyers: {item.buyers}",
                f"Pick when: {item.pick_when}",
                f"Avoid when: {item.avoid_when}",
            ]
            if item.proof:
                lines.append(f"Proof: {item.proof}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)


@lru_cache
def load_scanner_catalog(path: Path | None = None) -> ScannerCatalog:
    source = path or get_settings().scanners_path
    with source.open(encoding="utf-8") as file:
        raw = yaml.safe_load(file)["scanners"]
    return ScannerCatalog(
        scanners=[Scanner.model_validate({"id": key, **value}) for key, value in raw.items()]
    )
