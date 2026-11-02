#!/bin/bash

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

clear
echo "========================================================"
echo "          HyperOS Flashing Script (Linux / macOS)       "
echo "========================================================"
echo ""

# Ensure fastboot is installed
if ! command -v fastboot >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        echo "fastboot not found. Installing via apt-get..."
        sudo apt-get update && sudo apt-get install -y fastboot
    elif command -v brew >/dev/null 2>&1; then
        echo "fastboot not found. Installing via Homebrew..."
        brew install android-platform-tools
    fi
fi

if ! command -v fastboot >/dev/null 2>&1; then
    echo "[ERROR] fastboot command is required but not installed."
    echo "Please install Android platform-tools / fastboot and try again."
    exit 1
fi

EXPECTED_DEVICE="device_code"

# ==========================================================
# 1. Check phone codename / type / name
# ==========================================================
echo "[1/4] Checking connected device..."
echo "Please ensure your device is connected in Fastboot/Bootloader mode."
echo ""

product=$(fastboot getvar product 2>&1 | grep -i "^product:" | head -n 1 | awk -F': ' '{print $2}' | tr -d '\r' | tr -d ' ')

if [ -z "$product" ]; then
    echo "[WARNING] No device detected or unable to read device codename!"
    echo "Please verify fastboot connection and USB permissions (e.g. udev rules on Linux)."
    read -p "Do you want to continue anyway? (y/N): " continue_anyway
    if [[ ! "$continue_anyway" =~ ^[Yy]$ ]]; then
        echo "Flashing aborted by user."
        exit 1
    fi
else
    echo "Detected device codename : ${product}"
    echo "Expected ROM codename    : ${EXPECTED_DEVICE}"
    echo ""
    if [ "$product" != "$EXPECTED_DEVICE" ]; then
        echo "[WARNING] Device codename mismatch!"
        echo "ROM is designed for [${EXPECTED_DEVICE}], but detected device is [${product}]."
        read -p "Are you sure you want to continue anyway? (y/N): " continue_mismatch
        if [[ ! "$continue_mismatch" =~ ^[Yy]$ ]]; then
            echo "Flashing aborted by user."
            exit 1
        fi
    else
        echo "[OK] Device codename verified successfully."
    fi
fi
echo ""

# ==========================================================
# 2. Ask user whether to format data or not
# ==========================================================
echo "[2/4] User Data Format Options:"
echo ""
echo "  1. Keep user data (Dirty flash / Update) [Default]"
echo "  2. Format data    (Clean flash - wipes userdata and metadata)"
echo ""
read -p "Please select [1 or 2, default is 1]: " format_input
format_input=${format_input:-1}

if [ "$format_input" = "2" ]; then
    echo "Option selected: [2] Format user data."
else
    echo "Option selected: [1] Keep user data."
fi
echo ""

# ==========================================================
# 3. Flash phone firmware
# ==========================================================
echo "[3/4] Flashing firmware and boot partitions..."
echo ""

if [ -f "boot.img" ]; then
    echo "Flashing boot..."
    fastboot flash boot_a boot.img
    fastboot flash boot_b boot.img
elif [ -f "firmware-update/boot.img" ]; then
    echo "Flashing boot..."
    fastboot flash boot_a firmware-update/boot.img
    fastboot flash boot_b firmware-update/boot.img
fi

FW_PARTITIONS=(
    dtbo
    init_boot
    vendor_boot
    recovery
    vbmeta
    vbmeta_system
    vm-bootsys
    pvmfw
    modem
    modemfirmware
    dsp
    bluetooth
    xbl
    xbl_config
    xbl_ramdump
    tz
    hyp
    uefi
    uefisecapp
    keymaster
    qupfw
    devcfg
    featenabler
    cpucp
    cpucp_dtb
    aop
    aop_config
    abl
    shrm
    soccp_debug
    soccp_dcd
    spuservice
    imagefv
    countrycode
    idmanager
    multiimgqti
)

for part in "${FW_PARTITIONS[@]}"; do
    if [ -f "firmware-update/${part}.img" ]; then
        echo "Flashing ${part}..."
        fastboot flash "${part}_a" "firmware-update/${part}.img"
        fastboot flash "${part}_b" "firmware-update/${part}.img"
    fi
done

# firmware

echo ""

# ==========================================================
# 4. Flash super image
# ==========================================================
echo "[4/4] Flashing super image..."
echo ""

if [ ! -f "super.img" ]; then
    echo "[ERROR] super.img not found in current directory (${SCRIPT_DIR})!"
    echo "Please ensure super.img is present."
    exit 1
fi

echo "Flashing super.img (this may take several minutes)..."
fastboot flash super super.img
if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Failed to flash super.img!"
    exit 1
fi

if [ "$format_input" = "2" ]; then
    echo ""
    echo "Wiping userdata and metadata as requested..."
    fastboot erase userdata
    fastboot erase metadata
fi

# SET_ACTION_SLOT_A_BEGIN
echo ""
echo "Setting active slot to 'a'..."
fastboot set_active a
# SET_ACTION_SLOT_A_END

echo ""
echo "Rebooting device into system..."
fastboot reboot

echo ""
echo "========================================================"
echo "Flashing completed successfully!"
echo "If your phone does not restart automatically, please restart manually."
echo "========================================================"
exit 0
