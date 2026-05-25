#!/usr/bin/env bash
set -euo pipefail

# Install OpenJDK 17 JRE (headless) for Debian/Ubuntu or RHEL-based systems
# Optimized for Oracle Cloud Free Tier (ARM64/Ampere)

ARCH=$(uname -m)
OS=$(uname -s | tr '[:upper:]' '[:lower:]')

install_debian() {
    echo "[*] Installing OpenJDK 17 JRE headless (apt)..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq openjdk-17-jre-headless
}

install_rhel() {
    echo "[*] Installing OpenJDK 17 (yum)..."
    sudo yum install -y java-17-openjdk-headless
}

install_alpine() {
    echo "[*] Installing OpenJDK 17 (apk)..."
    sudo apk add --no-cache openjdk17-jre-headless
}

case "$OS" in
    linux)
        if [ -f /etc/debian_version ]; then
            install_debian
        elif [ -f /etc/redhat-release ]; then
            install_rhel
        elif [ -f /etc/alpine-release ]; then
            install_alpine
        else
            echo "[!] Unsupported Linux distro. Install Java 17 manually."
            exit 1
        fi
        ;;
    *)
        echo "[!] Unsupported OS: $OS"
        exit 1
        ;;
esac

echo "[✓] Java installed:"
java -version 2>&1 || true
