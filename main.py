#!/usr/bin/env python3
"""Interface en ligne de commande pour la cartographie WiFi."""

import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
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


def clear_screen():
    os.system("clear" if os.name != "nt" else "cls")


def print_header():
    print("\n" + "=" * 70)
    print("Cartographie WiFi")
    print("=" * 70)


def pause():
    input("  [Entrée pour continuer]")


def select_interface() -> str:
    """Demande à l'utilisateur de choisir une interface réseau."""
    clear_screen()
    print_header()
    print("\nInterface reseau")
    print("-" * 70)

    scanner = WiFiScanner()
    interfaces = scanner.get_available_interfaces()

    if not interfaces:
        print("  Aucune interface detectee automatiquement.")
        interface = input("  Interface (ex: wlan0): ").strip()
        return interface or "wlan0"

    print(f"\n  Interfaces detectees ({len(interfaces)}):")
    for i, iface in enumerate(interfaces, 1):
        print(f"    {i}. {iface}")

    choice = input("\n  Choix [1]: ").strip()
    if not choice:
        return interfaces[0]
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(interfaces):
            return interfaces[idx]
    except ValueError:
        pass
    return interfaces[0]


def menu_ssids(config: Config):
    while True:
        clear_screen()
        print_header()
        print("\nSSIDs")
        print("-" * 70)
        if config.ssids:
            for i, ssid in enumerate(config.ssids, 1):
                print(f"  {i}. {ssid}")
        else:
            print("  (aucun)")

        print("\n  [1] Ajouter un SSID")
        print("  [2] Retirer un SSID")
        print("  [3] Ajouter depuis les reseaux detectes")
        print("  [4] Retour")

        choice = input("\nChoix: ").strip()

        if choice == "1":
            ssid = input("  SSID a ajouter: ").strip()
            if not ssid:
                print("  SSID vide.")
            elif config.add_ssid(ssid):
                print(f"  Ajoute: {ssid}")
            else:
                print(f"  Deja present: {ssid}")
            pause()

        elif choice == "2":
            if not config.ssids:
                print("  Aucun SSID a retirer.")
                pause()
                continue
            for i, ssid in enumerate(config.ssids, 1):
                print(f"  {i}. {ssid}")
            try:
                idx = int(input("  Numero: ").strip()) - 1
                if 0 <= idx < len(config.ssids):
                    removed = config.ssids[idx]
                    config.remove_ssid(removed)
                    print(f"  Retire: {removed}")
            except ValueError:
                print("  Numero invalide.")
            pause()

        elif choice == "3":
            print("\n  Scan en cours...")
            scanner = WiFiScanner(interface=config.wifi_interface)
            networks = scanner.scan_all()
            if not networks:
                print("  Aucun reseau detecte.")
                pause()
                continue

            ordered = sorted(networks.items(), key=lambda x: x[1], reverse=True)
            for i, (ssid, rssi) in enumerate(ordered, 1):
                mark = "x" if ssid in config.ssids else " "
                print(f"  [{mark}] {i:2d}. {ssid:<35} {rssi:>7.1f} dBm")

            sel = input("\n  Ajouter (ex: 1,2,4 ou 'tous'): ").strip()
            if sel.lower() == "tous":
                for ssid in networks:
                    config.add_ssid(ssid)
            elif sel:
                try:
                    for idx in (int(x) - 1 for x in sel.split(",")):
                        if 0 <= idx < len(ordered):
                            config.add_ssid(ordered[idx][0])
                except ValueError:
                    print("  Format invalide.")
            pause()

        elif choice == "4":
            break


def menu_main(config: Config):
    while True:
        clear_screen()
        print_header()

        valid, msg = config.is_valid()
        print(f"\nStatut: {'pret' if valid else msg}")
        print(f"SSIDs: {len(config.ssids)}")
        print(f"Plan: {Path(config.plan_path).name}")
        print(f"Mesures: {Path(config.measurements_path).name}")
        print(f"Interface: {config.wifi_interface}")

        print("\n  [1] Gerer les SSIDs")
        print("  [2] Collecter des mesures")
        print("  [3] Generer les heatmaps")
        print("  [4] Statistiques")
        print("  [5] Exporter en CSV")
        print("  [6] Changer l'interface WiFi")
        print("  [7] Sauvegarder la configuration")
        print("  [8] Quitter")

        choice = input("\nChoix: ").strip()

        if choice == "1":
            menu_ssids(config)

        elif choice == "2":
            if not config.ssids:
                print("  Configurez d'abord les SSIDs.")
                pause()
                continue
            if not Path(config.plan_path).exists():
                print(f"  Plan introuvable: {config.plan_path}")
                pause()
                continue
            try:
                collector = InteractiveCollector(
                    config.plan_path,
                    config.ssids,
                    config.measurements_path,
                    config.scan_timeout,
                    config.wifi_interface,
                )
                collector.run()
            except Exception as e:
                print(f"  Erreur: {e}")
                pause()

        elif choice == "3":
            ok, measurements, ssids = load_measurements(config.measurements_path)
            if not ok:
                print(f"  Impossible de charger {config.measurements_path}")
                pause()
                continue
            valid, msg = validate_measurements(measurements)
            if not valid:
                print(f"  Donnees invalides: {msg}")
                pause()
                continue
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
                )
                Path(config.output_dir).mkdir(exist_ok=True)
                gen.generate_all(measurements, ssids, config.output_dir)
            except Exception as e:
                print(f"  Erreur: {e}")
            pause()

        elif choice == "4":
            ok, measurements, ssids = load_measurements(config.measurements_path)
            if not ok:
                print(f"  Impossible de charger {config.measurements_path}")
                pause()
                continue
            print(f"\nStatistiques ({len(measurements)} points)")
            print("-" * 70)
            for ssid in ssids:
                stats = get_signal_stats(measurements, ssid)
                if stats:
                    print(
                        f"{ssid:<35} "
                        f"min {stats['min']:6.1f}  "
                        f"moy {stats['mean']:6.1f}  "
                        f"max {stats['max']:6.1f}  "
                        f"({stats['count']} pts)"
                    )
            print("-" * 70)
            pause()

        elif choice == "5":
            ok, measurements, _ = load_measurements(config.measurements_path)
            if not ok:
                print(f"  Impossible de charger {config.measurements_path}")
                pause()
                continue
            output = input("  Fichier CSV [measurements.csv]: ").strip() or "measurements.csv"
            if export_to_csv(measurements, output):
                print(f"  Exporte: {output}")
            else:
                print("  Erreur lors de l'export.")
            pause()

        elif choice == "6":
            config.wifi_interface = select_interface()
            print(f"\n  Interface: {config.wifi_interface}")
            pause()

        elif choice == "7":
            config.save()
            print(f"  Configuration sauvegardee: {config.config_file}")
            pause()

        elif choice == "8":
            print()
            sys.exit(0)


def first_run_setup(config: Config):
    """Configuration au premier lancement (interface + SSIDs)."""
    clear_screen()
    print_header()
    print("\nConfiguration initiale")
    print("-" * 70)

    config.wifi_interface = select_interface()

    print("\n  [1] Scanner et ajouter des SSIDs")
    print("  [2] Ajouter manuellement")
    print("  [3] Plus tard")
    choice = input("\nChoix: ").strip()

    if choice == "1":
        print("\nScan en cours...")
        networks = WiFiScanner(interface=config.wifi_interface).scan_all()
        for ssid in networks:
            config.add_ssid(ssid)
        print(f"{len(networks)} reseaux ajoutes.")
        pause()
    elif choice == "2":
        while True:
            ssid = input("SSID (vide pour terminer): ").strip()
            if not ssid:
                break
            config.add_ssid(ssid)

    config.save()


def main():
    try:
        config = Config()
        if not config.ssids:
            first_run_setup(config)
        menu_main(config)
    except KeyboardInterrupt:
        print()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
