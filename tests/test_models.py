import pytest
from src.models import (
    ResourceRecord,
    ApplicationCluster,
    InventoryReportData,
    PlaybookGuide,
    FinOpsOpportunity,
    FinOpsAnalysisResult,
)

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
    assert record.resource_name == "-"
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

def test_finops_opportunity_models():
    guide = PlaybookGuide(
        playbook_id="pb-ec2-rightsizing",
        title="Playbook 1: EC2 Right-sizing",
        target_metric="CPUUtilization < 10%",
        target_resources=["i-090d9b01ccf2af5ae"],
        console_path="CloudWatch > Metrics > EC2",
        aws_cli_command="aws cloudwatch get-metric-statistics ...",
        decision_criteria="Se CPU < 10%, reduzir instância",
        recommended_action="Fazer downgrade de t3.large para t3.small"
    )
    assert guide.playbook_id == "pb-ec2-rightsizing"
    assert len(guide.target_resources) == 1

    opp = FinOpsOpportunity(
        pillar="Superdimensionamento",
        title="Desproporção de ALBs vs Instâncias EC2",
        description="9 ALBs para 2 instâncias EC2 mapeadas",
        evidence_status="[AÇÃO IMEDIATA]",
        effort_level="Baixo (Quick Win)",
        impact_level="Alto",
        estimated_monthly_savings_usd=157.5,
        affected_resources_count=9,
        resource_identifiers=["app/Docker-dev/6de4d3f3d608fb4c"],
        playbook_id=None
    )
    assert opp.pillar == "Superdimensionamento"
    assert opp.estimated_monthly_savings_usd == 157.5

    result = FinOpsAnalysisResult(
        account_id="multicanais-dev",
        total_opportunities=1,
        immediate_actions_count=1,
        needs_analysis_count=0,
        total_estimated_monthly_savings_usd=157.5,
        pillar_consumption_opportunities=[],
        pillar_rightsizing_opportunities=[opp],
        pillar_cost_reduction_opportunities=[],
        playbooks=[guide]
    )
    assert result.total_opportunities == 1
    assert len(result.playbooks) == 1

