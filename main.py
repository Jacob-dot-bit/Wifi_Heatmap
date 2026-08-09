#!/usr/bin/env python3
"""Command line interface for the WiFi mapping tool."""

import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.i18n import Translator, available_languages
from src.scanner import WiFiScanner
from src.collector import InteractiveCollector
from src.heatmap_generator import HeatmapGenerator
from src.utils import (
    load_measurements,
    export_to_csv,
    get_signal_stats,
    validate_measurements,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

config = Config()
tr = Translator(config.language)
AUTHOR = tr.t("app.author")


def clear_screen():
    os.system("clear" if os.name != "nt" else "cls")


def print_header():
    print("\n" + "=" * 70)
    print(f"{tr.t('cli.header')}  -  {AUTHOR}")
    print("=" * 70)


def pause():
    input(tr.t("cli.pause"))


def select_interface() -> str:
    """Ask the user which network interface to scan with."""
    clear_screen()
    print_header()
    print("\n" + tr.t("cli.interface.title"))
    print("-" * 70)

    interfaces = WiFiScanner().get_available_interfaces()

    if not interfaces:
        print(tr.t("cli.interface.none"))
        return input(tr.t("cli.interface.prompt")).strip() or "wlan0"

    print(tr.t("cli.interface.found", count=len(interfaces)))
    for i, iface in enumerate(interfaces, 1):
        print(f"    {i}. {iface}")

    choice = input(tr.t("cli.choice.default")).strip()
    if not choice:
        return interfaces[0]
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(interfaces):
            return interfaces[idx]
    except ValueError:
        pass
    return interfaces[0]


def select_language():
    """Switch the interface language and remember it."""
    clear_screen()
    print_header()
    print(tr.t("cli.language.title"))
    print("-" * 70)

    languages = available_languages()
    current = next((l["name"] for l in languages if l["code"] == config.language),
                   config.language)
    print(tr.t("cli.language.current", name=current))
    print()
    for i, lang in enumerate(languages, 1):
        print(f"    {i}. {lang['name']} ({lang['code']})")

    choice = input("\n" + tr.t("cli.choice")).strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(languages):
            config.language = languages[idx]["code"]
            tr.set_language(config.language)
            config.save()
    except ValueError:
        pass


def menu_ssids():
    while True:
        clear_screen()
        print_header()
        print("\n" + tr.t("cli.ssid.title"))
        print("-" * 70)
        if config.ssids:
            for i, ssid in enumerate(config.ssids, 1):
                print(f"  {i}. {ssid}")
        else:
            print(tr.t("cli.ssid.none"))

        print()
        print(tr.t("cli.ssid.add"))
        print(tr.t("cli.ssid.remove"))
        print(tr.t("cli.ssid.scan"))
        print(tr.t("cli.ssid.back"))

        choice = input("\n" + tr.t("cli.choice")).strip()

        if choice == "1":
            ssid = input(tr.t("cli.ssid.prompt")).strip()
            if not ssid:
                print(tr.t("cli.ssid.empty"))
            elif config.add_ssid(ssid):
                print(tr.t("cli.ssid.added", ssid=ssid))
            else:
                print(tr.t("cli.ssid.duplicate", ssid=ssid))
            pause()

        elif choice == "2":
            if not config.ssids:
                print(tr.t("cli.ssid.noremove"))
                pause()
                continue
            for i, ssid in enumerate(config.ssids, 1):
                print(f"  {i}. {ssid}")
            try:
                idx = int(input(tr.t("cli.ssid.number")).strip()) - 1
                if 0 <= idx < len(config.ssids):
                    removed = config.ssids[idx]
                    config.remove_ssid(removed)
                    print(tr.t("cli.ssid.removed", ssid=removed))
            except ValueError:
                print(tr.t("cli.ssid.badnumber"))
            pause()

        elif choice == "3":
            print(tr.t("cli.scan.running"))
            networks = WiFiScanner(interface=config.wifi_interface).scan_all()
            if not networks:
                print(tr.t("cli.scan.none"))
                pause()
                continue

            ordered = sorted(networks.items(), key=lambda x: x[1], reverse=True)
            for i, (ssid, rssi) in enumerate(ordered, 1):
                mark = "x" if ssid in config.ssids else " "
                print(f"  [{mark}] {i:2d}. {ssid:<35} {rssi:>7.1f} dBm")

            sel = input(tr.t("cli.scan.prompt")).strip()
            if sel.lower() == tr.t("cli.scan.all").lower():
                for ssid in networks:
                    config.add_ssid(ssid)
            elif sel:
                try:
                    for idx in (int(x) - 1 for x in sel.split(",")):
                        if 0 <= idx < len(ordered):
                            config.add_ssid(ordered[idx][0])
                except ValueError:
                    print(tr.t("cli.badformat"))
            pause()

        elif choice == "4":
            break


def build_generator() -> HeatmapGenerator:
    return HeatmapGenerator(
        config.plan_path,
        dpi=config.heatmap_dpi,
        resolution=config.heatmap_resolution,
        alpha=config.heatmap_alpha,
        smoothing=config.rbf_smoothing,
        auto_tune=config.rbf_auto_tune,
        fade=config.fade_extrapolation,
        fade_factor=config.fade_factor,
        translator=tr,
        author=AUTHOR,
    )


def menu_main():
    while True:
        clear_screen()
        print_header()

        valid, msg = config.is_valid()
        status = tr.t("status.ok") if valid else tr.t(msg)
        print(tr.t("cli.status", status=status))
        print(tr.t("cli.networks", count=len(config.ssids)))
        print(tr.t("cli.plan", name=Path(config.plan_path).name))
        print(tr.t("cli.measurements", name=Path(config.measurements_path).name))
        print(tr.t("cli.interface", name=config.wifi_interface))

        for key in ("ssids", "collect", "generate", "stats", "export",
                    "interface", "save", "language", "quit"):
            print(tr.t(f"cli.menu.{key}"))

        choice = input("\n" + tr.t("cli.choice")).strip()

        if choice == "1":
            menu_ssids()

        elif choice == "2":
            if not config.ssids:
                print(tr.t("cli.need.ssid"))
                pause()
                continue
            if not Path(config.plan_path).exists():
                print(tr.t("cli.plan.missing", path=config.plan_path))
                pause()
                continue
            try:
                InteractiveCollector(
                    config.plan_path,
                    config.ssids,
                    config.measurements_path,
                    config.scan_timeout,
                    config.wifi_interface,
                    translator=tr,
                ).run()
            except Exception as e:
                print(tr.t("cli.error", error=e))
                pause()

        elif choice == "3":
            ok, measurements, ssids = load_measurements(config.measurements_path)
            if not ok:
                print(tr.t("cli.load.failed", path=config.measurements_path))
                pause()
                continue
            valid, msg = validate_measurements(measurements)
            if not valid:
                print(tr.t("cli.invalid", message=msg))
                pause()
                continue
            try:
                Path(config.output_dir).mkdir(exist_ok=True)
                build_generator().generate_all(measurements, ssids, config.output_dir)
            except Exception as e:
                print(tr.t("cli.error", error=e))
            pause()

        elif choice == "4":
            ok, measurements, ssids = load_measurements(config.measurements_path)
            if not ok:
                print(tr.t("cli.load.failed", path=config.measurements_path))
                pause()
                continue
            print(tr.t("cli.stats.title", count=len(measurements)))
            print("-" * 70)
            for ssid in ssids:
                stats = get_signal_stats(measurements, ssid)
                if stats:
                    print(
                        f"{ssid:<35} "
                        f"min {stats['min']:6.1f}  "
                        f"avg {stats['mean']:6.1f}  "
                        f"max {stats['max']:6.1f}  "
                        f"({stats['count']} pts)"
                    )
            print("-" * 70)
            pause()

        elif choice == "5":
            ok, measurements, _ = load_measurements(config.measurements_path)
            if not ok:
                print(tr.t("cli.load.failed", path=config.measurements_path))
                pause()
                continue
            output = input(tr.t("cli.export.prompt")).strip() or "measurements.csv"
            if export_to_csv(measurements, output):
                print(tr.t("cli.export.done", path=output))
            else:
                print(tr.t("cli.export.failed"))
            pause()

        elif choice == "6":
            config.wifi_interface = select_interface()
            print("\n" + tr.t("cli.interface", name=config.wifi_interface))
            pause()

        elif choice == "7":
            config.save()
            print(tr.t("cli.config.saved", path=config.config_file))
            pause()

        elif choice == "8":
            select_language()

        elif choice == "9":
            print()
            sys.exit(0)


def first_run_setup():
    """Ask for the interface and the networks on the very first run."""
    clear_screen()
    print_header()
    print(tr.t("cli.setup.title"))
    print("-" * 70)

    config.wifi_interface = select_interface()

    print(tr.t("cli.setup.scan"))
    print(tr.t("cli.setup.manual"))
    print(tr.t("cli.setup.later"))
    choice = input("\n" + tr.t("cli.choice")).strip()

    if choice == "1":
        print(tr.t("cli.scan.running"))
        networks = WiFiScanner(interface=config.wifi_interface).scan_all()
        for ssid in networks:
            config.add_ssid(ssid)
        print(tr.t("cli.setup.added", count=len(networks)))
        pause()
    elif choice == "2":
        while True:
            ssid = input(tr.t("cli.setup.prompt")).strip()
            if not ssid:
                break
            config.add_ssid(ssid)

    config.save()


def main():
    try:
        if not config.ssids:
            first_run_setup()
        menu_main()
    except KeyboardInterrupt:
        print()
        sys.exit(0)
    except Exception as e:
        logger.error(f"fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
