from click.testing import CliRunner

from alphapulse.cli import cli


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "1.0.0" in result.output


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "market" in result.output
    assert "content" in result.output
    assert "briefing" in result.output


def test_market_group_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["market", "--help"])
    assert result.exit_code == 0


def test_content_group_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["content", "--help"])
    assert result.exit_code == 0


def test_briefing_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["briefing", "--help"])
    assert result.exit_code == 0
