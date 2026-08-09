#!/usr/bin/env python3
"""Web server for the WiFi mapping tool (JSON API plus a static page)."""

import io
import csv
import sys
import logging
from pathlib import Path

# The server runs headless, so matplotlib must select Agg before
# src.heatmap_generator imports pyplot.
import matplotlib
matplotlib.use("Agg")

from flask import Flask, jsonify, request, send_file, send_from_directory, abort
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.i18n import Translator, available_languages, LOCALES_DIR
from src.scanner import WiFiScanner
from src.heatmap_generator import HeatmapGenerator
from src.utils import (
    load_measurements,
    save_measurements,
    get_signal_stats,
    validate_measurements,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BASE_DIR = Path(__file__).parent
app = Flask(__name__, static_folder=None)
config = Config()
translator = Translator(config.language)


def _stats_payload(measurements, ssids):
    out = []
    for ssid in ssids:
        s = get_signal_stats(measurements, ssid)
        if s:
            out.append({
                "ssid": ssid,
                "min": s["min"],
                "mean": round(s["mean"], 1),
                "max": s["max"],
                "count": s["count"],
            })
    out.sort(key=lambda r: r["mean"], reverse=True)
    return out


# --- Page ---------------------------------------------------------------

@app.get("/")
def index():
    return send_from_directory(BASE_DIR / "web", "index.html")


@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(BASE_DIR / "web", filename)


@app.get("/locales/<code>.json")
def locale(code):
    """Serve a translation catalogue to the browser."""
    if not code.isalnum():
        abort(400)
    path = LOCALES_DIR / f"{code}.json"
    if not path.exists():
        abort(404)
    return send_file(path, mimetype="application/json")


@app.get("/plan")
def plan():
    path = BASE_DIR / config.plan_path
    if not path.exists():
        abort(404)
    return send_file(path)


def _thumbnail(source: Path, width: int) -> Path:
    """Disk-cached thumbnail, rebuilt when the source is newer."""
    width = max(80, min(width, 1200))
    cache_dir = source.parent / ".thumbs"
    cache_dir.mkdir(exist_ok=True)
    thumb = cache_dir / f"{width}_{source.name}"
    if not thumb.exists() or thumb.stat().st_mtime < source.stat().st_mtime:
        with Image.open(source) as im:
            im.thumbnail((width, width * 4), Image.LANCZOS)
            im.save(thumb, "PNG", optimize=True)
    return thumb


@app.get("/heatmap/<path:name>")
def heatmap(name):
    if "/" in name or "\\" in name or not name.endswith(".png"):
        abort(400)
    path = BASE_DIR / config.output_dir / name
    if not path.exists():
        abort(404)
    width = request.args.get("w", type=int)
    if width:
        try:
            return send_file(_thumbnail(path, width))
        except Exception as e:
            logging.warning(f"could not build a thumbnail for {name}: {e}")
    return send_file(path)


# --- Settings -----------------------------------------------------------

@app.get("/api/config")
def get_config():
    valid, msg = config.is_valid()
    return jsonify({
        "ssids": config.ssids,
        "interface": config.wifi_interface,
        "language": config.language,
        "languages": available_languages(),
        "plan_path": config.plan_path,
        "measurements_path": config.measurements_path,
        "scan_timeout": config.scan_timeout,
        "heatmap_dpi": config.heatmap_dpi,
        "heatmap_resolution": config.heatmap_resolution,
        "plan_available": (BASE_DIR / config.plan_path).exists(),
        "valid": valid,
        "status_key": msg,
    })


@app.post("/api/config")
def set_config():
    data = request.get_json(silent=True) or {}
    if "interface" in data:
        config.wifi_interface = str(data["interface"])
    if "language" in data:
        codes = {l["code"] for l in available_languages()}
        if data["language"] not in codes:
            return jsonify({"error": "unknown language"}), 400
        config.language = data["language"]
        translator.set_language(config.language)
    for key in ("scan_timeout", "heatmap_dpi", "heatmap_resolution"):
        if key in data:
            try:
                setattr(config, key, int(data[key]))
            except (TypeError, ValueError):
                return jsonify({"error": f"invalid {key}"}), 400
    config.save()
    return get_config()


@app.get("/api/interfaces")
def interfaces():
    return jsonify({"interfaces": WiFiScanner().get_available_interfaces()})


# --- Networks -----------------------------------------------------------

@app.post("/api/ssids")
def add_ssids():
    data = request.get_json(silent=True) or {}
    incoming = data.get("ssids") or ([data["ssid"]] if data.get("ssid") else [])
    added = [s for s in incoming if s and config.add_ssid(s)]
    config.save()
    return jsonify({"ssids": config.ssids, "added": added})


@app.delete("/api/ssids/<path:ssid>")
def remove_ssid(ssid):
    config.remove_ssid(ssid)
    config.save()
    return jsonify({"ssids": config.ssids})


# --- Scanning -----------------------------------------------------------

@app.post("/api/scan")
def scan():
    only_targets = bool((request.get_json(silent=True) or {}).get("only_targets"))
    networks = WiFiScanner(config.wifi_interface, config.scan_timeout).scan_all()
    if only_targets:
        networks = {s: v for s, v in networks.items() if s in config.ssids}
    rows = sorted(
        ({"ssid": s, "rssi": v} for s, v in networks.items()),
        key=lambda r: r["rssi"],
        reverse=True,
    )
    return jsonify({"networks": rows})


# --- Measurements -------------------------------------------------------

@app.get("/api/measurements")
def get_measurements():
    ok, measurements, ssids = load_measurements(config.measurements_path)
    if not ok:
        measurements, ssids = [], config.ssids
    return jsonify({
        "measurements": measurements,
        "ssids": ssids,
        "stats": _stats_payload(measurements, ssids),
    })


@app.post("/api/measurements")
def post_measurements():
    data = request.get_json(silent=True) or {}
    measurements = data.get("measurements", [])
    valid, msg = validate_measurements(measurements)
    if not valid:
        return jsonify({"error": msg}), 400
    if not save_measurements(measurements, config.ssids,
                             config.plan_path, config.measurements_path):
        return jsonify({"error": "could not save"}), 500
    return jsonify({"saved": len(measurements)})


# --- Heatmaps -----------------------------------------------------------

@app.get("/api/heatmaps")
def list_heatmaps():
    out_dir = BASE_DIR / config.output_dir
    files = sorted(out_dir.glob("heatmap_*.png")) if out_dir.exists() else []
    return jsonify({
        "heatmaps": [
            {"ssid": f.stem.replace("heatmap_", ""), "file": f.name}
            for f in files
        ]
    })


@app.post("/api/heatmaps")
def generate_heatmaps():
    ok, measurements, ssids = load_measurements(config.measurements_path)
    if not ok or not measurements:
        return jsonify({"error": "no measurement"}), 400
    valid, msg = validate_measurements(measurements)
    if not valid:
        return jsonify({"error": msg}), 400
    try:
        gen = HeatmapGenerator(
            config.plan_path,
            dpi=config.heatmap_dpi,
            resolution=config.heatmap_resolution,
            alpha=config.heatmap_alpha,
            smoothing=config.rbf_smoothing,
            auto_tune=config.rbf_auto_tune,
            fade=config.fade_extrapolation,
            fade_factor=config.fade_factor,
            translator=translator,
            author=translator.t("app.author"),
        )
        (BASE_DIR / config.output_dir).mkdir(exist_ok=True)
        done, total = gen.generate_all(measurements, ssids, config.output_dir)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"generated": done, "total": total})


# --- Export -------------------------------------------------------------

def _csv_response(rows, fieldnames, filename):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    data = io.BytesIO(buf.getvalue().encode())
    return send_file(data, mimetype="text/csv",
                     as_attachment=True, download_name=filename)


@app.get("/api/export/measurements.csv")
def export_measurements():
    ok, measurements, _ = load_measurements(config.measurements_path)
    if not ok:
        abort(404)
    rows = [
        {"x": m["x"], "y": m["y"], "ssid": ssid, "rssi": rssi}
        for m in measurements
        for ssid, rssi in m["signaux"].items()
    ]
    return _csv_response(rows, ["x", "y", "ssid", "rssi"], "measurements.csv")


@app.get("/api/export/stats.csv")
def export_stats():
    ok, measurements, ssids = load_measurements(config.measurements_path)
    if not ok:
        abort(404)
    return _csv_response(_stats_payload(measurements, ssids),
                         ["ssid", "min", "mean", "max", "count"], "stats.csv")


if __name__ == "__main__":
    print("Available at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
