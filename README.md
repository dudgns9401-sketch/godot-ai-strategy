# 🎮 Godot AI Strategy - Asset Pipeline

Google Colab의 GPU 자원과 로컬 Godot 4 프로젝트를 Google Drive로 자동 연결하는 서브컬처 스타일 AI 게임 에셋 생성 파이프라인입니다.

---

## 📂 저장소 디렉토리 구조

```text
godot-ai-strategy/
├── .gitignore                     # 모델 및 시크릿 파일 GitHub 업로드 차단
├── README.md                      # 파이프라인 매뉴얼
├── config/
│   ├── lora_manifest.json         # 서브컬처 LoRA 다운로드 리스트 및 가중치 설정
│   └── bridge_config.json         # 로컬 <-> Google Drive 경로 매핑 설정
├── colab/
│   ├── setup_comfy_lora.sh        # Colab VM 내부 ComfyUI + LoRA + aria2c 설치 스크립트
│   └── Colab_AI_Runner.ipynb      # Colab 1-Click 실행 노트북
├── tools/
│   ├── heightmap_converter.py     # 2D 맵 이미지를 Godot 4용 16-bit 3D Heightmap/Normalmap으로 변환
│   └── sync_from_drive.py         # Google Drive 에셋을 Godot 프로젝트로 자동 동기화
└── godot_project/
    ├── project.godot              # Godot 4 프로젝트 설정 파일 (Forward+)
    └── assets/
        ├── art_2d/                # ComfyUI 생성 캐릭터/일러스트 에셋
        ├── terrain_3d/            # 16-bit 높이맵 및 노멀맵
        └── shaders/
            └── terrain_displacement.gdshader  # 3D 지형 디스플레이스먼트 셰이더
```

---

## ⚡ 빠른 시작 가이드 (Quick Start)

### 1. Google Drive 브리지 준비
- Google Drive 데스크톱이 설치되어 있다면 드라이브 루트(예: `G:\내 드라이브\`)에 `AI_GameDev_Bridge` 폴더를 생성하거나, 미설치 시 프로젝트 내부의 `_gdrive_mock/AI_GameDev_Bridge` 폴더가 임시 브리지로 작동합니다.
- Civitai 모델 자동 다운로드가 필요한 경우, 브리지 폴더 내 `.env.example`을 복사하여 `.env`를 만들고 API 토큰을 입력합니다:
  ```bash
  CIVITAI_TOKEN=your_civitai_api_token_here
  ```

### 2. Google Colab에서 ComfyUI 실행
1. GitHub 저장소의 `colab/Colab_AI_Runner.ipynb`를 Colab에서 엽니다.
2. 런타임 유형을 **T4 GPU**로 설정합니다.
3. 셀을 순서대로 실행하면:
   - Google Drive가 마운트됩니다.
   - Base Checkpoint(`animagine-xl-3.1`) 및 LoRA 모델이 고속(`aria2c`) 다운로드되어 Drive에 영구 캐시됩니다.
   - Cloudflare Tunnel을 통해 외부 접속 가능한 Web UI 링크(`*.trycloudflare.com`)가 출력됩니다.
   - 생성된 모든 이미지는 Google Drive의 `outputs/raw_renders/`에 실시간 자동 저장됩니다.

### 3. 로컬 에셋 동기화 및 3D 지형 변환
로컬 PC 터미널에서 다음 명령을 실행하여 Google Drive에 생성된 에셋을 Godot 프로젝트로 가져옵니다:

```bash
python tools/sync_from_drive.py
```

- `outputs/raw_renders/`의 그림은 `godot_project/assets/art_2d/`로 복사됩니다.
- `outputs/maps_2d/`의 지형 그림은 자동으로 16-bit `*_heightmap.png`와 `*_normalmap.png`로 변환되어 `godot_project/assets/terrain_3d/`에 저장됩니다.

단독으로 2D 이미지를 3D 높이맵/노멀맵으로 변환하려면:
```bash
python tools/heightmap_converter.py --input path/to/map.png --blur-radius 5
```

### 4. Godot 4에서 3D 지형 적용
1. Godot 4.x 에디터로 `godot_project/project.godot`를 엽니다.
2. 3D 씬을 만들고 `MeshInstance3D`를 추가한 후 `PlaneMesh`를 할당합니다 (Subdivide Width/Depth를 128~256 정도로 지정).
3. `assets/shaders/terrain_displacement.gdshader`를 `ShaderMaterial`로 지정합니다.
4. `heightmap` 슬롯에 생성된 `*_heightmap.png`, `normalmap` 슬롯에 `*_normalmap.png`를 연결하면 고품질 3D 지형이 렌더링됩니다.
