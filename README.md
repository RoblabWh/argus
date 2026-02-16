![Argus Logo](https://github.com/RoblabWh/argus/blob/main/frontend/src/assets/Argus_icon_dark_title-long_white_BG_scaled.PNG?raw=true)

# ARGUS - Aerial Rescue and Geospatial Utility System

ARGUS is a web application for structured documentation and analysis of drone images in rescue operations. It creates orthophotos from UAV mapping flights (RGB and thermal/IR), presents flight data in a structured manner, evaluates infrared imagery, and offers object detection using custom-trained neural networks. An integrated local LLM (Ollama) can automatically generate scene descriptions.

ARGUS runs as a multi-container Docker application and is accessible from any device on the same network. It is recommended to use a Chromium-based browser.

> **Note:** ARGUS is developed at [Westphalian University of Applied Sciences](https://www.w-hs.de/) as part of the [E-DRZ](https://rettungsrobotik.de/e-drz/) research project. It is intended for scientific use and does not offer the reliability of commercial software.

> **360 Video Support:** The previous version of ARGUS supported 360 video processing (path reconstruction, partial point clouds, panoramic tours). This feature is being ported to the new architecture and will be available soon. If you need 360 support now, use the [previous version](https://github.com/RoblabWh/argus/tree/b3577000c26dcc3b26be9e8dd48b6b99623cfd73).

---

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [WebODM Integration (Optional)](#webodm-integration-optional)
- [Image & Metadata Requirements](#image--metadata-requirements)
- [Architecture Overview](#architecture-overview)
- [Known Issues](#known-issues)
- [Example Data](#example-data)
- [Papers](#papers)

---

## Features

- **Orthophoto Generation** — Built-in fast mapping pipeline that handles both nadir and angled camera orientations using perspective-correct projection
- **Thermal/IR Analysis** — Temperature matrix extraction, IR overlays, and hotspot detection
- **Object Detection** — Two detection backends: a custom Transformer-based model trained on rescue scenarios and a YOLO based with models still in development
- **AI Scene Descriptions** — Local LLM (Ollama with LLaVA) generates automatic image descriptions
- **WebODM Integration** — Optional high-quality orthophoto generation via OpenDroneMap
- **Weather Data** — Automatic weather context via OpenWeatherMap API

## Prerequisites

- **Docker** & **Docker Compose** — [Installation guide](https://docs.docker.com/engine/install/)
- **Git** (with submodule support)
- **(Optional) NVIDIA Container Toolkit** — [Installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) — enables GPU-accelerated detection and LLM inference. Without it, everything runs on CPU.

**Supported platforms:** Linux (primary), Windows (via `start-win-argus.cmd` / PowerShell wrapper)

## Installation

1. Clone the repository with submodules:
   ```bash
   git clone --recursive https://github.com/RoblabWh/argus.git
   cd argus
   ```
   If you already cloned without `--recursive`:
   ```bash
   git submodule update --init --recursive
   ```

2. Start ARGUS:
   ```bash
   ./argus.sh up --build
   ```
   The first build takes several minutes. On the first launch a `.env` file is created automatically from `.env.example`.

3. Open in browser: `http://<your-ip>:5173`

The startup script (`argus.sh`) automatically detects your local IP, checks for NVIDIA GPU support, and selects the appropriate Docker Compose configuration.

## Configuration

The `.env` file in the project root controls all settings. It is created automatically on first launch. Key variables:

| Variable | Default | Description |
|---|---|---|
| `PORT_API` | `8008` | API backend port |
| `PORT_FRONTEND` | `5173` | Frontend port (open this in your browser) |
| `PORT_DB` | `5433` | PostgreSQL port on host |
| `OPEN_WEATHER_API_KEY` | *(empty)* | [OpenWeatherMap](https://openweathermap.org/) API key for weather data |
| `ENABLE_WEBODM` | `false` | Enable WebODM integration (see [below](#webodm-integration-optional)) |
| `VITE_API_URL` | *(auto-detected)* | Backend URL — set automatically by `argus.sh` |

The IP address is auto-detected on every start. Use `--keep-ip` to preserve a manually set `VITE_API_URL`:
```bash
./argus.sh up --build --keep-ip
```

After editing `.env` manually, restart the containers for changes to take effect.

## Usage

```bash
# Start all services (builds if needed)
./argus.sh up --build

# Start without rebuilding
./argus.sh up

# Stop all services
./argus.sh down
#or simply in the running terminal
crtl + c

# Windows
start-win-argus.cmd up --build
```

**Workflow:**
1. Create a group and a report in the web UI
2. Upload drone images (RGB and/or thermal)
3. Click **Process** — images are preprocessed, then an orthophoto is generated
4. Optionally run **Detection** to identify objects in the images
5. Optionally run **Auto Description** for AI-generated scene summaries


## WebODM Integration (Optional)

For high-quality orthophoto generation via [OpenDroneMap](https://www.opendronemap.org/):

1. Clone WebODM separately: [github.com/OpenDroneMap/WebODM](https://github.com/OpenDroneMap/WebODM)
2. Set the following in your `.env`:
   ```
   ENABLE_WEBODM=true
   WEBODM_PATH=/path/to/WebODM
   WEBODM_USERNAME=your_username
   WEBODM_PASSWORD=your_password
   ```
3. `argus.sh` will start WebODM automatically alongside ARGUS.

## Image & Metadata Requirements

ARGUS can display images from various cameras/drones. For orthophoto generation, the following EXIF metadata is used:

| Required | Field | Notes |
|---|---|---|
| Yes | GPS latitude & longitude | |
| Yes | Image width & height | Extracted automatically |
| Yes | Creation date/time | |
| Recommended | Relative altitude (AGL) | If missing, a default can be set on upload |
| Recommended | Field of view (FOV) | |
| Recommended | Gimbal yaw, pitch, roll | Camera/gimbal orientation |
| Recommended | UAV yaw, pitch, roll | Drone body orientation |
| Optional | Camera model name | Used to look up per-model EXIF key mappings in `api/app/cameramodels.json` |
| Optional | Projection type | Used to filter out panoramic images |

**Thermal/IR images** are identified by:
- An `ImageSource` EXIF tag containing "thermal" or "infrared" (preferred)
- Alternatively: image dimensions or filename pattern (configurable per camera model)

Currently tested with DJI drones (M30T, Mavic Enterprise, Mavic 2, Mavic 3). Other drones may work if they provide the required metadata.

## Architecture Overview

ARGUS consists of the following Docker services:

| Service | Description |
|---|---|
| `api` | FastAPI backend (Python 3.12) with documentation under `http://<your-ip>:8008/docs`|
| `frontend` | React frontend (Vite) |
| `db` | PostgreSQL 16 |
| `redis` | Task queue broker & progress tracking |
| `argus_mapping_worker` | Celery worker for orthophoto generation |
| `argus_detection_worker` | Celery worker for Transformer-based detection |
| `argus_yolo_worker` | Celery worker for experimental YOLO detection |
| `argus_ollama_worker` | Celery worker for LLM image descriptions |
| `ollama` | Local LLM server (LLaVA, Llama 3.2) |

Database migrations are handled automatically via Alembic on startup.

## Known Issues

- Firefox may have problems uploading large files (e.g., high-resolution panoramic photos). Use a Chromium-based browser.
- Running multiple processing tasks simultaneously can lead to unexpected behavior.
- Primarily tested with DJI drones. Other manufacturers may require adding camera model definitions to `api/app/cameramodels.json`.
- Some older Linux distributions use `docker-compose` (hyphenated) instead of `docker compose`. ARGUS requires the modern `docker compose` plugin syntax.

## Example Data

- **Processed example project:** coming soon
- **Demo video:** [ARGUS on YouTube](https://www.youtube.com/watch?v=7CUPtE3lJ6U) (german)

## Papers

1. Redefining Recon: Bridging Gaps with UAVs, 360 Cameras, and Neural Radiance Fields — Surmann et al., [IEEE SSRR 2023, Fukushima](https://github.com/RoblabWh/argus/blob/main/papers/ssrr2023-surmann.pdf)
2. UAVs and Neural Networks for search and rescue missions — Surmann et al., [ISR Europe 2023](https://arxiv.org/abs/2310.05512)
3. Lessons from Robot-Assisted Disaster Response Deployments — Surmann et al., [Journal of Field Robotics, 2023](https://onlinelibrary.wiley.com/doi/full/10.1002/rob.22275)
4. Deployment of Aerial Robots during the Flood Disaster in Erftstadt/Blessem — Surmann et al., [ICARA 2022](https://ieeexplore.ieee.org/document/9738529)
5. Deployment of Aerial Robots after a major fire of an industrial hall — Surmann et al., [IEEE SSRR 2021](https://ieeexplore.ieee.org/document/9597677)

---

*Developed at [Westphalian University of Applied Sciences](https://www.w-hs.de/) — [RobLab](https://roblab.2morrow-tec.de/) | Funded by the German Feederal Ministry of Research, Technology and Space (BMFTR)*
