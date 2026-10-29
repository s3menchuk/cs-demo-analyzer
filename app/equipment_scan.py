"""Bridge to the entity scanner. Unknown data never implies an empty world."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def scan_equipment(path, first_round):
    start = first_round["start"]
    end = first_round.get("decision_tick", first_round["end"])
    base = dict(method="equipment-v1", round=first_round["number"], start=start, end=end)
    executable = ROOT / "bin" / ("weapon-scan.exe" if os.name == "nt" else "weapon-scan")
    if not executable.is_file():
        return dict(base, status="unknown", reason="scanner_unavailable")
    try:
        process = subprocess.run([str(executable), "-demo", str(Path(path).resolve()),
                                  "-start", str(start), "-end", str(end)],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 timeout=90, check=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        report = json.loads(process.stdout)
        if (not isinstance(report, dict) or report.get("method") != "equipment-v1" or
                report.get("status") not in ("knife", "not_knife", "unknown")):
            raise ValueError("Invalid equipment scan report")
        return dict(report, **base)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return dict(base, status="unknown", reason="scanner_failed")
