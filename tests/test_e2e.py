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
    
    excel_path, md_path, finops_path, orphan_path, topology_path = run_pipeline(
        input_dir=str(tmp_path),
        output_dir=str(out_dir),
        account="testaccount"
    )
    
    assert Path(excel_path).exists()
    assert Path(excel_path).parent.name == "spreadsheets"
    assert Path(md_path).exists()
    assert Path(md_path).parent.name == "markdowns"
    assert Path(finops_path).exists()
    assert Path(finops_path).name == "relatorio_oportunidades_finops_testaccount.md"
    assert Path(finops_path).parent.name == "markdowns"
    opp_content = Path(finops_path).read_text(encoding="utf-8")
    assert "Relatório Executivo de Oportunidades FinOps" in opp_content
    assert "Scorecard Executivo & Impacto Financeiro" in opp_content
    assert "Playbooks Práticos de Investigação" in opp_content

    assert Path(orphan_path).exists()
    assert Path(orphan_path).name == "relatorio_recursos_orfaos_testaccount.md"
    assert Path(orphan_path).parent.name == "markdowns"
    orphan_content = Path(orphan_path).read_text(encoding="utf-8")
    assert "Relatório Executivo de Identificação de Recursos Órfãos" in orphan_content
    assert "Scorecard Executivo de Recursos Órfãos" in orphan_content
    assert "Playbooks Práticos" in orphan_content

    assert Path(topology_path).exists()
    assert Path(topology_path).name == "relatorio_arquitetura_aplicacoes_testaccount.md"
    assert Path(topology_path).parent.name == "markdowns"
    topo_content = Path(topology_path).read_text(encoding="utf-8")
    assert "Relatório de Arquitetura de Aplicações, Topologia e Governança" in topo_content

    # DOCX reports verification in output/docs/
    docs_dir = out_dir / "docs"
    assert (docs_dir / "relatorio_testaccount.docx").exists()
    assert (docs_dir / "relatorio_oportunidades_finops_testaccount.docx").exists()
    assert (docs_dir / "relatorio_recursos_orfaos_testaccount.docx").exists()
    assert (docs_dir / "relatorio_arquitetura_aplicacoes_testaccount.docx").exists()

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
    
    assert (out_dir / "spreadsheets" / "inventario_test-account.xlsx").exists()
    assert (out_dir / "markdowns" / "relatorio_test-account.md").exists()
    assert (out_dir / "markdowns" / "relatorio_oportunidades_finops_test-account.md").exists()
    assert (out_dir / "markdowns" / "relatorio_recursos_orfaos_test-account.md").exists()
    assert (out_dir / "markdowns" / "relatorio_arquitetura_aplicacoes_test-account.md").exists()
    assert (out_dir / "docs" / "relatorio_test-account.docx").exists()
    assert (out_dir / "docs" / "relatorio_oportunidades_finops_test-account.docx").exists()
    assert (out_dir / "docs" / "relatorio_recursos_orfaos_test-account.docx").exists()
    assert (out_dir / "docs" / "relatorio_arquitetura_aplicacoes_test-account.docx").exists()

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
    
    # 807445251352 is resolved to multicanais-dev via accounts.json
    assert (out_dir / "spreadsheets" / "inventario_multicanais-dev.xlsx").exists()
    assert (out_dir / "markdowns" / "relatorio_multicanais-dev.md").exists()
    assert (out_dir / "markdowns" / "relatorio_oportunidades_finops_multicanais-dev.md").exists()
    assert (out_dir / "markdowns" / "relatorio_recursos_orfaos_multicanais-dev.md").exists()
    assert (out_dir / "markdowns" / "relatorio_arquitetura_aplicacoes_multicanais-dev.md").exists()
    assert (out_dir / "docs" / "relatorio_multicanais-dev.docx").exists()
    assert (out_dir / "docs" / "relatorio_arquitetura_aplicacoes_multicanais-dev.docx").exists()

def test_main_cli_unmapped_account_id_fallback(tmp_path: Path, monkeypatch):
    csv_file = tmp_path / "resources.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row = "alb-test,arn:aws:elasticloadbalancing:ca-central-1:999888777666:loadbalancer/app/alb-test/1,elasticloadbalancing:loadbalancer,ca-central-1,999888777666,-,AWS::ElasticLoadBalancingV2::LoadBalancer,2026-10-10,elasticloadbalancing,0\n"
    csv_file.write_text(header + row, encoding="utf-8")
    
    out_dir = tmp_path / "output"
    test_args = [
        "src/main.py",
        "--input-dir", str(tmp_path),
        "--output-dir", str(out_dir)
    ]
    monkeypatch.setattr(sys, "argv", test_args)
    main()
    
    # Unmapped ID keeps numeric ID in filename
    assert (out_dir / "spreadsheets" / "inventario_999888777666.xlsx").exists()
    assert (out_dir / "markdowns" / "relatorio_999888777666.md").exists()
    assert (out_dir / "markdowns" / "relatorio_oportunidades_finops_999888777666.md").exists()
    assert (out_dir / "markdowns" / "relatorio_recursos_orfaos_999888777666.md").exists()
    assert (out_dir / "markdowns" / "relatorio_arquitetura_aplicacoes_999888777666.md").exists()
    assert (out_dir / "docs" / "relatorio_999888777666.docx").exists()
    assert (out_dir / "docs" / "relatorio_arquitetura_aplicacoes_999888777666.docx").exists()

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
    
    assert (out_dir / "spreadsheets" / "inventario_acct_prod_team_1.xlsx").exists()
    assert (out_dir / "markdowns" / "relatorio_acct_prod_team_1.md").exists()
    assert (out_dir / "markdowns" / "relatorio_oportunidades_finops_acct_prod_team_1.md").exists()
    assert (out_dir / "markdowns" / "relatorio_recursos_orfaos_acct_prod_team_1.md").exists()
    assert (out_dir / "markdowns" / "relatorio_arquitetura_aplicacoes_acct_prod_team_1.md").exists()
    assert (out_dir / "docs" / "relatorio_arquitetura_aplicacoes_acct_prod_team_1.docx").exists()

def test_pipeline_e2e_includes_topology(tmp_path: Path):
    csv_file = tmp_path / "resources.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row = "alb-test,arn:aws:elasticloadbalancing:ca-central-1:807445251352:loadbalancer/app/alb-test/1,elasticloadbalancing:loadbalancer,ca-central-1,807445251352,-,AWS::ElasticLoadBalancingV2::LoadBalancer,2026-10-10,elasticloadbalancing,0\n"
    csv_file.write_text(header + row, encoding="utf-8")

    out_dir = tmp_path / "output"
    res = run_pipeline(input_dir=str(tmp_path), output_dir=str(out_dir))
    assert len(res) == 5
    excel_path, md_path, finops_path, orphan_path, topology_path = res

    assert Path(topology_path).exists()
    topo_docx = out_dir / "docs" / Path(topology_path).name.replace(".md", ".docx")
    assert topo_docx.exists()

    import openpyxl
    wb = openpyxl.load_workbook(excel_path)
    assert "Topologia & Arquitetura" in wb.sheetnames

def test_main_cli_with_catalog_flag(tmp_path: Path, monkeypatch):
    csv_file = tmp_path / "resources.csv"
    header = "Identificador,ARN,Tipo de recurso,Região,Conta da AWS,Aplicação,CfnResourceType,LastReportedAt,Serviço,Tags\n"
    row = "alb-vdo,arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/alb-vdo/1,elasticloadbalancing:loadbalancer,us-east-1,123456789012,vdo,AWS::ElasticLoadBalancingV2::LoadBalancer,2026-10-10,elasticloadbalancing,0\n"
    csv_file.write_text(header + row, encoding="utf-8")

    catalog_file = tmp_path / "custom_catalog.json"
    catalog_content = '''{
        "applications": {
            "vdo": {
                "name": "VDO & Promoção Digital",
                "squad": "Squad Pagamentos Custom",
                "owner": "lead@empresa.com",
                "criticality": "Crítica Tier 1",
                "description": "Sistema de pagamentos da loja",
                "match_patterns": ["alb-vdo", "vdo"]
            }
        }
    }'''
    catalog_file.write_text(catalog_content, encoding="utf-8")

    out_dir = tmp_path / "output"
    test_args = [
        "src/main.py",
        "--input-dir", str(tmp_path),
        "--output-dir", str(out_dir),
        "--account", "vdo-account",
        "--catalog", str(catalog_file)
    ]
    monkeypatch.setattr(sys, "argv", test_args)
    main()

    topo_md = out_dir / "markdowns" / "relatorio_arquitetura_aplicacoes_vdo-account.md"
    assert topo_md.exists()
    topo_text = topo_md.read_text(encoding="utf-8")
    assert "Squad Pagamentos Custom" in topo_text
    assert "lead@empresa.com" in topo_text
    assert (out_dir / "docs" / "relatorio_arquitetura_aplicacoes_vdo-account.docx").exists()

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
