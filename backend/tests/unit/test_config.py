from backend.core.config import settings


def test_settings_has_required_fields() -> None:
    assert hasattr(settings, "DATABASE_URL")
    assert hasattr(settings, "REDIS_URL")
    assert hasattr(settings, "ANTHROPIC_API_KEY")
    assert hasattr(settings, "JWT_SECRET_KEY")
    assert hasattr(settings, "JWT_ALGORITHM")
    assert hasattr(settings, "EMBEDDING_MODEL")
    assert hasattr(settings, "EMBEDDING_DIM")


def test_database_url_uses_asyncpg_or_sqlite() -> None:
    assert "asyncpg" in settings.DATABASE_URL or "sqlite" in settings.DATABASE_URL


def test_embedding_dim_is_384() -> None:
    assert settings.EMBEDDING_DIM == 384


def test_embedding_model_is_minilm() -> None:
    assert "MiniLM" in settings.EMBEDDING_MODEL
