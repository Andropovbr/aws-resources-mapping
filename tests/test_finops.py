import pytest
from src.models import ResourceRecord
from src.finops import evaluate_finops_rules

def test_finops_advisory_rules():
    records = [
        ResourceRecord(
            identifier="teste123canais",
            arn="arn:aws:s3:::teste123canais",
            resource_type="s3:bucket",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::S3::Bucket",
            last_reported_at="2026-10-10",
            service="s3",
            tags="0",
            macro_domain="Aplicação"
        ),
        ResourceRecord(
            identifier="app/alb-public/123",
            arn="arn:aws:elasticloadbalancing:ca-central-1:123:loadbalancer/app/alb-public/123",
            resource_type="elasticloadbalancing:loadbalancer",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
            last_reported_at="2026-10-10",
            service="elasticloadbalancing",
            tags="0",
            macro_domain="Aplicação"
        ),
        ResourceRecord(
            identifier="eipalloc-12345",
            arn="arn:aws:ec2:ca-central-1:123:elastic-ip/eipalloc-12345",
            resource_type="ec2:elastic-ip",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::EC2::EIP",
            last_reported_at="2026-10-10",
            service="ec2",
            tags="0",
            macro_domain="Infraestrutura Compartilhada"
        ),
        ResourceRecord(
            identifier="config-rule-abc",
            arn="arn:aws:config:us-east-1:123:config-rule/abc",
            resource_type="config:config-rule",
            region="us-east-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::Config::ConfigRule",
            last_reported_at="2026-10-10",
            service="config",
            tags="0",
            macro_domain="Governança"
        )
    ]
    
    evaluated = evaluate_finops_rules(records)
    
    s3_rec = next(r for r in evaluated if r.identifier == "teste123canais")
    assert s3_rec.finops_suggestion == "Investigar (Possível Teste / Temporário)"
    assert s3_rec.finops_cost_impact == "Médio"
    
    alb_rec = next(r for r in evaluated if "alb-public" in r.identifier)
    assert alb_rec.finops_suggestion == "Investigar (Possível Órfão / Ocioso)"
    assert alb_rec.finops_cost_impact == "Alto"
    
    eip_rec = next(r for r in evaluated if r.identifier == "eipalloc-12345")
    assert eip_rec.finops_suggestion == "Investigar (Possível Órfão / Ocioso)"
    
    gov_rec = next(r for r in evaluated if r.identifier == "config-rule-abc")
    assert gov_rec.finops_suggestion == "Manter (Governança)"
    assert gov_rec.finops_cost_impact == "Baixo/Zero"

def test_finops_additional_rules():
    records = [
        # Snapshots & AMIs
        ResourceRecord(
            identifier="snap-0123456789abcdef0",
            arn="arn:aws:ec2:ca-central-1:123:snapshot/snap-0123456789abcdef0",
            resource_type="ec2:snapshot",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::EC2::Snapshot",
            last_reported_at="2026-10-10",
            service="ec2",
            tags="0",
            macro_domain="Infraestrutura Compartilhada"
        ),
        ResourceRecord(
            identifier="ami-0123456789abcdef0",
            arn="arn:aws:ec2:ca-central-1:123:image/ami-0123456789abcdef0",
            resource_type="ec2:image",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::EC2::Image",
            last_reported_at="2026-10-10",
            service="ec2",
            tags="0",
            macro_domain="Infraestrutura Compartilhada"
        ),
        # MemoryDB / ElastiCache user without cluster
        ResourceRecord(
            identifier="user-default-redis",
            arn="arn:aws:memorydb:ca-central-1:123:user/default-redis",
            resource_type="user",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::MemoryDB::User",
            last_reported_at="2026-10-10",
            service="memorydb",
            tags="0",
            macro_domain="Infraestrutura Compartilhada"
        ),
        # Application operational EC2 (impact Alto)
        ResourceRecord(
            identifier="i-0123456789abcdef0",
            arn="arn:aws:ec2:ca-central-1:123:instance/i-0123456789abcdef0",
            resource_type="ec2:instance",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::EC2::Instance",
            last_reported_at="2026-10-10",
            service="ec2",
            tags="0",
            macro_domain="Aplicação"
        ),
        # Application operational Lambda (impact Médio)
        ResourceRecord(
            identifier="fn-processor",
            arn="arn:aws:lambda:ca-central-1:123:function:fn-processor",
            resource_type="lambda:function",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::Lambda::Function",
            last_reported_at="2026-10-10",
            service="lambda",
            tags="0",
            macro_domain="Aplicação"
        ),
        # Test keyword on non-storage/compute service (impact Baixo/Zero)
        ResourceRecord(
            identifier="sample-log-group",
            arn="arn:aws:logs:ca-central-1:123:log-group:/sample-log-group",
            resource_type="logs:log-group",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::Logs::LogGroup",
            last_reported_at="2026-10-10",
            service="logs",
            tags="0",
            macro_domain="Infraestrutura Compartilhada"
        )
    ]

    evaluated = evaluate_finops_rules(records)

    snap_rec = next(r for r in evaluated if r.identifier == "snap-0123456789abcdef0")
    assert snap_rec.finops_suggestion == "Investigar (Possível Órfão / Ocioso)"
    assert snap_rec.finops_cost_impact == "Médio"

    ami_rec = next(r for r in evaluated if r.identifier == "ami-0123456789abcdef0")
    assert ami_rec.finops_suggestion == "Investigar (Possível Órfão / Ocioso)"
    assert ami_rec.finops_cost_impact == "Médio"

    mem_user = next(r for r in evaluated if r.identifier == "user-default-redis")
    assert mem_user.finops_suggestion == "Investigar (Possível Órfão / Ocioso)"
    assert mem_user.finops_cost_impact == "Baixo/Zero"

    ec2_app = next(r for r in evaluated if r.identifier == "i-0123456789abcdef0")
    assert ec2_app.finops_suggestion == "Manter (Em Operação)"
    assert ec2_app.finops_cost_impact == "Alto"

    lambda_app = next(r for r in evaluated if r.identifier == "fn-processor")
    assert lambda_app.finops_suggestion == "Manter (Em Operação)"
    assert lambda_app.finops_cost_impact == "Médio"

    sample_log = next(r for r in evaluated if r.identifier == "sample-log-group")
    assert sample_log.finops_suggestion == "Investigar (Possível Teste / Temporário)"
    assert sample_log.finops_cost_impact == "Baixo/Zero"

def test_finops_empty_list():
    assert evaluate_finops_rules([]) == []
