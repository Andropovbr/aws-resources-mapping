import sys
import pytest
from pathlib import Path
from src.main import run_pipeline, main

def test_run_pipeline_end_to_end(tmp_path: Path):
    csv_file = tmp_path / "resources.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row = "alb-test,arn:aws:elasticloadbalancing:ca-central-1:807445251352:loadbalancer/app/alb-test/1,elasticloadbalancing:loadbalancer,ca-central-1,807445251352,-,AWS::ElasticLoadBalancingV2::LoadBalancer,2026-10-10,elasticloadbalancing,0\n"
    csv_file.write_text(header + row, encoding="utf-8")
    
    out_dir = tmp_path / "output"
    
    excel_path, md_path = run_pipeline(
        input_dir=str(tmp_path),
        output_dir=str(out_dir),
        account="multicanais-dev"
    )
    
    assert Path(excel_path).exists()
    assert Path(md_path).exists()

def test_run_pipeline_empty_dir_raises_error(tmp_path: Path):
    out_dir = tmp_path / "output"
    with pytest.raises(ValueError, match="Nenhum recurso encontrado"):
        run_pipeline(
            input_dir=str(tmp_path),
            output_dir=str(out_dir),
            account="multicanais-dev"
        )

def test_main_cli(tmp_path: Path, monkeypatch):
    csv_file = tmp_path / "resources.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row = "alb-test,arn:aws:elasticloadbalancing:ca-central-1:807445251352:loadbalancer/app/alb-test/1,elasticloadbalancing:loadbalancer,ca-central-1,807445251352,-,AWS::ElasticLoadBalancingV2::LoadBalancer,2026-10-10,elasticloadbalancing,0\n"
    csv_file.write_text(header + row, encoding="utf-8")
    
    out_dir = tmp_path / "output"
    test_args = [
        "src/main.py",
        "--input-dir", str(tmp_path),
        "--output-dir", str(out_dir),
        "--account", "test-account"
    ]
    monkeypatch.setattr(sys, "argv", test_args)
    main()
    
    assert (out_dir / "inventario_test-account.xlsx").exists()
    assert (out_dir / "relatorio_test-account.md").exists()

def test_main_cli_default_account_autodetect(tmp_path: Path, monkeypatch):
    csv_file = tmp_path / "resources.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row = "alb-test,arn:aws:elasticloadbalancing:ca-central-1:807445251352:loadbalancer/app/alb-test/1,elasticloadbalancing:loadbalancer,ca-central-1,807445251352,-,AWS::ElasticLoadBalancingV2::LoadBalancer,2026-10-10,elasticloadbalancing,0\n"
    csv_file.write_text(header + row, encoding="utf-8")
    
    out_dir = tmp_path / "output"
    test_args = [
        "src/main.py",
        "--input-dir", str(tmp_path),
        "--output-dir", str(out_dir)
    ]
    monkeypatch.setattr(sys, "argv", test_args)
    main()
    
    assert (out_dir / "inventario_807445251352.xlsx").exists()
    assert (out_dir / "relatorio_807445251352.md").exists()

def test_main_cli_account_sanitization(tmp_path: Path, monkeypatch):
    csv_file = tmp_path / "resources.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row = "alb-test,arn:aws:elasticloadbalancing:ca-central-1:12345:loadbalancer/app/alb-test/1,elasticloadbalancing:loadbalancer,ca-central-1,12345,-,AWS::ElasticLoadBalancingV2::LoadBalancer,2026-10-10,elasticloadbalancing,0\n"
    csv_file.write_text(header + row, encoding="utf-8")
    
    out_dir = tmp_path / "output"
    test_args = [
        "src/main.py",
        "--input-dir", str(tmp_path),
        "--output-dir", str(out_dir),
        "--account", "acct/prod:team*1"
    ]
    monkeypatch.setattr(sys, "argv", test_args)
    main()
    
    assert (out_dir / "inventario_acct_prod_team_1.xlsx").exists()
    assert (out_dir / "relatorio_acct_prod_team_1.md").exists()

def test_main_cli_error_exit(tmp_path: Path, monkeypatch):
    empty_in = tmp_path / "empty_dir"
    empty_in.mkdir()
    out_dir = tmp_path / "output"
    test_args = [
        "src/main.py",
        "--input-dir", str(empty_in),
        "--output-dir", str(out_dir),
    ]
    monkeypatch.setattr(sys, "argv", test_args)
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 1
