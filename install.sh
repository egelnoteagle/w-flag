#!/usr/bin/env bash
# install.sh — set up the W Flag app on a Raspberry Pi Zero
# Run as root: sudo bash install.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/venv"

echo "==> Installing system dependencies..."
apt-get update -q
apt-get install -y -q python3 python3-pip python3-venv python3-dev \
    libglib2.0-dev libjpeg-dev libopenjp2-7-dev

# ---------------------------------------------------------------------------
# rpi-rgb-led-matrix (build from source — no pip package for Pi Zero ARM)
# ---------------------------------------------------------------------------
if [ ! -d /opt/rpi-rgb-led-matrix ]; then
    echo "==> Cloning rpi-rgb-led-matrix..."
    git clone https://github.com/hzeller/rpi-rgb-led-matrix.git /opt/rpi-rgb-led-matrix
fi

echo "==> Building rpi-rgb-led-matrix Python bindings..."
cd /opt/rpi-rgb-led-matrix
make -j2 build-python PYTHON="$(which python3)"
make install-python PYTHON="$(which python3)"
cd "$REPO_DIR"

# ---------------------------------------------------------------------------
# Python virtual environment + pip dependencies
# ---------------------------------------------------------------------------
echo "==> Creating Python venv at $VENV_DIR..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt"

# ---------------------------------------------------------------------------
# Prepare the W flag image
# ---------------------------------------------------------------------------
if [ -f "$REPO_DIR/assets/w_flag_source.png" ]; then
    echo "==> Preparing W flag image for 64x32 matrix..."
    "$VENV_DIR/bin/python3" -m wflag.prepare_image
else
    echo "WARNING: assets/w_flag_source.png not found — copy your W flag image there,"
    echo "  then run:  python3 -m wflag.prepare_image"
fi

# ---------------------------------------------------------------------------
# Fetch the 2026 Cubs schedule into the local DB
# ---------------------------------------------------------------------------
echo "==> Fetching 2026 Cubs schedule..."
"$VENV_DIR/bin/python3" -m wflag.setup_schedule

# ---------------------------------------------------------------------------
# Install systemd service
# ---------------------------------------------------------------------------
echo "==> Installing systemd service..."
sed "s|REPO_DIR|$REPO_DIR|g; s|VENV_DIR|$VENV_DIR|g" \
    "$REPO_DIR/w-flag.service.template" \
    > /etc/systemd/system/w-flag.service

systemctl daemon-reload
systemctl enable w-flag.service
systemctl start w-flag.service

echo ""
echo "==> Done! Service status:"
systemctl status w-flag.service --no-pager
