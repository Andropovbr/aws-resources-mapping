import pytest
from src.models import ResourceRecord, InventoryReportData, ApplicationCluster
from src.finops_analyzer import analyze_finops_opportunities

def create_sample_report_data(alb_count=9, ec2_count=2, rds_count=2, regions=None):
    if regions is None:
        regions = {"ca-central-1": 10, "sa-east-1": 10, "us-west-2": 2, "ap-northeast-2": 1}
    
    resources = []
    # ALBs
    for i in range(alb_count):
        resources.append(ResourceRecord(
            identifier=f"app/alb-{i}/abc{i}",
            arn=f"arn:aws:elasticloadbalancing:ca-central-1:807445251352:loadbalancer/app/alb-{i}/abc{i}",
            resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
            region="ca-central-1",
            aws_account="807445251352",
            application_raw="-",
            cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
            last_reported_at="2026-10-10",
            service="elasticloadbalancing",
            tags="0",
            macro_domain="Aplicação"
        ))
    # EC2
    for i in range(ec2_count):
        resources.append(ResourceRecord(
            identifier=f"i-00000000{i}",
            arn=f"arn:aws:ec2:ca-central-1:807445251352:instance/i-00000000{i}",
            resource_type="ec2:instance",
            region="ca-central-1",
            aws_account="807445251352",
            application_raw="-",
            cfn_resource_type="AWS::EC2::Instance",
            last_reported_at="2026-10-10",
            service="ec2",
            tags="0",
            macro_domain="Aplicação"
        ))
    # RDS
    for i in range(rds_count):
        resources.append(ResourceRecord(
            identifier=f"canaisdb-0{i}",
            arn=f"arn:aws:rds:ca-central-1:807445251352:db:canaisdb-0{i}",
            resource_type="AWS::RDS::DBInstance",
            region="ca-central-1",
            aws_account="807445251352",
            application_raw="-",
            cfn_resource_type="AWS::RDS::DBInstance",
            last_reported_at="2026-10-10",
            service="rds",
            tags="0",
            macro_domain="Aplicação"
        ))
    # Test Snapshot
    resources.append(ResourceRecord(
        identifier="snapshot-copy-test",
        arn="arn:aws:rds:sa-east-1:807445251352:snapshot:snapshot-copy-test",
        resource_type="AWS::RDS::DBSnapshot",
        region="sa-east-1",
        aws_account="807445251352",
        application_raw="-",
        cfn_resource_type="AWS::RDS::DBSnapshot",
        last_reported_at="2026-10-10",
        service="rds",
        tags="0",
        macro_domain="Infraestrutura Compartilhada"
    ))
    # Unassociated EIP
    resources.append(ResourceRecord(
        identifier="eipalloc-123456",
        arn="arn:aws:ec2:ca-central-1:807445251352:elastic-ip/eipalloc-123456",
        resource_type="AWS::EC2::EIP",
        region="ca-central-1",
        aws_account="807445251352",
        application_raw="-",
        cfn_resource_type="AWS::EC2::EIP",
        last_reported_at="2026-10-10",
        service="ec2",
        tags="0",
        macro_domain="Infraestrutura Compartilhada"
    ))

    return InventoryReportData(
        account_id="multicanais-dev",
        total_resources=len(resources),
        unique_arns=len(resources),
        regions=regions,
        services={"elasticloadbalancing": alb_count, "ec2": ec2_count + 1, "rds": rds_count + 1},
        macro_domains={"Aplicação": alb_count + ec2_count + rds_count, "Infraestrutura Compartilhada": 2},
        finops_summary={"Manter (Em Operação)": 10, "Investigar (Possível Órfão / Ocioso)": 2},
        clusters=[],
        all_resources=resources
    )

def test_analyze_finops_opportunities_disproportion_and_playbooks():
    report_data = create_sample_report_data(alb_count=9, ec2_count=2)
    analysis = analyze_finops_opportunities(report_data)

    assert analysis.account_id == "multicanais-dev"
    assert analysis.total_opportunities >= 3
    assert analysis.immediate_actions_count >= 1
    assert analysis.needs_analysis_count >= 1
    assert analysis.total_estimated_monthly_savings_usd > 100.0

    # Verificar oportunidade de desproporção de ALBs
    alb_opp = next((o for o in analysis.pillar_rightsizing_opportunities if "ALB" in o.title), None)
    assert alb_opp is not None
    assert alb_opp.evidence_status == "[AÇÃO IMEDIATA]"
    assert alb_opp.affected_resources_count == 9

    # Verificar que playbooks foram montados
    assert len(analysis.playbooks) >= 3
    ec2_pb = next((p for p in analysis.playbooks if "EC2" in p.title), None)
    assert ec2_pb is not None
    assert "i-000000000" in ec2_pb.target_resources
    assert "aws compute-optimizer get-ec2-instance-recommendations" in ec2_pb.aws_cli_command

def test_analyze_finops_opportunities_zero_division_guard():
    # Garantir que 0 instâncias EC2 não gere ZeroDivisionError
    report_data = create_sample_report_data(alb_count=3, ec2_count=0)
    analysis = analyze_finops_opportunities(report_data)
    assert analysis is not None
    alb_opp = next((o for o in analysis.pillar_rightsizing_opportunities if "ALB" in o.title), None)
    assert alb_opp is not None

def test_analyze_finops_opportunities_real_rds_and_false_positive_filters():
    resources = [
        ResourceRecord(
            identifier="canaisdb-02",
            arn="arn:aws:rds:ca-central-1:807445251352:db:canaisdb-02",
            resource_type="rds:db",
            region="ca-central-1",
            aws_account="807445251352",
            application_raw="-",
            cfn_resource_type="AWS::RDS::DBInstance",
            last_reported_at="2026-10-10",
            service="rds",
            tags="0",
            macro_domain="Aplicação"
        ),
        ResourceRecord(
            identifier="Inventario-AWS:$LATEST",
            arn="arn:aws:lambda:ca-central-1:807445251352:function:Inventario-AWS:$LATEST",
            resource_type="lambda:function",
            region="ca-central-1",
            aws_account="807445251352",
            application_raw="-",
            cfn_resource_type="AWS::Lambda::Function",
            last_reported_at="2026-10-10",
            service="lambda",
            tags="0",
            macro_domain="Aplicação"
        ),
        ResourceRecord(
            identifier="cf-templates-1n04cz2bei4gp-us-east-1",
            arn="arn:aws:s3:::cf-templates-1n04cz2bei4gp-us-east-1",
            resource_type="s3:bucket",
            region="us-east-1",
            aws_account="807445251352",
            application_raw="-",
            cfn_resource_type="AWS::S3::Bucket",
            last_reported_at="2026-10-10",
            service="s3",
            tags="0",
            macro_domain="Infraestrutura Compartilhada"
        ),
        ResourceRecord(
            identifier="snapshot-copy-test",
            arn="arn:aws:rds:sa-east-1:807445251352:snapshot:snapshot-copy-test",
            resource_type="AWS::RDS::DBSnapshot",
            region="sa-east-1",
            aws_account="807445251352",
            application_raw="-",
            cfn_resource_type="AWS::RDS::DBSnapshot",
            last_reported_at="2026-10-10",
            service="rds",
            tags="0",
            macro_domain="Infraestrutura Compartilhada"
        )
    ]
    report_data = InventoryReportData(
        account_id="807445251352",
        total_resources=len(resources),
        unique_arns=len(resources),
        regions={"ca-central-1": 2, "us-east-1": 1, "sa-east-1": 1},
        services={"rds": 2, "lambda": 1, "s3": 1},
        macro_domains={"Aplicação": 2, "Infraestrutura Compartilhada": 2},
        finops_summary={},
        clusters=[],
        all_resources=resources
    )

    analysis = analyze_finops_opportunities(report_data)

    # 1. RDS deve ser detectado e colocado no playbook de dev scheduling
    dev_sched_pb = next((p for p in analysis.playbooks if p.playbook_id == "pb-dev-scheduling"), None)
    assert dev_sched_pb is not None
    assert "canaisdb-02" in dev_sched_pb.target_resources

    # 2. $LATEST e cf-templates NÃO devem ser marcados como teste
    test_opp = next((o for o in analysis.pillar_cost_reduction_opportunities if "Teste" in o.title), None)
    assert test_opp is not None
    assert "snapshot-copy-test" in test_opp.resource_identifiers
    assert "Inventario-AWS:$LATEST" not in test_opp.resource_identifiers
    assert "cf-templates-1n04cz2bei4gp-us-east-1" not in test_opp.resource_identifiers

