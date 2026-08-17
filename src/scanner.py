"""WiFi scanning through the `iw` command.

Scanning is Linux-only: it shells out to `sudo iw`. Everything else in the
project runs anywhere Python does.
"""

import shutil
import subprocess
import re
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class WiFiScanner:
    def __init__(self, interface: str = "wlan0", timeout: int = 15):
        self.interface = interface
        self.timeout = timeout

    def unavailable_reason(self) -> Optional[str]:
        """Why scanning cannot run here, or None when it can.

        The sudo probe runs `iw` itself rather than a placeholder command: a
        sudoers rule is usually scoped to `iw` alone, so testing anything else
        would report a failure where scanning actually works.
        """
        missing = [tool for tool in ("sudo", "iw") if shutil.which(tool) is None]
        if missing:
            return (
                f"scanning needs the Linux tools {' and '.join(missing)}, "
                "which this system does not provide"
            )
        try:
            probe = subprocess.run(
                ["sudo", "-n", "iw", "dev"],
                timeout=5,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            return f"could not run iw: {e}"
        if probe.returncode != 0:
            return "passwordless sudo for iw is required, see the README"
        return None

    def scan_all(self) -> Dict[str, float]:
        """Scan and return {SSID: strongest RSSI}, empty on failure."""
        reason = self.unavailable_reason()
        if reason:
            logger.error(reason)
            return {}

        try:
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
        reason = self.unavailable_reason()
        if reason:
            logger.error(reason)
            return []

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
