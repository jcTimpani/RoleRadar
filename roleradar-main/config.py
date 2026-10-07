import yaml
import os

# Get path to config.yaml relative to this file
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')

# Load the configuration
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)
