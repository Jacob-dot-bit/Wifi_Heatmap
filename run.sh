#!/bin/bash
# Lance l'interface en ligne de commande.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

if ! python3 -c "import numpy, matplotlib, scipy" 2>/dev/null; then
    echo "Dependances manquantes : sudo apt install python3-numpy python3-matplotlib python3-scipy"
    exit 1
fi

if ! command -v iw >/dev/null; then
    echo "Avertissement : 'iw' introuvable, le scan WiFi ne fonctionnera pas."
fi

python3 main.py
