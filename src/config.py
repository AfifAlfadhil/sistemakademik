import yaml
import os
from pathlib import Path

def load_config(config_file="config.yaml"):
    # Cari di root project
    base_dir = Path(__file__).resolve().parent.parent
    config_path = os.path.join(base_dir, config_file)
    
    if not os.path.exists(config_path):
        # Fallback jika dijalankan dari root langsung
        config_path = config_file
        
    if not os.path.exists(config_path):
        return {} # Return empty if not found, let defaults handle it
        
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

config = load_config()
