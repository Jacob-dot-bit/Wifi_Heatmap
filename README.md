# WiFi Mapping

Measures WiFi signal strength at chosen spots and renders one heatmap per
network on top of a floor plan or aerial view.

Two front-ends share the same core (`src/`):

- **web** (`server.py` + `web/`): Flask plus a plain HTML/CSS/JS page. This is
  the main interface; the survey works by clicking on the plan.
- **command line** (`main.py`): the same features in a text menu, with the
  survey running in a matplotlib window.

The interface ships in English and French, and any other language can be added
without touching the code — see [Translations](#translations).

Author: Jakub WERLINSKI.

## Requirements

- Python 3 with `numpy`, `matplotlib`, `scipy`, `flask`, `pillow`
- `iw` for scanning (`sudo apt install iw`)
- passwordless `sudo` for `iw`, otherwise every scan fails:

  ```
  # in sudo visudo
  youruser ALL=(ALL) NOPASSWD: /usr/sbin/iw
  ```

On Kali/Debian the Python packages come from apt:

```
sudo apt install python3-numpy python3-matplotlib python3-scipy \
                 python3-flask python3-pil
```

## Usage

```
./run_web.sh        # then open http://127.0.0.1:5000
```

Pick the WiFi interface under *Settings*, choose the networks to follow under
*Networks*, then click your position on the plan under *Survey* — each click
triggers a scan and records a point. *Heatmaps* renders the maps.

Collected points stay in the browser until you press **Save**.

Command line version: `./run.sh`.

## Translations

The active language is stored in `wifi_config.json` and can be changed from the
language selector in the top bar, or from entry 8 of the command line menu.
Both front-ends and the generated map labels follow the setting.

Catalogues live in `locales/<code>.json` as flat key/value pairs. Adding a
language means copying `locales/en.json`, translating the values, and setting
`language.name` to the label shown in the picker — the file is picked up
automatically. Missing keys fall back to English, so a partial translation
degrades gracefully instead of breaking a screen.

## Method

Each click runs `iw dev <interface> scan` and keeps the strongest RSSI seen for
every tracked network. Positions are stored as relative coordinates in `[0,1]`,
which keeps the survey independent of the image size.

The heatmap interpolates those readings with radial basis functions
(`scipy.interpolate.RBFInterpolator`), with two safeguards:

**Automatic calibration.** Kernel and smoothing are chosen per network by
leave-one-out cross-validation over two kernels and nine smoothing levels. Too
little smoothing makes the surface oscillate between readings that are noisy by
nature; too much flattens it onto the mean. Each map's title reports the chosen
model and its RMSE, so the result can be judged rather than trusted blindly.

**Faded extrapolation.** Opacity falls off with distance to the nearest
reading, scaled from the median spacing between neighbouring points. Without
it the map would paint solid colour over areas that were never visited.

A network needs at least 3 points to be mapped, and at least 5 for
cross-validation to mean anything. Since the signal varies by several dB at a
fixed spot, spreading points across the whole area beats walking a single line.

## Layout

```
server.py        JSON API and static file serving
web/             page, styles and browser logic
main.py          command line interface
locales/         translation catalogues
src/config.py    settings, persisted as JSON
src/i18n.py      catalogue loading and lookup
src/scanner.py   network scanning through iw
src/collector.py interactive survey (matplotlib)
src/heatmap_generator.py  interpolation and rendering
src/utils.py     reading, writing and exporting measurements
data/            plan.png and mesures.json
output/          rendered heatmaps, thumbnails under .thumbs/
```

## Settings

`wifi_config.json` is created on first save and can be edited by hand. It is
not tracked by git, being specific to each machine; copy
`wifi_config.example.json` over it to start from a documented set of keys.

The survey shipped in `data/` uses neutral network names, since real SSIDs
identify the people living around the surveyed area.

| Key | Default | Purpose |
|---|---|---|
| `ssids` | `[]` | networks followed during a survey |
| `wifi_interface` | `wlan0` | interface used for scanning |
| `language` | `en` | interface language, matching a file in `locales/` |
| `plan_path` | `data/plan.png` | background image |
| `measurements_path` | `data/mesures.json` | survey file |
| `output_dir` | `output` | where maps are written |
| `scan_timeout` | `15` | longest a scan may take, in seconds |
| `heatmap_dpi` | `150` | resolution of the rendered PNG |
| `heatmap_resolution` | `400` | interpolation grid size |
| `heatmap_alpha` | `0.55` | colour opacity over measured areas |
| `rbf_auto_tune` | `true` | calibrate by cross-validation |
| `rbf_smoothing` | `1.0` | fixed smoothing, used when `rbf_auto_tune` is `false` |
| `fade_extrapolation` | `true` | fade out unmeasured areas |
| `fade_factor` | `2.5` | how far the fade reaches; lower tightens the colour |

## API

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/config` | current settings and available languages |
| POST | `/api/config` | interface, language, timeout, DPI, grid size |
| GET | `/api/interfaces` | detected WiFi interfaces |
| POST | `/api/ssids` | add one or more networks |
| DELETE | `/api/ssids/<ssid>` | stop following a network |
| POST | `/api/scan` | run a scan and return the RSSI values |
| GET/POST | `/api/measurements` | read / save the survey |
| GET/POST | `/api/heatmaps` | list / render the maps |
| GET | `/heatmap/<name>` | one map; `?w=560` returns a thumbnail |
| GET | `/locales/<code>.json` | a translation catalogue |
| GET | `/api/export/*.csv` | CSV export |

## Measurement format

`data/mesures.json` holds positions normalised to `[0,1]` and RSSI in dBm.

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

## Known limits

The Flask development server is meant for local use on `127.0.0.1`; it is not
built to be exposed on a network.

The interpolation knows nothing about the geometry of the place — neither walls
nor the logarithmic fall-off with distance. On a sparse survey it barely beats
predicting the network average, which the RMSE printed on each map makes plain.
