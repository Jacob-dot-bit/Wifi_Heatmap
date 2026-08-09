"""Chargement, sauvegarde et export des mesures."""

import json
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def export_to_csv(
    measurements: List[Dict[str, Any]], output_file: str = "measurements.csv"
) -> bool:
    """Exporte les mesures en CSV (colonnes x, y, ssid, rssi)."""
    try:
        rows = []
        for m in measurements:
            x, y = m["x"], m["y"]
            for ssid, rssi in m["signaux"].items():
                rows.append({"x": x, "y": y, "ssid": ssid, "rssi": rssi})

        if not rows:
            logger.warning("Aucune donnée à exporter")
            return False

        with open(output_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["x", "y", "ssid", "rssi"])
            writer.writeheader()
            writer.writerows(rows)
        return True
    except Exception as e:
        logger.error(f"Export CSV impossible: {e}")
        return False


def load_measurements(file_path: str) -> tuple[bool, List[Dict], List[str]]:
    """Charge un fichier de mesures. Retourne (succès, mesures, ssids)."""
    try:
        with open(file_path) as f:
            data = json.load(f)
        return True, data.get("mesures", []), data.get("ssids", [])
    except FileNotFoundError:
        return False, [], []
    except json.JSONDecodeError as e:
        logger.error(f"JSON invalide: {e}")
        return False, [], []
    except Exception as e:
        logger.error(f"Chargement impossible: {e}")
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
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Sauvegarde impossible: {e}")
        return False


def get_signal_stats(measurements: List[Dict], ssid: str) -> Dict[str, float]:
    """Min, max, moyenne et nombre de points pour un SSID."""
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
    if not measurements:
        return False, "Aucune mesure"
    for i, m in enumerate(measurements):
        if not all(k in m for k in ("x", "y", "signaux")):
            return False, f"Mesure {i} : structure invalide"
        if not isinstance(m["signaux"], dict):
            return False, f"Mesure {i} : 'signaux' doit être un dict"
        if not (0 <= m["x"] <= 1 and 0 <= m["y"] <= 1):
            return False, f"Mesure {i} : x ou y hors [0,1]"
    return True, "ok"
