import os
from pathlib import Path


os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("DATABASE_URL", "sqlite:///./storage/test_smart_learning_agent.db")
os.environ.setdefault("POW_DIFFICULTY", "1")
os.environ["PLUGIN_MODULES"] = (
    "app.plugins.example,"
    "app.plugins.mastery_tracking,"
    "app.plugins.wrong_question_book,"
    "app.plugins.assignment_grading,"
    "app.plugins.layered_practice,"
    "app.plugins.stage_assessment,"
    "app.plugins.learning_dashboard,"
    "app.plugins.learning_insights"
)

test_database = Path(__file__).resolve().parents[1] / "storage" / "test_smart_learning_agent.db"
test_database.unlink(missing_ok=True)
