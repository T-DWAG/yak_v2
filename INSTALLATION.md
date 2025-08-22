# Installation Guide

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Prepare Model Files
Place your YOLO model files in the `data/` directory:
- `best.pt` - Your trained YOLO model
- Or modify the model path in `src/group3.py`

### 3. Run the Application
```bash
python run.py
```

Access the web interface at: http://127.0.0.1:5000

## Manual Installation

### 1. Clone and Setup
```bash
git clone https://github.com/yourusername/yak-similarity-analyzer.git
cd yak-similarity-analyzer
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -e .
```

### 3. Initialize License System
```bash
python tools/generate_initial_license.py
```

### 4. Generate Client Key (for testing)
```bash
python tools/client_key_generator.py
```

### 5. Generate Provider Key
```bash
python tools/provider_key_generator.py path/to/client_key.json
```

## System Requirements

- Python 3.9+
- 4GB+ RAM
- GPU recommended for YOLO inference
- Windows/Linux/macOS

## Configuration

- Model path: Edit `src/group3.py`
- Upload directory: Edit `src/app.py`
- License settings: Edit `src/license_manager_simple.py`

## Troubleshooting

### ModuleNotFoundError: 'ultralytics'
```bash
pip install ultralytics torch torchvision
```

### Model file not found
Place your YOLO model in `data/best.pt` or update the path in the code.

### License validation failed
Ensure your provider key is properly generated and placed in the correct directory.