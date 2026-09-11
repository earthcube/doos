"""Typed view of config.yaml — wrappers, not reimplementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config import load_raw_config


def _as_str_list(value) -> list[str]:
    if not value:
        return []
    return [str(item) for item in value]


@dataclass(frozen=True)
class Step:
    """One existing project script the wrapper may subprocess."""

    name: str
    script: str
    default_args: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OutputSpec:
    """Published path the project script already writes."""

    path: str
    format: str
    shacl: bool = True


@dataclass(frozen=True)
class Provider:
    """Registry entry for one existing generator."""

    name: str
    description: str
    status: str
    runnable: bool
    run_on_all: bool
    cwd: str
    graph: str | None
    steps: tuple[Step, ...]
    default_steps: tuple[str, ...]
    outputs: tuple[OutputSpec, ...]

    def resolve_cwd(self, root: Path) -> Path:
        return (root / self.cwd).resolve()

    def step_by_name(self, name: str) -> Step:
        for step in self.steps:
            if step.name == name:
                return step
        known = ", ".join(s.name for s in self.steps) or "(none)"
        raise KeyError(f"Unknown step {name!r} for {self.name}. Known: {known}")

    def selected_steps(self, requested: list[str] | None) -> list[Step]:
        if requested:
            return [self.step_by_name(name) for name in requested]
        if self.default_steps:
            return [self.step_by_name(name) for name in self.default_steps]
        return list(self.steps)

    def resolve_outputs(self, root: Path) -> list[tuple[Path, str, bool]]:
        return [
            (root / spec.path, spec.format, spec.shacl) for spec in self.outputs
        ]


def _parse_provider(name: str, raw: dict) -> Provider:
    steps = tuple(
        Step(
            name=str(item.get("name") or f"step{index}"),
            script=str(item["script"]),
            default_args=_as_str_list(item.get("default_args")),
        )
        for index, item in enumerate(raw.get("steps") or [])
    )
    outputs = tuple(
        OutputSpec(
            path=str(item["path"]),
            format=str(item.get("format") or "mixed"),
            shacl=bool(item.get("shacl", True)),
        )
        for item in raw.get("outputs") or []
    )
    default_steps = tuple(_as_str_list(raw.get("default_steps")))
    return Provider(
        name=name,
        description=str(raw.get("description") or ""),
        status=str(raw.get("status") or ""),
        runnable=bool(raw.get("runnable", True)),
        run_on_all=bool(raw.get("run_on_all", False)),
        cwd=str(raw.get("cwd") or "."),
        graph=raw.get("graph"),
        steps=steps,
        default_steps=default_steps,
        outputs=outputs,
    )


def load_providers(config_path: Path | None = None) -> tuple[dict, dict[str, Provider]]:
    """Return (raw_config, name → Provider)."""
    raw = load_raw_config(config_path)
    providers = {
        name: _parse_provider(name, body)
        for name, body in (raw.get("providers") or {}).items()
    }
    return raw, providers


def get_provider(name: str, providers: dict[str, Provider]) -> Provider:
    if name not in providers:
        known = ", ".join(sorted(providers))
        raise KeyError(f"Unknown provider {name!r}. Known: {known}")
    return providers[name]

