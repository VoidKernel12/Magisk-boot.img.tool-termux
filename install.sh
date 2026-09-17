#!/data/data/com.termux/files/usr/bin/bash
#
# install.sh — Setup for Magisk Boot Patcher (Termux)
#

set -euo pipefail

GOLD="\033[38;5;220m"
GREEN="\033[92m"
CYAN="\033[96m"
RESET="\033[0m"
BOLD="\033[1m"

echo -e "${GOLD}${BOLD}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║     Magisk Boot Patcher — Installer                  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"

echo -e "${CYAN}[*] Updating packages…${RESET}"
pkg update -y

echo -e "${CYAN}[*] Installing python…${RESET}"
pkg install -y python

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
chmod +x "${SCRIPT_DIR}/magisk_patcher.py"
chmod +x "${SCRIPT_DIR}/install.sh"

echo -e "${GREEN}[+] Done.${RESET}"
echo ""
echo -e "Run the patcher with:"
echo -e "  ${CYAN}python magisk_patcher.py${RESET}"
echo ""
