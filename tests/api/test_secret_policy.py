import pytest

from open_notebook.utils.secret_policy import classify_secret

SECRET_VARS = (
    "OPEN_NOTEBOOK_PASSWORD",
    "OPEN_NOTEBOOK_PASSWORD_FILE",
    "OPEN_NOTEBOOK_ENCRYPTION_KEY",
    "OPEN_NOTEBOOK_ENCRYPTION_KEY_FILE",
    "SURREAL_PASSWORD",
    "SURREAL_PASS",
)

GOOD = "q7Vx-2mPz9Lr4Tn8Kd3W"


@pytest.mark.parametrize(
    "value",
    [
        # .env.example
        "CHANGE_ME_TO_A_STRONG_PASSWORD",
        "CHANGE_ME_TO_A_LONG_RANDOM_SECRET",
        "CHANGE_ME_TO_A_LONG_RANDOM_DB_PASSWORD",
        # .env.hardened
        "⚠️_CAMBIAR_ESTO_contraseña_de_acceso",
        "⚠️_CAMBIAR_ESTO_cadena_aleatoria_de_32_caracteres_minimo",
        # examples/ and documentation
        "change-me-to-a-secret-string",
        "open-notebook-change-me",
        "your_secure_password",
        "your-secret-encryption-key",
        "your-strong-secret-key",
        "my-secret-passphrase",
        "my-secret",
        "MySecure2024!Research#Tool",
        "Notebook$Dev$2024$Strong!",
        "change-this-strong-password",
        "change-this-secret",
        "my-dev-secret-key",
        "secure_password",
    ],
)
def test_placeholders_are_detected(value):
    assert classify_secret(value) == "placeholder"


@pytest.mark.parametrize("value", ["root", "admin", "password123", "opennotebook", "Password"])
def test_weak_values_are_detected(value):
    assert classify_secret(value) == "weak"


def test_short_value_is_flagged():
    assert classify_secret("Ab3-xyz") == "short"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_value_is_not_classified(value):
    assert classify_secret(value) is None


@pytest.mark.parametrize("value", [GOOD, "kP9fV2qL7zXc4Rt1Wm8Yb6Na", "correct horse battery staple"])
def test_random_values_are_accepted(value):
    assert classify_secret(value) is None


@pytest.fixture
def clean_env(monkeypatch):
    for var in SECRET_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_startup_rejects_placeholder_password(clean_env):
    from api.main import _check_secret_values

    clean_env.setenv("OPEN_NOTEBOOK_PASSWORD", "CHANGE_ME_TO_A_STRONG_PASSWORD")
    clean_env.setenv("OPEN_NOTEBOOK_ENCRYPTION_KEY", GOOD)
    with pytest.raises(RuntimeError, match="OPEN_NOTEBOOK_PASSWORD"):
        _check_secret_values()


def test_startup_rejects_placeholder_encryption_key(clean_env):
    from api.main import _check_secret_values

    clean_env.setenv("OPEN_NOTEBOOK_PASSWORD", GOOD)
    clean_env.setenv("OPEN_NOTEBOOK_ENCRYPTION_KEY", "change-me-to-a-secret-string")
    with pytest.raises(RuntimeError, match="OPEN_NOTEBOOK_ENCRYPTION_KEY"):
        _check_secret_values()


def test_startup_rejects_weak_password(clean_env):
    from api.main import _check_secret_values

    clean_env.setenv("OPEN_NOTEBOOK_PASSWORD", "admin")
    with pytest.raises(RuntimeError, match="weak"):
        _check_secret_values()


def test_startup_rejects_placeholder_from_secret_file(clean_env, tmp_path):
    from api.main import _check_secret_values

    secret_file = tmp_path / "password"
    secret_file.write_text("your_secure_password\n")
    clean_env.setenv("OPEN_NOTEBOOK_PASSWORD_FILE", str(secret_file))
    with pytest.raises(RuntimeError, match="OPEN_NOTEBOOK_PASSWORD"):
        _check_secret_values()


def test_startup_rejects_placeholder_db_password(clean_env):
    from api.main import _check_secret_values

    clean_env.setenv("OPEN_NOTEBOOK_PASSWORD", GOOD)
    clean_env.setenv("SURREAL_PASSWORD", "CHANGE_ME_TO_A_LONG_RANDOM_DB_PASSWORD")
    with pytest.raises(RuntimeError, match="SURREAL_PASSWORD"):
        _check_secret_values()


def test_startup_only_warns_for_weak_db_password(clean_env):
    from api.main import _check_secret_values

    clean_env.setenv("OPEN_NOTEBOOK_PASSWORD", GOOD)
    clean_env.setenv("OPEN_NOTEBOOK_ENCRYPTION_KEY", GOOD)
    clean_env.setenv("SURREAL_PASSWORD", "root")
    _check_secret_values()


def test_startup_accepts_random_secrets(clean_env):
    from api.main import _check_secret_values

    clean_env.setenv("OPEN_NOTEBOOK_PASSWORD", GOOD)
    clean_env.setenv("OPEN_NOTEBOOK_ENCRYPTION_KEY", "kP9fV2qL7zXc4Rt1Wm8Yb6Na")
    clean_env.setenv("SURREAL_PASSWORD", "Zr5-Hq2Lm8Tv3Xc7")
    _check_secret_values()


def test_startup_allows_missing_password_check_to_handle_unset(clean_env):
    """An unset password is handled by the existing fail-closed check, not here."""
    from api.main import _check_secret_values

    _check_secret_values()
