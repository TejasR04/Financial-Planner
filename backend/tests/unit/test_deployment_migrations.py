from pathlib import Path

from alembic.script import ScriptDirectory


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_migration_graph_has_one_head_for_container_startup() -> None:
    script = ScriptDirectory(str(BACKEND_ROOT / "alembic"))
    assert len(script.get_heads()) == 1


def test_runtime_container_migrates_before_starting_api() -> None:
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8")

    command = next(line for line in dockerfile.splitlines() if line.startswith("CMD "))
    assert "python -m alembic upgrade head" in command
    assert command.index("alembic upgrade head") < command.index("uvicorn")


def test_online_migrations_are_serialized() -> None:
    migration_environment = (BACKEND_ROOT / "alembic" / "env.py").read_text(
        encoding="utf-8"
    )

    assert "pg_advisory_xact_lock" in migration_environment
