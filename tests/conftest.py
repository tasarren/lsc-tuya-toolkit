from pathlib import Path

import pytest


@pytest.fixture
def private_root() -> Path:
    """Evidence-dependent tests are always skipped.

    Tests that decode camera databases may expose credentials, keys, and device
    IDs in temporary files or logs. Synthetic tests cover supported code paths.
    """
    # ponytail: private-evidence tests stay skipped until safe, redacted fixtures exist.
    pytest.skip(
        "private-evidence tests disabled to prevent secret persistence or disclosure; "
        "synthetic tests cover supported paths, not hardware evidence"
    )
