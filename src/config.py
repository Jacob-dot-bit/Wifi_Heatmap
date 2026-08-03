"""Configuration de l'application, persistee en JSON."""

import json
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class Config:
    DEFAULT_CONFIG_FILE = "wifi_config.json"
    DEFAULT_MEASUREMENTS_FILE = "data/mesures.json"
    DEFAULT_PLAN_FILE = "data/plan.png"

    def __init__(self, config_file: str = DEFAULT_CONFIG_FILE):
        self.config_file = config_file
        self.ssids: List[str] = []
        self.plan_path: str = self.DEFAULT_PLAN_FILE
        self.measurements_path: str = self.DEFAULT_MEASUREMENTS_FILE
        self.wifi_interface: str = "wlan0"
        self.scan_timeout: int = 15
        self.heatmap_dpi: int = 150
        self.heatmap_resolution: int = 400
        self.heatmap_alpha: float = 0.55
        self.rbf_smoothing: float = 1.0
        self.output_dir: str = "output"

        self.load()

    def load(self) -> None:
        if not Path(self.config_file).exists():
            return
        try:
            with open(self.config_file) as f:
                self.__dict__.update(json.load(f))
        except Exception as e:
            logger.warning(f"Config illisible: {e}")

    def save(self) -> None:
        config_data = {
            "ssids": self.ssids,
            "plan_path": self.plan_path,
            "measurements_path": self.measurements_path,
            "wifi_interface": self.wifi_interface,
            "scan_timeout": self.scan_timeout,
            "heatmap_dpi": self.heatmap_dpi,
            "heatmap_resolution": self.heatmap_resolution,
            "heatmap_alpha": self.heatmap_alpha,
            "rbf_smoothing": self.rbf_smoothing,
            "output_dir": self.output_dir,
        }
        try:
            with open(self.config_file, "w") as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            logger.error(f"Sauvegarde impossible: {e}")

    def add_ssid(self, ssid: str) -> bool:
        """Ajoute un SSID. Retourne False s'il etait deja present."""
        if ssid not in self.ssids:
            self.ssids.append(ssid)
            return True
        return False

    def remove_ssid(self, ssid: str) -> bool:
        if ssid in self.ssids:
            self.ssids.remove(ssid)
            return True
        return False

    def get_ssids(self) -> List[str]:
        return self.ssids.copy()

    def is_valid(self) -> tuple[bool, str]:
        if not self.ssids:
            return False, "Aucun SSID configure"
        if not Path(self.plan_path).exists():
            return False, f"Plan introuvable: {self.plan_path}"
        return True, "ok"
