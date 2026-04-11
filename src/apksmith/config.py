"""Configuration dataclass for an ApkSmith instrumentation run."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Packages we treat as "framework / system / major third-party" and skip by
# default. Callers can override via InstrumentConfig.skip_package_prefixes.
DEFAULT_SKIP_PACKAGES: tuple[str, ...] = (
    "android",
    "androidx",
    "kotlin",
    "kotlinx",
    "java",
    "javax",
    "dalvik",
    "junit",
    "org",
)

DEFAULT_SKIP_COM_CHILDREN: tuple[str, ...] = (
    "android",
    "facebook",
    "google",
    "adobe",
)


MethodCallback = Callable[[str, str], None]
"""(method_hash, method_signature) -> None, fired once per patched method."""


@dataclass
class InstrumentConfig:
    """All tunables for one `instrument_apk` invocation.

    The design rule is: anything that might differ between environments
    or callers lives here. ApkSmith itself never reads environment
    variables, global config files, or a database — everything flows
    through this object.
    """

    # --- signing ---
    keystore: Path
    keystore_pass: str
    key_alias: str | None = None
    key_pass: str | None = None  # if omitted, falls back to keystore_pass

    # --- target selection ---
    target_api_graph: dict[str, Any] = field(default_factory=dict)
    """Nested-dict trie of "interesting" API calls to log. Empty = log none."""

    skip_package_prefixes: Iterable[str] = DEFAULT_SKIP_PACKAGES
    skip_com_children: Iterable[str] = DEFAULT_SKIP_COM_CHILDREN

    # --- tool paths (None = autodetect on PATH) ---
    apktool: str | None = None
    zipalign: str | None = None
    apksigner: str | None = None

    # --- rewriting knobs ---
    log_tag: str = "ApkSmith"
    """logcat tag used by all injected Log.d calls."""

    extra_local_regs: int = 2
    """Extra v-registers reserved per method for logging scratch space."""

    # --- callbacks ---
    on_method: MethodCallback | None = None
    """Fired for every method that gets patched."""

    # --- misc ---
    redecompile: bool = True
    """If False, reuse an existing apktool dir next to the input apk."""

    def resolved_key_pass(self) -> str:
        """Return the key password, defaulting to the keystore password."""
        return self.key_pass if self.key_pass is not None else self.keystore_pass
