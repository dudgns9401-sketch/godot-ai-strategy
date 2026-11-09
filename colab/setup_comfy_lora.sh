#!/usr/bin/env bash
set -e

echo "=== [1/5] Installing System Dependencies (aria2, jq) ==="
apt-get update -qq
apt-get install -y -qq aria2 jq curl wget

GDRIVE_ROOT="/content/drive/MyDrive/AI_GameDev_Bridge"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MANIFEST_FILE="${REPO_ROOT}/config/lora_manifest.json"

echo "=== [2/5] Setting up Google Drive Bridge Directories ==="
mkdir -p "${GDRIVE_ROOT}/models_cache/checkpoints"
mkdir -p "${GDRIVE_ROOT}/models_cache/loras"
mkdir -p "${GDRIVE_ROOT}/outputs/raw_renders"
mkdir -p "${GDRIVE_ROOT}/outputs/maps_2d"
mkdir -p "${GDRIVE_ROOT}/workflows"

if [ -f "${GDRIVE_ROOT}/.env" ]; then
    echo "Loading environment variables from ${GDRIVE_ROOT}/.env"
    set -a
    # shellcheck disable=SC1090
    source "${GDRIVE_ROOT}/.env"
    set +a
fi

# Fallback default token if not loaded from .env
if [ -z "${CIVITAI_TOKEN}" ]; then
    CIVITAI_TOKEN="ff6290f892af1dfeaec11e5613fd292d"
    echo "CIVITAI_TOKEN=${CIVITAI_TOKEN}" > "${GDRIVE_ROOT}/.env"
    echo "Saved Civitai token to ${GDRIVE_ROOT}/.env"
fi

echo "=== [3/5] Setting up ComfyUI and ComfyUI-Manager ==="
if [ ! -d "/content/ComfyUI" ]; then
    echo "Cloning ComfyUI..."
    git clone https://github.com/comfyanonymous/ComfyUI.git /content/ComfyUI
fi

cd /content/ComfyUI
echo "Installing ComfyUI python requirements..."
pip install -q -r requirements.txt

if [ ! -d "/content/ComfyUI/custom_nodes/ComfyUI-Manager" ]; then
    echo "Cloning ComfyUI-Manager..."
    git clone https://github.com/ltdrdata/ComfyUI-Manager.git /content/ComfyUI/custom_nodes/ComfyUI-Manager
fi

mkdir -p /content/ComfyUI/models/checkpoints
mkdir -p /content/ComfyUI/models/loras

echo "=== [4/5] Syncing AI Models with GDrive Cache ==="
if [ -f "${MANIFEST_FILE}" ]; then
    # Base Checkpoint
    BASE_NAME=$(jq -r '.base_checkpoint.name // empty' "${MANIFEST_FILE}")
    BASE_URL=$(jq -r '.base_checkpoint.url // empty' "${MANIFEST_FILE}")

    if [ -n "${BASE_NAME}" ] && [ -n "${BASE_URL}" ]; then
        DRIVE_CKPT="${GDRIVE_ROOT}/models_cache/checkpoints/${BASE_NAME}"
        COMFY_CKPT="/content/ComfyUI/models/checkpoints/${BASE_NAME}"

        if [ ! -f "${DRIVE_CKPT}" ] && [ ! -f "${COMFY_CKPT}" ]; then
            echo "Downloading Base Checkpoint: ${BASE_NAME} via aria2c..."
            aria2c -c -x 16 -s 16 -k 1M --header="User-Agent: Mozilla/5.0" -d "${GDRIVE_ROOT}/models_cache/checkpoints" -o "${BASE_NAME}" "${BASE_URL}"
        else
            echo "Base Checkpoint cached: ${BASE_NAME}"
        fi

        if [ -f "${DRIVE_CKPT}" ] && [ ! -e "${COMFY_CKPT}" ]; then
            ln -s "${DRIVE_CKPT}" "${COMFY_CKPT}"
        fi
    fi

    # LoRAs
    LORA_COUNT=$(jq '.loras | length' "${MANIFEST_FILE}")
    for ((i=0; i<LORA_COUNT; i++)); do
        LORA_NAME=$(jq -r ".loras[$i].name // empty" "${MANIFEST_FILE}")
        VERSION_ID=$(jq -r ".loras[$i].civitai_version_id // empty" "${MANIFEST_FILE}")

        if [ -z "${LORA_NAME}" ]; then
            continue
        fi

        DRIVE_LORA="${GDRIVE_ROOT}/models_cache/loras/${LORA_NAME}"
        COMFY_LORA="/content/ComfyUI/models/loras/${LORA_NAME}"

        if [ "${VERSION_ID}" != "REPLACE_WITH_VERSION_ID" ] && [ -n "${VERSION_ID}" ]; then
            if [ ! -f "${DRIVE_LORA}" ] && [ ! -f "${COMFY_LORA}" ]; then
                DOWNLOAD_URL="https://civitai.com/api/download/models/${VERSION_ID}?token=${CIVITAI_TOKEN}"
                echo "Downloading LoRA [${LORA_NAME}] (Civitai ID: ${VERSION_ID})..."
                aria2c -c -x 16 -s 16 -k 1M \
                    --header="User-Agent: Mozilla/5.0" \
                    --header="Authorization: Bearer ${CIVITAI_TOKEN}" \
                    --auto-file-renaming=false \
                    -d "${GDRIVE_ROOT}/models_cache/loras" \
                    -o "${LORA_NAME}" \
                    "${DOWNLOAD_URL}" || {
                        echo "Warning: aria2c failed for ${LORA_NAME}. Retrying with curl..."
                        curl -f -L -H "Authorization: Bearer ${CIVITAI_TOKEN}" -o "${DRIVE_LORA}" "${DOWNLOAD_URL}"
                    }
            else
                echo "LoRA cached: ${LORA_NAME}"
            fi
        else
            echo "Skipping placeholder LoRA [${LORA_NAME}] (version_id not set yet)"
        fi

        if [ -f "${DRIVE_LORA}" ] && [ ! -e "${COMFY_LORA}" ]; then
            ln -s "${DRIVE_LORA}" "${COMFY_LORA}"
        fi
    done
else
    echo "Warning: Manifest file ${MANIFEST_FILE} not found."
fi

echo "=== [5/5] Launching Cloudflare Tunnel & ComfyUI Server ==="
if ! command -v cloudflared &> /dev/null; then
    echo "Installing Cloudflared..."
    wget -q -nc https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    dpkg -i cloudflared-linux-amd64.deb > /dev/null 2>&1 || apt-get install -f -y -qq
fi

# Run cloudflared tunnel in background
rm -f /content/cloudflared.log
cloudflared tunnel --url http://127.0.0.1:8188 > /content/cloudflared.log 2>&1 &

echo "Waiting for Cloudflare Tunnel URL..."
TUNNEL_URL=""
for i in {1..20}; do
    sleep 1
    TUNNEL_URL=$(grep -o 'https://[-0-9a-z]*\.trycloudflare\.com' /content/cloudflared.log | head -n 1 || true)
    if [ -n "${TUNNEL_URL}" ]; then
        break
    fi
done

echo "================================================================="
if [ -n "${TUNNEL_URL}" ]; then
    echo " ComfyUI Public Web UI: ${TUNNEL_URL}"
else
    echo " Check tunnel URL manually: cat /content/cloudflared.log"
fi
echo " Generated images will be saved directly to:"
echo "   ${GDRIVE_ROOT}/outputs/raw_renders"
echo "================================================================="

cd /content/ComfyUI
exec python main.py --listen 127.0.0.1 --port 8188 --output-directory "${GDRIVE_ROOT}/outputs/raw_renders"
