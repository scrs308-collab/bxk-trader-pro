import importlib.util
from pathlib import Path
import sys
from unittest.mock import Mock
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('start_runtime',ROOT/'scripts/start_runtime.py')
start=importlib.util.module_from_spec(spec);spec.loader.exec_module(start)
sys.modules['start_runtime']=start
spec=importlib.util.spec_from_file_location('prepare_runtime',ROOT/'scripts/prepare_runtime.py')
prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)


def test_production_default(monkeypatch):
    monkeypatch.delenv('BXK_ISOLATED_STAGING',raising=False)
    assert start.isolated() is False
    execute=Mock();monkeypatch.setattr(start.os,'execv',execute)
    start.main()
    assert 'server:app' in execute.call_args.args[1]


def test_isolated_runtime_requires_safe_flags(monkeypatch):
    monkeypatch.setenv('BXK_ISOLATED_STAGING','true')
    monkeypatch.setenv('BXK_PREVIEW_MODE','true')
    monkeypatch.setenv('BXK_LIVE_TRADING_ENABLED','false')
    assert start.isolated()
    execute=Mock();monkeypatch.setattr(start.os,'execv',execute);start.main()
    assert 'staging_preview:app' in execute.call_args.args[1]
    monkeypatch.setenv('BXK_LIVE_TRADING_ENABLED','true')
    with pytest.raises(RuntimeError):start.main()
    assert execute.call_count==1


def test_production_migrates_isolated_does_not(monkeypatch):
    run=Mock();monkeypatch.setattr(prepare.subprocess,'run',run)
    monkeypatch.delenv('BXK_ISOLATED_STAGING',raising=False)
    prepare.main()
    assert run.call_count==2
    assert run.call_args_list[0].args[0][-1]=='--probe'
    assert run.call_args_list[1].args[0][-3:]==['alembic','upgrade','head']
    run.reset_mock()
    monkeypatch.setenv('BXK_ISOLATED_STAGING','true')
    monkeypatch.setenv('BXK_PREVIEW_MODE','true')
    monkeypatch.setenv('BXK_LIVE_TRADING_ENABLED','false')
    prepare.main()
    assert run.call_count==1 and '--probe' not in run.call_args.args[0]
