import os
import sys
import pytest
from fastapi.testclient import TestClient

# Stelle sicher, dass der Projektroot im sys.path ist, damit 'api' importierbar ist
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.index import app

@pytest.fixture(scope="session")
def client():
    return TestClient(app)
