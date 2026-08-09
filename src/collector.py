"""Interactive survey through a matplotlib window."""

import logging
from pathlib import Path
from typing import List, Dict
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.widgets import Button

from .scanner import WiFiScanner
from .utils import save_measurements
from .i18n import Translator

logger = logging.getLogger(__name__)


class InteractiveCollector:
    """Show the plan, scan on every click and record the readings."""

    def __init__(
        self,
        plan_path: str,
        ssids: List[str],
        output_file: str = "mesures.json",
        scan_timeout: int = 15,
        wifi_interface: str = "wlan0",
        translator: Translator = None,
    ):
        self.plan_path = plan_path
        self.ssids = ssids
        self.output_file = output_file
        self.measurements: List[Dict] = []
        self.scanning = False
        self.point_num = 0
        self.tr = translator or Translator()

        try:
            self.plan = mpimg.imread(plan_path)
            self.h, self.w = self.plan.shape[:2]
        except Exception as e:
            logger.error(f"could not read the floor plan: {e}")
            raise

        self.scanner = WiFiScanner(interface=wifi_interface, timeout=scan_timeout)

    def run(self) -> bool:
        if not self.ssids:
            logger.error("no network configured")
            return False

        self.fig = plt.figure(figsize=(14, 9))
        self.ax = self.fig.add_axes([0.02, 0.08, 0.96, 0.90])
        ax_btn = self.fig.add_axes([0.40, 0.01, 0.20, 0.05])
        btn = Button(ax_btn, self.tr.t("collector.button"), color="lightgreen")

        self.ax.imshow(self.plan)
        self.ax.set_title(self.tr.t("collector.title"), fontsize=11)
        self.ax.axis("off")

        colors = plt.cm.tab10(np.linspace(0, 1, min(len(self.ssids), 10)))

        for i, ssid in enumerate(self.ssids[:10]):
            self.ax.scatter([], [], color=colors[i % 10], s=80, label=ssid)
        if len(self.ssids) > 10:
            self.ax.scatter([], [], color="gray", s=80, label=f"+{len(self.ssids) - 10}")
        self.ax.legend(loc="upper right", fontsize=8, framealpha=0.85)

        self.scatters = {}
        for i, ssid in enumerate(self.ssids):
            self.scatters[ssid] = self.ax.scatter(
                [], [], color=colors[i % 10], s=120,
                edgecolors="black", linewidths=0.6, zorder=5, alpha=0.9,
            )

        self.status_txt = self.ax.text(
            0.01, 0.01, self.tr.t("collector.ready"),
            transform=self.ax.transAxes, fontsize=10,
            bbox=dict(boxstyle="round", fc="white", alpha=0.8),
        )

        self.fig.canvas.mpl_connect("button_press_event", self._on_click)
        btn.on_clicked(self._on_finish)

        print(self.tr.t("collector.info", name=Path(self.plan_path).name,
                        width=self.w, height=self.h, count=len(self.ssids)))
        print(self.tr.t("collector.help") + "\n")

        plt.tight_layout()
        plt.show()
        return True

    def _on_click(self, event):
        if event.inaxes != self.ax or event.button != 1 or self.scanning:
            return

        x, y = event.xdata, event.ydata
        self.point_num += 1
        self.scanning = True

        self.status_txt.set_text(self.tr.t("collector.scanning", index=self.point_num))
        self.fig.canvas.draw()
        plt.pause(0.05)

        print(f"\nPoint {self.point_num} ({int(x)}, {int(y)})", flush=True)
        rssis = self.scanner.scan_all()

        if not rssis:
            print(self.tr.t("collector.nonetwork"))
            self.status_txt.set_text(self.tr.t("collector.none", index=self.point_num))
            self.point_num -= 1
            self.scanning = False
            self.fig.canvas.draw()
            return

        self.measurements.append({"x": x / self.w, "y": y / self.h, "signaux": rssis})

        for ssid, rssi in sorted(rssis.items()):
            print(f"  {ssid:<35} {rssi:>7.1f} dBm")

        for ssid in self.ssids:
            pts = [(m["x"] * self.w, m["y"] * self.h) for m in self.measurements
                   if ssid in m["signaux"]]
            if pts:
                self.scatters[ssid].set_offsets(pts)

        self.ax.annotate(
            str(self.point_num), (x, y),
            textcoords="offset points", xytext=(4, 4),
            fontsize=9, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.15", fc="yellow", alpha=0.8),
        )

        self.status_txt.set_text(self.tr.t("collector.collected", count=self.point_num))
        self.scanning = False
        self.fig.canvas.draw()

    def _on_finish(self, event):
        if not self.measurements:
            print(self.tr.t("collector.nopoint"))
            return
        if save_measurements(self.measurements, self.ssids, self.plan_path, self.output_file):
            print(self.tr.t("collector.saved", count=len(self.measurements)))
        else:
            print(self.tr.t("collector.savefailed"))
        plt.close()
