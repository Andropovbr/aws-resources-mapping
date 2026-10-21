import pytest
from src.models import ResourceRecord, ApplicationCluster, InventoryReportData

def test_resource_record_defaults():
    record = ResourceRecord(
        identifier="i-123456",
        arn="arn:aws:ec2:ca-central-1:123456789012:instance/i-123456",
        resource_type="ec2:instance",
        region="ca-central-1",
        aws_account="123456789012",
        application_raw="-",
        cfn_resource_type="AWS::EC2::Instance",
        last_reported_at="2026-10-21 10:00:00",
        service="ec2",
        tags="0",
        source_files=["ec2.csv"]
    )
    assert record.identifier == "i-123456"
    assert record.macro_domain == "A Classificar"
    assert record.inferred_app == "Não Identificado"
    assert record.finops_suggestion == "Avaliar"
    assert record.finops_cost_impact == "Baixo/Zero"
    assert record.finops_rationale == ""
    assert record.source_files == ["ec2.csv"]

def test_application_cluster_initialization():
    cluster = ApplicationCluster(
        name="Canais Digitais",
        slug="canais-dig",
        resources=[],
        compute_instances=["i-123"],
        load_balancers=["app/alb-1"],
        target_groups=["tg-1"],
        databases=["canaisdb-02"],
        secrets=["canais-db-01"],
        storage_buckets=["logs-canaisdig"]
    )
    assert cluster.name == "Canais Digitais"
    assert len(cluster.compute_instances) == 1
    assert cluster.databases == ["canaisdb-02"]

def test_inventory_report_data_initialization():
    report = InventoryReportData(
        account_id="123456789012",
        total_resources=1,
        unique_arns=1,
        regions={"ca-central-1": 1},
        services={"ec2": 1},
        macro_domains={"A Classificar": 1},
        finops_summary={"Avaliar": 1},
        clusters=[],
        all_resources=[]
    )
    assert report.account_id == "123456789012"
    assert report.total_resources == 1
    assert report.regions == {"ca-central-1": 1}
