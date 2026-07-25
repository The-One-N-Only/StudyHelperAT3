import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Shared Flask app instance for all tests to avoid SQLAlchemy model conflicts
from backend import create_app

flask_app = create_app()
