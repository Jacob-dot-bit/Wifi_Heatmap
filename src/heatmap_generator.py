"""Generation des heatmaps par interpolation RBF sur le plan."""

import logging
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from scipy.interpolate import RBFInterpolator

logger = logging.getLogger(__name__)


class HeatmapGenerator:
    def __init__(
        self,
        plan_path: str,
        dpi: int = 150,
        resolution: int = 400,
        alpha: float = 0.55,
        smoothing: float = 1.0,
    ):
        self.plan_path = plan_path
        self.dpi = dpi
        self.resolution = resolution
        self.alpha = alpha
        self.smoothing = smoothing

        try:
            self.plan = mpimg.imread(plan_path)
            self.h, self.w = self.plan.shape[:2]
        except Exception as e:
            logger.error(f"Chargement du plan impossible: {e}")
            raise

    def generate(
        self,
        measurements: List[Dict],
        ssid: str,
        output_file: str = None,
    ) -> Tuple[bool, str]:
        """Genere une heatmap pour un SSID. Retourne (succes, message)."""
        if output_file is None:
            output_file = f"heatmap_{ssid.replace(' ', '_')}.png"

        pts = [
            (m["x"] * self.w, m["y"] * self.h, m["signaux"][ssid])
            for m in measurements
            if ssid in m["signaux"]
        ]

        if len(pts) < 3:
            msg = f"{ssid}: pas assez de points ({len(pts)}), 3 minimum."
            logger.warning(msg)
            return False, msg

        xs = np.array([p[0] for p in pts])
        ys = np.array([p[1] for p in pts])
        zs = np.array([p[2] for p in pts])

        try:
            points = np.column_stack([xs, ys])
            rbf = RBFInterpolator(
                points,
                zs,
                kernel="thin_plate_spline",
                smoothing=self.smoothing,
            )

            gx, gy = np.meshgrid(
                np.linspace(0, self.w, self.resolution),
                np.linspace(0, self.h, self.resolution),
            )
            gz = rbf(np.column_stack([gx.ravel(), gy.ravel()])).reshape(gx.shape)
            gz = np.clip(gz, -100, -20)

            fig, ax = plt.subplots(figsize=(14, 9))
            ax.imshow(self.plan, zorder=1)

            hm = ax.imshow(
                gz,
                extent=[0, self.w, self.h, 0],
                origin="upper",
                cmap="RdYlGn",
                alpha=self.alpha,
                vmin=-85,
                vmax=-35,
                zorder=2,
            )

            ax.scatter(
                xs,
                ys,
                c=zs,
                cmap="RdYlGn",
                vmin=-85,
                vmax=-35,
                s=90,
                edgecolors="black",
                linewidths=0.8,
                zorder=3,
            )

            for p in pts:
                ax.annotate(
                    f"{p[2]:.0f}",
                    (p[0], p[1]),
                    textcoords="offset points",
                    xytext=(5, -10),
                    fontsize=8,
                    fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.75),
                )

            cbar = plt.colorbar(hm, ax=ax, fraction=0.03, pad=0.02)
            cbar.set_label("Signal (dBm)", fontsize=11)
            cbar.set_ticks([-85, -75, -65, -55, -45, -35])
            cbar.set_ticklabels(
                ["-85\n(tres faible)", "-75", "-65", "-55\n(moyen)", "-45", "-35\n(bon)"]
            )

            min_r, max_r, moy_r = zs.min(), zs.max(), zs.mean()
            ax.set_title(
                f"Heatmap WiFi - {ssid}\n"
                f"Min: {min_r:.0f} dBm  |  Max: {max_r:.0f} dBm  |  "
                f"Moy: {moy_r:.1f} dBm  |  {len(pts)} points",
                fontsize=12,
            )
            ax.axis("off")
            plt.tight_layout()
            plt.savefig(output_file, dpi=self.dpi, bbox_inches="tight")
            plt.close()

            msg = (
                f"{ssid:<30} -> {output_file} "
                f"(min {min_r:.0f} / moy {moy_r:.1f} / max {max_r:.0f} dBm)"
            )
            logger.info(msg)
            return True, msg

        except Exception as e:
            msg = f"Erreur pour {ssid}: {e}"
            logger.error(msg)
            return False, msg

    def generate_all(
        self,
        measurements: List[Dict],
        ssids: List[str],
        output_dir: str = ".",
    ) -> Tuple[int, int]:
        """Genere une heatmap par SSID. Retourne (succes, total)."""
        Path(output_dir).mkdir(exist_ok=True)
        success_count = 0

        for ssid in ssids:
            output_file = str(Path(output_dir) / f"heatmap_{ssid.replace(' ', '_')}.png")
            ok, msg = self.generate(measurements, ssid, output_file)
            if ok:
                success_count += 1
            print(msg)

        print(f"{success_count}/{len(ssids)} heatmaps generees")
        return success_count, len(ssids)
