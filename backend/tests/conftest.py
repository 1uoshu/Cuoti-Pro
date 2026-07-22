import os
from pathlib import Path


os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("DATABASE_URL", "sqlite:///./storage/test_smart_learning_agent.db")

test_database = Path(__file__).resolve().parents[1] / "storage" / "test_smart_learning_agent.db"
test_database.unlink(missing_ok=True)
