"""Railway rejects more than one pre-deploy command at deployment time."""
from pathlib import Path
import tomllib


def test_railway_predeploy_command_limit():
    config = tomllib.loads((Path(__file__).resolve().parents[1] / "railway.toml").read_text())
    command = config.get("deploy", {}).get("preDeployCommand", [])
    assert isinstance(command, (str, list))
    if isinstance(command, list):
        assert len(command) <= 1, "Railway permits at most one pre-deploy command"
