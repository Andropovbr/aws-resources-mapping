import pytest
from pathlib import Path
import openpyxl
from src.models import InventoryReportData, ApplicationCluster, ResourceRecord
from src.exporters.excel import generate_excel_workbook

def test_excel_workbook_generation(tmp_path: Path):
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
        finops_suggestion="Investigar (Possível Órfão / Ocioso)",
        finops_cost_impact="Alto",
        finops_rationale="Validar RDS"
    )
    data = InventoryReportData(
        account_id="123",
        total_resources=1,
        unique_arns=1,
        regions={"ca-central-1": 1},
        services={"rds": 1},
        macro_domains={"Aplicação": 1},
        finops_summary={"Investigar (Possível Órfão / Ocioso)": 1},
        clusters=[],
        all_resources=[rec]
    )
    
    out_file = tmp_path / "inventario.xlsx"
    generate_excel_workbook(data, str(out_file))
    
    assert out_file.exists()
    wb = openpyxl.load_workbook(out_file)
    expected_sheets = [
        "Resumo Executivo",
        "FinOps & Ações do Time",
        "Aplicações & Compute",
        "Bancos & Armazenamento",
        "Governança & Segurança",
        "Inventário Geral"
    ]
    for s in expected_sheets:
        assert s in wb.sheetnames


def test_excel_sheet_contents_and_filtering(tmp_path: Path):
    r1 = ResourceRecord(
        identifier="app-ec2-1",
        arn="arn:aws:ec2:us-east-1:123:instance/i-1",
        resource_type="ec2:instance",
        region="us-east-1",
        aws_account="123",
        application_raw="-",
        cfn_resource_type="AWS::EC2::Instance",
        last_reported_at="2026-10-10",
        service="ec2",
        tags="env=prod",
        source_files=["ec2.csv"],
        macro_domain="Aplicação",
        inferred_app="Portal",
        finops_suggestion="Investigar (Instância Ociosa)",
        finops_cost_impact="Médio",
        finops_rationale="CPU baixa"
    )
    r2 = ResourceRecord(
        identifier="prod-db",
        arn="arn:aws:rds:us-east-1:123:db:prod-db",
        resource_type="rds:db",
        region="us-east-1",
        aws_account="123",
        application_raw="-",
        cfn_resource_type="AWS::RDS::DBInstance",
        last_reported_at="2026-10-10",
        service="rds",
        tags="env=prod",
        source_files=["rds.csv"],
        macro_domain="Dados",
        inferred_app="Database Cluster",
        finops_suggestion="Manter / Produção Ativa",
        finops_cost_impact="Alto",
        finops_rationale="Banco principal"
    )
    r3 = ResourceRecord(
        identifier="cw-alarm-1",
        arn="arn:aws:cloudwatch:us-east-1:123:alarm:cw-alarm-1",
        resource_type="cloudwatch:alarm",
        region="us-east-1",
        aws_account="123",
        application_raw="-",
        cfn_resource_type="AWS::CloudWatch::Alarm",
        last_reported_at="2026-10-10",
        service="cloudwatch",
        tags="",
        source_files=["cloudwatch.csv"],
        macro_domain="Governança",
        inferred_app="Infraestrutura Compartilhada",
        finops_suggestion="Avaliar Otimização",
        finops_cost_impact="Baixo/Zero",
        finops_rationale="Alarme CloudWatch"
    )

    data = InventoryReportData(
        account_id="123",
        total_resources=3,
        unique_arns=3,
        regions={"us-east-1": 3},
        services={"ec2": 1, "rds": 1, "cloudwatch": 1},
        macro_domains={"Aplicação": 1, "Dados": 1, "Governança": 1},
        finops_summary={
            "Investigar (Instância Ociosa)": 1,
            "Manter / Produção Ativa": 1,
            "Avaliar Otimização": 1
        },
        clusters=[],
        all_resources=[r1, r2, r3]
    )

    out_file = tmp_path / "nested" / "relatorio.xlsx"
    generate_excel_workbook(data, str(out_file))

    assert out_file.exists()
    wb = openpyxl.load_workbook(out_file)

    # 1. Resumo Executivo
    ws_resumo = wb["Resumo Executivo"]
    assert "Conta 123" in str(ws_resumo.cell(row=1, column=1).value)
    assert ws_resumo.cell(row=3, column=1).value == "Métrica"
    assert ws_resumo.cell(row=3, column=2).value == "Valor"
    assert ws_resumo.cell(row=4, column=1).value == "Total de Recursos Canônicos"
    assert ws_resumo.cell(row=4, column=2).value == 3

    # 2. FinOps & Ações do Time (only r1 has 'Investigar')
    ws_finops = wb["FinOps & Ações do Time"]
    finops_rows = list(ws_finops.iter_rows(values_only=True))
    assert finops_rows[0][0] == "Identificador"
    assert finops_rows[0][7] == "Decisão do Time (Manter/Deletar/Em Análise)"
    assert finops_rows[0][8] == "Responsável"
    assert finops_rows[0][9] == "Observações do Time"
    assert len(finops_rows) == 2  # 1 header + 1 record (r1)
    assert finops_rows[1][0] == "app-ec2-1"
    assert finops_rows[1][7] in (None, "")
    assert finops_rows[1][8] in (None, "")
    assert finops_rows[1][9] in (None, "")

    # 3. Aplicações & Compute (r1 has macro_domain="Aplicação" and service="ec2")
    ws_app = wb["Aplicações & Compute"]
    app_rows = list(ws_app.iter_rows(values_only=True))
    assert len(app_rows) == 2  # header + r1
    assert app_rows[1][0] == "app-ec2-1"

    # 4. Bancos & Armazenamento (r2 has service="rds")
    ws_storage = wb["Bancos & Armazenamento"]
    storage_rows = list(ws_storage.iter_rows(values_only=True))
    assert len(storage_rows) == 2  # header + r2
    assert storage_rows[1][0] == "prod-db"

    # 5. Governança & Segurança (r3 has macro_domain="Governança")
    ws_gov = wb["Governança & Segurança"]
    gov_rows = list(ws_gov.iter_rows(values_only=True))
    assert len(gov_rows) == 2  # header + r3
    assert gov_rows[1][0] == "cw-alarm-1"

    # 6. Inventário Geral (all 3 records)
    ws_geral = wb["Inventário Geral"]
    geral_rows = list(ws_geral.iter_rows(values_only=True))
    assert len(geral_rows) == 4  # header + 3 records


def test_excel_workbook_empty_data(tmp_path: Path):
    data = InventoryReportData(
        account_id="empty-acc",
        total_resources=0,
        unique_arns=0,
        regions={},
        services={},
        macro_domains={},
        finops_summary={},
        clusters=[],
        all_resources=[]
    )
    out_file = tmp_path / "empty.xlsx"
    generate_excel_workbook(data, str(out_file))
    assert out_file.exists()
    wb = openpyxl.load_workbook(out_file)
    assert "Resumo Executivo" in wb.sheetnames
    assert "Inventário Geral" in wb.sheetnames

