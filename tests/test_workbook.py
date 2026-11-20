import subprocess
import sys
from pathlib import Path

from src.course import workbook


def test_downloadable_workbook_matches_displayed_results():
    path = Path(__file__).resolve().parents[1] / "src/static/workbook.py"
    result = subprocess.run([sys.executable, str(path), "all"],
                            check=True, capture_output=True, text=True)
    assert result.stdout.strip() == "\n".join(lab["output"] for lab in workbook()["lessons"])
