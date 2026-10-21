import pytest
from pathlib import Path
from src.models import InventoryReportData, ApplicationCluster, ResourceRecord
from src.exporters.markdown import generate_markdown_report

def test_markdown_report_generation(tmp_path: Path):
    rec = ResourceRecord(
        identifier="canaisdb-02",
        arn="arn:aws:rds:ca-central-1:123:db:canaisdb-02",
        resource_type="rds:db",
        region="ca-central-1",
        aws_account="123",
        application_raw="-",
        cfn_resource_type="AWS::RDS::DBInstance",
        last_reported_at="2026-10-10",
        service="rds",
        tags="0",
        macro_domain="Aplicação",
        inferred_app="Canais Digitais",
        finops_suggestion="Manter (Em Operação)",
        finops_cost_impact="Alto",
        finops_rationale="Banco RDS ativo"
    )
    cluster = ApplicationCluster(
        name="Canais Digitais",
        slug="canais-dig",
        resources=[rec],
        compute_instances=["i-0123456789abcdef0"],
        load_balancers=["app/alb-canais-dig-1"],
        target_groups=["tg-canais-dig-1"],
        databases=["canaisdb-02"],
        secrets=["canais-db-01"],
        storage_buckets=["logs-canaisdig"]
    )
    data = InventoryReportData(
        account_id="123",
        total_resources=1,
        unique_arns=1,
        regions={"ca-central-1": 1},
        services={"rds": 1},
        macro_domains={"Aplicação": 1},
        finops_summary={"Manter (Em Operação)": 1},
        clusters=[cluster],
        all_resources=[rec]
    )
    
    out_file = tmp_path / "relatorio.md"
    content = generate_markdown_report(data, str(out_file))
    
    assert out_file.exists()
    assert "# Relatório Executivo de Inventário AWS e FinOps" in content
    assert "Canais Digitais" in content
    assert "canaisdb-02" in content
    assert "ca-central-1" in content
    assert "i-0123456789abcdef0" in content
    assert "app/alb-canais-dig-1" in content
    assert "tg-canais-dig-1" in content
    assert "canais-db-01" in content
    assert "logs-canaisdig" in content
    assert "Nenhum recurso de alto ou médio impacto necessitando de investigação imediata." in content

def test_markdown_report_investigate_items_truncation(tmp_path: Path):
    items = []
    for i in range(25):
        items.append(
            ResourceRecord(
                identifier=f"res-{i:02d}",
                arn=f"arn:aws:service:us-east-1:123:res-{i:02d}",
                resource_type="type",
                region="us-east-1",
                aws_account="123",
                application_raw="-",
                cfn_resource_type="AWS::Type",
                last_reported_at="2026-10-10",
                service="svc",
                tags="0",
                macro_domain="Aplicação",
                inferred_app="App",
                finops_suggestion="Investigar Ociosidade",
                finops_cost_impact="Alto" if i % 2 == 0 else "Médio",
                finops_rationale=f"Possível ociosidade recurso {i}"
            )
        )
    data = InventoryReportData(
        account_id="123",
        total_resources=25,
        unique_arns=25,
        regions={"us-east-1": 25},
        services={"svc": 25},
        macro_domains={"Aplicação": 25},
        finops_summary={"Investigar Ociosidade": 25},
        clusters=[],
        all_resources=items
    )

    out_file = tmp_path / "relatorio_investigate.md"
    content = generate_markdown_report(data, str(out_file))

    assert out_file.exists()
    assert "| Recurso | Tipo / Serviço | Região | Impacto | Justificativa |" in content
    assert "res-00" in content
    assert "res-19" in content
    assert "*(Mostrando 20 de 25 itens de atenção; veja lista completa na planilha Excel)*" in content
