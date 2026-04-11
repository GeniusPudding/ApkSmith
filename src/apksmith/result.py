"""Return types for `instrument_apk`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class InstrumentStats:
    """Counters collected during one instrumentation run."""

    methods_scanned: int = 0
    methods_patched: int = 0
    methods_skipped_too_many_locals: int = 0
    branches_logged: int = 0
    labels_logged: int = 0
    target_api_hits: int = 0


@dataclass
class InstrumentResult:
    """Everything a caller might want after a successful run."""

    repacked_apk: Path
    app_hash: str
    """sha256[:16] of the app's derived name — stable across runs of the same apk."""

    methods: dict[str, str] = field(default_factory=dict)
    """method_hash -> fully qualified method signature, for every patched method."""

    stats: InstrumentStats = field(default_factory=InstrumentStats)
