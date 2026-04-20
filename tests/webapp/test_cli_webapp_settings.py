"""ap webapp settings CLI."""
from click.testing import CliRunner
from cryptography.fernet import Fernet

from alphapulse.cli import cli


def test_init_encrypt_key_prints_key(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    r = CliRunner().invoke(cli, ["webapp", "init-encrypt-key"])
    assert r.exit_code == 0
    assert "WEBAPP_ENCRYPT_KEY=" in r.output


def test_set_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    fk = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("WEBAPP_ENCRYPT_KEY", fk)

    r1 = CliRunner().invoke(
        cli,
        ["webapp", "set",
         "--key", "KIS_APP_KEY", "--value", "myvalue",
         "--category", "api_key", "--secret"],
    )
    assert r1.exit_code == 0

    r2 = CliRunner().invoke(
        cli, ["webapp", "list", "--category", "api_key"],
    )
    assert r2.exit_code == 0
    assert "KIS_APP_KEY" in r2.output
    assert "myvalue" not in r2.output  # 마스킹


def test_list_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    fk = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("WEBAPP_ENCRYPT_KEY", fk)
    r = CliRunner().invoke(cli, ["webapp", "list"])
    assert r.exit_code == 0
    assert "설정 없음" in r.output or "None" in r.output or "설정" in r.output


def test_rotate_encrypt_key(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    old_k = Fernet.generate_key().decode("utf-8")
    new_k = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("WEBAPP_ENCRYPT_KEY", old_k)
    # seed
    CliRunner().invoke(cli, [
        "webapp", "set", "--key", "K", "--value", "v",
        "--category", "risk_limit", "--plain",
    ])
    r = CliRunner().invoke(
        cli,
        ["webapp", "rotate-encrypt-key", "--new-key", new_k],
    )
    assert r.exit_code == 0
    assert "Rotated" in r.output
