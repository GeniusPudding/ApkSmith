"""ApkSmith — smali-level Android APK rewriting toolchain.

Public API is intentionally small and stable. Everything else is
internal and may change without notice until v1.0.
"""

from apksmith.config import InstrumentConfig
from apksmith.pipeline import instrument_apk
from apksmith.result import InstrumentResult, InstrumentStats

__version__ = "0.0.1"

__all__ = [
    "InstrumentConfig",
    "InstrumentResult",
    "InstrumentStats",
    "instrument_apk",
    "__version__",
]
