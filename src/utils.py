"""Reading, writing and exporting survey measurements."""

import json
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def export_to_csv(
    measurements: List[Dict[str, Any]], output_file: str = "measurements.csv"
) -> bool:
    """Write the measurements as CSV with columns x, y, ssid, rssi."""
    try:
        rows = []
        for m in measurements:
            x, y = m["x"], m["y"]
            for ssid, rssi in m["signaux"].items():
                rows.append({"x": x, "y": y, "ssid": ssid, "rssi": rssi})

        if not rows:
            logger.warning("nothing to export")
            return False

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["x", "y", "ssid", "rssi"])
            writer.writeheader()
            writer.writerows(rows)
        return True
    except Exception as e:
        logger.error(f"CSV export failed: {e}")
        return False


def load_measurements(file_path: str) -> tuple[bool, List[Dict], List[str]]:
    """Read a survey file. Returns (ok, measurements, ssids)."""
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        return True, data.get("mesures", []), data.get("ssids", [])
    except FileNotFoundError:
        return False, [], []
    except json.JSONDecodeError as e:
        logger.error(f"invalid JSON: {e}")
        return False, [], []
    except Exception as e:
        logger.error(f"could not read measurements: {e}")
        return False, [], []


def save_measurements(
    measurements: List[Dict],
    ssids: List[str],
    plan_path: str,
    output_file: str = "mesures.json",
) -> bool:
    try:
        import matplotlib.image as mpimg

        h, w = mpimg.imread(plan_path).shape[:2]
        data = {
            "ssids": ssids,
            "plan": Path(plan_path).name,
            "plan_w": w,
            "plan_h": h,
            "mesures": measurements,
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"could not save measurements: {e}")
        return False


def get_signal_stats(measurements: List[Dict], ssid: str) -> Dict[str, float]:
    """Minimum, maximum, mean and point count for one network."""
    values = [m["signaux"][ssid] for m in measurements if ssid in m["signaux"]]
    if not values:
        return {}
    return {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "count": len(values),
    }


def validate_measurements(measurements: List[Dict]) -> tuple[bool, str]:
    """Check the survey structure. Returns (ok, message)."""
    if not measurements:
        return False, "no measurement"
    for i, m in enumerate(measurements):
        if not all(k in m for k in ("x", "y", "signaux")):
            return False, f"measurement {i}: invalid structure"
        if not isinstance(m["signaux"], dict):
            return False, f"measurement {i}: 'signaux' must be an object"
        if not (0 <= m["x"] <= 1 and 0 <= m["y"] <= 1):
            return False, f"measurement {i}: x or y outside [0,1]"
    return True, "ok"
