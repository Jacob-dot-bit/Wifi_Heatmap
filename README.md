# Cartographie WiFi

Relève la puissance du signal WiFi à différents endroits d'un lieu et génère une
carte de chaleur par réseau, superposée à un plan ou à une vue aérienne.

Deux interfaces partagent le même code métier (`src/`) :

- **web** (`server.py` + `web/`) : Flask et une page HTML/CSS/JS. Interface
  principale, avec collecte au clic sur le plan.
- **ligne de commande** (`main.py`) : mêmes fonctions dans un menu texte, la
  collecte se faisant dans une fenêtre matplotlib.

## Prérequis

- Python 3 avec `numpy`, `matplotlib`, `scipy`, `flask`, `pillow`
- `iw` pour le scan (`sudo apt install iw`)
- `sudo` sans mot de passe pour `iw`, sinon le scan échoue :

  ```
  # dans sudo visudo
  monuser ALL=(ALL) NOPASSWD: /usr/sbin/iw
  ```

Sous Kali/Debian, les paquets Python passent par apt :

```
sudo apt install python3-numpy python3-matplotlib python3-scipy \
                 python3-flask python3-pil
```

## Utilisation

```
./run_web.sh        # puis http://127.0.0.1:5000
```

Déroulé : *Configuration* pour choisir l'interface WiFi, *Réseaux* pour
sélectionner les SSID à suivre, *Collecte* pour cliquer sur le plan à chaque
position (un scan se déclenche et le point s'ajoute), puis *Heatmaps*.

Les points collectés ne sont écrits sur disque qu'au clic sur **Enregistrer**.

Version en ligne de commande : `./run.sh`.

## Méthode

À chaque clic, `iw dev <interface> scan` est lancé et la meilleure valeur RSSI
de chaque réseau suivi est retenue. La position est stockée en coordonnées
relatives dans `[0,1]`, ce qui rend les mesures indépendantes de la taille de
l'image.

La carte de chaleur interpole ces points par fonctions de base radiales
(`scipy.interpolate.RBFInterpolator`). Deux garde-fous sont appliqués :

**Calibrage automatique.** Le noyau et le lissage sont choisis par validation
croisée *leave-one-out*, réseau par réseau, parmi deux noyaux et neuf niveaux
de lissage. Un lissage trop faible fait osciller l'interpolation entre des
mesures naturellement bruitées ; trop fort, elle s'aplatit sur la moyenne. Le
titre de chaque carte indique le modèle retenu et son erreur quadratique
moyenne, ce qui permet de juger la fiabilité du résultat.

**Estompage des zones non mesurées.** L'opacité décroît avec la distance à la
mesure la plus proche, l'échelle étant déduite de l'espacement médian entre
points voisins. Sans cela, la carte peindrait une couleur franche sur des zones
où l'interpolation ne fait qu'extrapoler.

Il faut au moins 3 points pour tracer la carte d'un réseau ; en dessous de 5,
la validation croisée n'est pas fiable et un réglage prudent est utilisé.
Comme le signal varie de plusieurs dB au même endroit, mieux vaut répartir les
points sur toute la surface plutôt que de les concentrer le long d'un trajet.

## Structure

```
server.py        API JSON et service des fichiers statiques
web/             page, styles et logique côté navigateur
main.py          interface en ligne de commande
src/config.py    configuration, persistée en JSON
src/scanner.py   scan des réseaux via iw
src/collector.py collecte interactive (matplotlib)
src/heatmap_generator.py  interpolation et rendu
src/utils.py     lecture, écriture et export des mesures
data/            plan.png et mesures.json
output/          heatmaps générées, et leurs vignettes dans .thumbs/
```

## Configuration

`wifi_config.json` est créé au premier enregistrement et peut être édité à la
main. Il n'est pas versionné, étant propre à chaque machine.

| Clé | Défaut | Rôle |
|---|---|---|
| `ssids` | `[]` | réseaux suivis lors de la collecte |
| `wifi_interface` | `wlan0` | interface utilisée pour le scan |
| `plan_path` | `data/plan.png` | image de fond |
| `measurements_path` | `data/mesures.json` | fichier des mesures |
| `output_dir` | `output` | dossier des cartes générées |
| `scan_timeout` | `15` | délai maximal d'un scan, en secondes |
| `heatmap_dpi` | `150` | résolution du PNG produit |
| `heatmap_resolution` | `400` | finesse de la grille d'interpolation |
| `heatmap_alpha` | `0.55` | opacité de la couleur sur les zones mesurées |
| `rbf_auto_tune` | `true` | calibrage par validation croisée |
| `rbf_smoothing` | `1.0` | lissage fixe, utilisé si `rbf_auto_tune` est `false` |
| `fade_extrapolation` | `true` | estompage des zones non mesurées |
| `fade_factor` | `2.5` | étendue de l'estompage ; plus bas resserre la couleur |

## API

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/config` | configuration courante |
| POST | `/api/config` | interface, timeout, DPI, résolution |
| GET | `/api/interfaces` | interfaces WiFi détectées |
| POST | `/api/ssids` | ajoute un ou plusieurs SSID |
| DELETE | `/api/ssids/<ssid>` | retire un SSID |
| POST | `/api/scan` | lance un scan et renvoie les RSSI |
| GET/POST | `/api/measurements` | lit / enregistre les mesures |
| GET/POST | `/api/heatmaps` | liste / génère les cartes |
| GET | `/heatmap/<nom>` | une carte ; `?w=560` renvoie une vignette |
| GET | `/api/export/*.csv` | export CSV |

## Format des mesures

`data/mesures.json` : positions normalisées dans `[0,1]` et RSSI en dBm.

```json
{
  "ssids": ["Network-07"],
  "plan": "plan.png",
  "plan_w": 489,
  "plan_h": 449,
  "mesures": [
    {"x": 0.55, "y": 0.34, "signaux": {"Network-07": -74.0}}
  ]
}
```

## Limites connues

Le serveur Flask est celui de développement, prévu pour un usage local sur
`127.0.0.1` ; il n'est pas conçu pour être exposé sur un réseau.

L'interpolation ignore la géométrie des lieux : elle ne connaît ni les murs ni
l'atténuation logarithmique avec la distance. Sur un jeu de points épars, elle
ne fait guère mieux que la moyenne du réseau, ce que le RMSE affiché sur chaque
carte permet de constater.
