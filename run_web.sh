#!/bin/bash
# Lance le serveur web.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

if ! python3 -c "import flask, numpy, matplotlib, scipy" 2>/dev/null; then
    echo "Dependances manquantes, voir README.md"
    exit 1
fi

if ! command -v iw >/dev/null; then
    echo "Avertissement : 'iw' introuvable, le scan WiFi ne fonctionnera pas."
fi

python3 server.py
