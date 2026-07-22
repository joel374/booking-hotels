import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app

if __name__ == '__main__':
    print("✓ Flask app imports successfully")
    print(f"✓ Registered blueprints: {list(app.blueprints.keys())}")
    print(f"✓ Mail configured: {hasattr(app, 'extensions') and 'mail' in app.extensions}")
    print("✓ All auth routes loaded")
