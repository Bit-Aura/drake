#!/usr/bin/env bash
# =====================================================================
#           DELL DRAKE INFRASTRUCTURE COMMAND CENTER - LAUNCHER
# =====================================================================
# Bash script wrapper to execute the main Linux startup script.
# =====================================================================

bash "$(dirname "$0")/start_main.sh"
read -n 1 -s -r -p "Press any key to continue..."
echo ""
