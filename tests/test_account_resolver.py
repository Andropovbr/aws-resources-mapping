import json
import pytest
from pathlib import Path
from src.account_resolver import AccountInfo, load_account_mappings, resolve_account_info

def test_account_info_display_and_slug():
    # Both name and id present
    info1 = AccountInfo(account_id="807445251352", account_name="multicanais-dev")
    assert info1.display_title == "Conta multicanais-dev (807445251352)"
    assert info1.file_slug == "multicanais-dev"

    # Only id present (no name)
    info2 = AccountInfo(account_id="807445251352", account_name=None)
    assert info2.display_title == "Conta 807445251352"
    assert info2.file_slug == "807445251352"

    # Name equals id
    info3 = AccountInfo(account_id="807445251352", account_name="807445251352")
    assert info3.display_title == "Conta 807445251352"
    assert info3.file_slug == "807445251352"

def test_load_account_mappings(tmp_path: Path):
    config = tmp_path / "accounts.json"
    config.write_text(json.dumps({"111": "conta-1", "222": "conta-2"}), encoding="utf-8")
    
    mapping = load_account_mappings(config)
    assert mapping == {"111": "conta-1", "222": "conta-2"}

def test_load_account_mappings_missing_file(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist.json"
    mapping = load_account_mappings(non_existent)
    assert mapping == {}

def test_resolve_with_config_match(tmp_path: Path):
    config = tmp_path / "accounts.json"
    config.write_text(json.dumps({"807445251352": "multicanais-dev"}), encoding="utf-8")

    # Match by raw_account_id
    info = resolve_account_info(account_arg="", raw_account_id="807445251352", config_path=config)
    assert info.account_id == "807445251352"
    assert info.account_name == "multicanais-dev"
    assert info.display_title == "Conta multicanais-dev (807445251352)"
    assert info.file_slug == "multicanais-dev"

    # Match by account_arg as ID
    info2 = resolve_account_info(account_arg="807445251352", raw_account_id="", config_path=config)
    assert info2.account_id == "807445251352"
    assert info2.account_name == "multicanais-dev"

    # Match by account_arg as Name
    info3 = resolve_account_info(account_arg="multicanais-dev", raw_account_id="", config_path=config)
    assert info3.account_id == "807445251352"
    assert info3.account_name == "multicanais-dev"

def test_resolve_folder_inference(tmp_path: Path):
    contas_dir = tmp_path / "contas" / "multicanais-dev"
    contas_dir.mkdir(parents=True)
    
    empty_config = tmp_path / "empty.json"
    empty_config.write_text("{}", encoding="utf-8")

    info = resolve_account_info(
        account_arg="",
        raw_account_id="807445251352",
        input_dir=str(contas_dir),
        config_path=empty_config
    )
    assert info.account_id == "807445251352"
    assert info.account_name == "multicanais-dev"
    assert info.display_title == "Conta multicanais-dev (807445251352)"
    assert info.file_slug == "multicanais-dev"

def test_resolve_unknown_account_fallback(tmp_path: Path):
    empty_config = tmp_path / "empty.json"
    empty_config.write_text("{}", encoding="utf-8")

    info = resolve_account_info(
        account_arg="",
        raw_account_id="999888777666",
        input_dir=str(tmp_path),
        config_path=empty_config
    )
    assert info.account_id == "999888777666"
    assert info.account_name is None
    assert info.display_title == "Conta 999888777666"
    assert info.file_slug == "999888777666"
