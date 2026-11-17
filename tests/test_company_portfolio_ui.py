"""Execute the rendered company cabinet script against isolated HTTP/DOM fixtures."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for browser script contract tests")
def test_company_portfolio_browser_script():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        ["node", "tests/js/company_portfolio_flow.cjs"],
        cwd=root,
        env={**os.environ, "PYTHON": sys.executable},
        check=True,
        # The fixture invokes the independent Python backend repeatedly; allow
        # loaded CI runners time for imports, while keeping a bounded timeout.
        timeout=90,
        capture_output=True,
        text=True,
    )
