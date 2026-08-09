"""WiFi scanning through the `iw` command."""

import subprocess
import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class WiFiScanner:
    def __init__(self, interface: str = "wlan0", timeout: int = 15):
        self.interface = interface
        self.timeout = timeout

    def _check_sudo(self) -> bool:
        try:
            subprocess.run(
                ["sudo", "-n", "true"],
                timeout=2,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False

    def scan_all(self) -> Dict[str, float]:
        """Scan and return {SSID: strongest RSSI}, empty on failure."""
        try:
            if not self._check_sudo():
                logger.error("passwordless sudo is required to scan")
                return {}

            out = subprocess.check_output(
                ["sudo", "iw", "dev", self.interface, "scan"],
                stderr=subprocess.DEVNULL,
                timeout=self.timeout,
                text=True,
            )
        except subprocess.TimeoutExpired:
            logger.error(f"scan timed out after {self.timeout} s")
            return {}
        except FileNotFoundError:
            logger.error("'iw' not found (sudo apt install iw)")
            return {}
        except Exception as e:
            logger.error(f"scan failed: {e}")
            return {}

        return self._parse_scan_output(out)

    def _parse_scan_output(self, output: str) -> Dict[str, float]:
        results = {}
        current_ssid = None

        for line in output.split("\n"):
            if line.strip().startswith("SSID:"):
                current_ssid = line.split("SSID:")[1].strip() or None
                continue

            if current_ssid and "signal:" in line:
                match = re.search(r"signal:\s*([-\d.]+)\s*dBm", line)
                if match:
                    rssi = float(match.group(1))
                    # A network may be seen on several bands: keep the best.
                    if current_ssid not in results or rssi > results[current_ssid]:
                        results[current_ssid] = rssi

        return results

    def get_available_interfaces(self) -> list:
        try:
            out = subprocess.check_output(
                ["sudo", "iw", "dev"],
                stderr=subprocess.DEVNULL,
                timeout=5,
                text=True,
            )
            return [
                line.split("Interface")[-1].strip()
                for line in out.split("\n")
                if "Interface" in line
            ]
        except Exception as e:
            logger.error(f"could not list interfaces: {e}")
            return []
