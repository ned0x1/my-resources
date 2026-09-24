#!/bin/bash
echo "[+] INSTALLING STRINGCHEESE"
echo "[+] Creating venv ..."
python3 -m venv .venv
echo "[+] Activating venv ..."
source ./.venv/bin/activate
echo "[+] Collecting stringcheese ..."
pip install stringcheese
stringcheese --help
echo "[+] Finished, to run Stringcheese, enable your venv with 'source ./.venv/bin/activate' and run 'stringcheese'."
