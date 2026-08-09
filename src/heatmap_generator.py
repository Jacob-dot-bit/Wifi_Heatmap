"""Génération des heatmaps par interpolation RBF sur le plan."""

import logging
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from scipy.interpolate import RBFInterpolator
from scipy.spatial import cKDTree

logger = logging.getLogger(__name__)

# Noyaux comparés lors du calibrage. Les multiplicateurs de lissage sont
# exprimés en fraction de la taille du plan pour rester valables quelle que
# soit la résolution de l'image.
KERNELS = ("linear", "thin_plate_spline")
SMOOTHING_RATIOS = (0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 20.0, 100.0)

# En dessous de ce nombre de points, la validation croisée n'est pas fiable.
MIN_POINTS_TUNING = 5


class HeatmapGenerator:
    def __init__(
        self,
        plan_path: str,
        dpi: int = 150,
        resolution: int = 400,
        alpha: float = 0.55,
        smoothing: float = 1.0,
        auto_tune: bool = True,
        fade: bool = True,
        fade_factor: float = 2.5,
    ):
        self.plan_path = plan_path
        self.dpi = dpi
        self.resolution = resolution
        self.alpha = alpha
        self.smoothing = smoothing
        self.auto_tune = auto_tune
        self.fade = fade
        self.fade_factor = fade_factor

        try:
            self.plan = mpimg.imread(plan_path)
            self.h, self.w = self.plan.shape[:2]
        except Exception as e:
            logger.error(f"Chargement du plan impossible: {e}")
            raise

    # --- Choix du modèle ---------------------------------------------------

    def _loocv_rmse(self, points, values, kernel, smoothing) -> float:
        """Erreur de prédiction en laissant chaque point de côté à son tour."""
        errors = []
        for i in range(len(points)):
            keep = np.arange(len(points)) != i
            try:
                model = RBFInterpolator(
                    points[keep], values[keep], kernel=kernel, smoothing=smoothing
                )
                errors.append(model(points[i][None])[0] - values[i])
            except Exception:
                return np.inf
        return float(np.sqrt(np.mean(np.square(errors))))

    def _fit(self, points, values):
        """Ajuste le modèle, en calibrant noyau et lissage si possible.

        Retourne (modèle, description). Un lissage trop faible fait osciller
        l'interpolation entre des mesures naturellement bruitées ; la
        validation croisée choisit le compromis à partir des données.
        """
        scale = float(max(self.w, self.h))
        candidates = [(k, r * scale) for k in KERNELS for r in SMOOTHING_RATIOS]

        if not self.auto_tune or len(points) < MIN_POINTS_TUNING:
            kernel, smoothing = "linear", scale  # compromis sur peu de points
            model = RBFInterpolator(points, values, kernel=kernel, smoothing=smoothing)
            return model, f"{kernel}/{smoothing:.3g} (défaut)"

        best = min(candidates, key=lambda c: self._loocv_rmse(points, values, *c))
        kernel, smoothing = best
        rmse = self._loocv_rmse(points, values, kernel, smoothing)

        # Référence : ignorer la position et prédire la moyenne. Si le modèle
        # ne fait pas mieux, autant l'annoncer dans le journal.
        baseline = float(np.sqrt(np.mean([
            (values[np.arange(len(values)) != i].mean() - values[i]) ** 2
            for i in range(len(values))
        ])))
        if rmse > baseline:
            logger.info(
                "Interpolation peu informative pour ce jeu de points "
                f"(RMSE {rmse:.1f} dB contre {baseline:.1f} dB pour la moyenne)."
            )

        model = RBFInterpolator(points, values, kernel=kernel, smoothing=smoothing)
        return model, f"{kernel}/{smoothing:.3g}, RMSE {rmse:.1f} dB"

    # --- Couverture --------------------------------------------------------

    def _coverage_alpha(self, points, grid_xy, shape):
        """Opacité décroissante à mesure qu'on s'éloigne des mesures.

        Sans cela, la carte peint une couleur franche sur des zones jamais
        mesurées, où l'interpolation ne fait qu'extrapoler.
        """
        tree = cKDTree(points)
        distance, _ = tree.query(grid_xy)
        distance = distance.reshape(shape)

        # Distance caractéristique entre mesures voisines.
        if len(points) > 1:
            neighbour, _ = cKDTree(points).query(points, k=2)
            spacing = float(np.median(neighbour[:, 1]))
        else:
            spacing = max(self.w, self.h) / 10.0
        spacing = max(spacing, max(self.w, self.h) / 50.0)

        inner = spacing
        outer = spacing * max(self.fade_factor, 1.01)
        ramp = np.clip((outer - distance) / (outer - inner), 0.0, 1.0)
        return ramp * self.alpha

    # --- Rendu -------------------------------------------------------------

    def generate(
        self,
        measurements: List[Dict],
        ssid: str,
        output_file: str = None,
    ) -> Tuple[bool, str]:
        """Génère une heatmap pour un SSID. Retourne (succès, message)."""
        if output_file is None:
            output_file = f"heatmap_{ssid.replace(' ', '_')}.png"

        pts = [
            (m["x"] * self.w, m["y"] * self.h, m["signaux"][ssid])
            for m in measurements
            if ssid in m["signaux"]
        ]

        if len(pts) < 3:
            msg = f"{ssid} : pas assez de points ({len(pts)}), 3 minimum."
            logger.warning(msg)
            return False, msg

        xs = np.array([p[0] for p in pts])
        ys = np.array([p[1] for p in pts])
        zs = np.array([p[2] for p in pts])

        try:
            points = np.column_stack([xs, ys])
            model, model_desc = self._fit(points, zs)

            gx, gy = np.meshgrid(
                np.linspace(0, self.w, self.resolution),
                np.linspace(0, self.h, self.resolution),
            )
            grid_xy = np.column_stack([gx.ravel(), gy.ravel()])
            gz = model(grid_xy).reshape(gx.shape)
            gz = np.clip(gz, -100, -20)

            alpha = (
                self._coverage_alpha(points, grid_xy, gx.shape)
                if self.fade
                else self.alpha
            )

            fig, ax = plt.subplots(figsize=(14, 9))
            ax.imshow(self.plan, zorder=1)

            hm = ax.imshow(
                gz,
                extent=[0, self.w, self.h, 0],
                origin="upper",
                cmap="RdYlGn",
                alpha=alpha,
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
                ["-85\n(très faible)", "-75", "-65", "-55\n(moyen)", "-45", "-35\n(bon)"]
            )

            min_r, max_r, moy_r = zs.min(), zs.max(), zs.mean()
            subtitle = f"{len(pts)} points  |  {model_desc}"
            if self.fade:
                subtitle += "  |  zones non mesurées estompées"
            ax.set_title(
                f"Heatmap WiFi - {ssid}\n"
                f"Min: {min_r:.0f} dBm  |  Max: {max_r:.0f} dBm  |  "
                f"Moy: {moy_r:.1f} dBm\n{subtitle}",
                fontsize=11,
            )
            ax.axis("off")
            fig.text(0.99, 0.01, "Jakub WERLINSKI", ha="right", va="bottom",
                     fontsize=7, color="0.45")
            plt.tight_layout()
            plt.savefig(output_file, dpi=self.dpi, bbox_inches="tight")
            plt.close()

            msg = (
                f"{ssid:<30} -> {output_file} "
                f"(min {min_r:.0f} / moy {moy_r:.1f} / max {max_r:.0f} dBm, {model_desc})"
            )
            logger.info(msg)
            return True, msg

        except Exception as e:
            plt.close("all")
            msg = f"Erreur pour {ssid}: {e}"
            logger.error(msg)
            return False, msg

    def generate_all(
        self,
        measurements: List[Dict],
        ssids: List[str],
        output_dir: str = ".",
    ) -> Tuple[int, int]:
        """Génère une heatmap par SSID. Retourne (succès, total)."""
        Path(output_dir).mkdir(exist_ok=True)
        success_count = 0

        for ssid in ssids:
            output_file = str(Path(output_dir) / f"heatmap_{ssid.replace(' ', '_')}.png")
            ok, msg = self.generate(measurements, ssid, output_file)
            if ok:
                success_count += 1
            print(msg)

        print(f"{success_count}/{len(ssids)} heatmaps générées")
        return success_count, len(ssids)
