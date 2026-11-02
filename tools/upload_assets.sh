#!/bin/bash

# ================= Configuration =================
REPO="toraidl/HyperOS-Port-Python"
TAG="assets"
# =================================================

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo "[-] Error: GitHub CLI (gh) not found."
    echo "    Please install and log in first: https://cli.github.com/"
    exit 1
fi

# Ensure Release exists
echo "[*] Checking Release Tag: $TAG ..."
gh release view "$TAG" -R "$REPO" &>/dev/null
if [ $? -ne 0 ]; then
    echo "[*] Creating new Release: $TAG ..."
    gh release create "$TAG" --title "Resources Storage" --notes "Auto-managed assets for HyperOS Porting." -R "$REPO"
fi

upload_file() {
    local file_path="$1"
    
    if [[ ! -f "$file_path" ]]; then
        echo "[-] Skipping: $file_path is not a valid file."
        return
    fi

    local filename=$(basename "$file_path")
    local dir_path=$(dirname "$file_path")
    local asset_name=""

    # Match naming logic in Python
    if [[ "$dir_path" == *"devices/"* ]]; then
        # Extract the first directory name under devices/ as prefix
        local prefix=$(echo "$dir_path" | sed 's/.*devices\///' | cut -d'/' -f1)
        asset_name="${prefix}_${filename}"
    elif [[ "$dir_path" == *"assets"* ]]; then
        asset_name="assets_${filename}"
    else
        asset_name="$filename"
    fi

    echo "[+] Uploading: $file_path -> $asset_name"
    
    # Perform upload (--clobber overwrites if already exists)
    # Syntax: gh release upload <tag> <local_path>#<remote_name>
    gh release upload "$TAG" "$file_path#$asset_name" --clobber -R "$REPO"
    
    if [ $? -eq 0 ]; then
        echo "    Success!"
    else
        echo "    Failed!"
    fi
}

# Process all passed arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <file1> [file2] ..."
    echo "Example: $0 devices/common/wild_boost_5.10.zip devices/fuxi/perfmgr.ko"
    exit 1
fi

for arg in "$@"; do
    upload_file "$arg"
done

echo "[*] All operations completed."
