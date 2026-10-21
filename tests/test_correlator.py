import pytest
from src.models import ResourceRecord
from src.correlator import correlate_and_classify_resources, generate_slug

def test_governance_classification():
    records = [
        ResourceRecord(
            identifier="StackSet-AWSControlTowerBP-BASELINE-CLOUDWATCH",
            arn="arn:aws:cloudformation:ca-central-1:123:stack/StackSet-AWSControlTowerBP",
            resource_type="cloudformation:stack",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::CloudFormation::Stack",
            last_reported_at="2026-10-10",
            service="cloudformation",
            tags="0"
        ),
        ResourceRecord(
            identifier="aws-service-rule/fms.amazonaws.com/config-rule-ccwwdc",
            arn="arn:aws:config:us-east-1:123:config-rule/aws-service-rule/fms",
            resource_type="config:config-rule",
            region="us-east-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::Config::ConfigRule",
            last_reported_at="2026-10-10",
            service="config",
            tags="0"
        ),
        ResourceRecord(
            identifier="StackSet-PrismaCloud-Compute-Role",
            arn="arn:aws:iam::123:role/StackSet-PrismaCloud-Compute-Role",
            resource_type="iam:role",
            region="global",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::IAM::Role",
            last_reported_at="2026-10-10",
            service="iam",
            tags="0"
        ),
        ResourceRecord(
            identifier="/CrowdStrike/CSPM/SensorManagement/FalconAPICredentials-HoHthC",
            arn="arn:aws:secretsmanager:us-east-1:123:secret:/CrowdStrike/FalconAPICredentials",
            resource_type="secretsmanager:secret",
            region="us-east-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::SecretsManager::Secret",
            last_reported_at="2026-10-10",
            service="secretsmanager",
            tags="0"
        ),
        ResourceRecord(
            identifier="StackSet-VisionOne-TrendMicro",
            arn="arn:aws:cloudformation:us-east-1:123:stack/StackSet-VisionOne",
            resource_type="cloudformation:stack",
            region="us-east-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::CloudFormation::Stack",
            last_reported_at="2026-10-10",
            service="cloudformation",
            tags="0"
        ),
        ResourceRecord(
            identifier="aws-quicksetup-patchmanager-association",
            arn="arn:aws:ssm:us-east-1:123:association/aws-quicksetup-123",
            resource_type="ssm:association",
            region="us-east-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::SSM::Association",
            last_reported_at="2026-10-10",
            service="ssm",
            tags="0"
        )
    ]
    classified, clusters = correlate_and_classify_resources(records)
    assert all(r.macro_domain == "Governança" for r in classified)
    assert all(r.inferred_app == "Governança & Segurança" for r in classified)
    assert len(clusters) == 0

def test_application_clustering_and_topology():
    records = [
        ResourceRecord(
            identifier="app/alb-blog-wordpress/71ffc2bd913c4691",
            arn="arn:aws:elasticloadbalancing:ca-central-1:123:loadbalancer/app/alb-blog-wordpress/71ffc2bd913c4691",
            resource_type="elasticloadbalancing:loadbalancer",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
            last_reported_at="2026-10-10",
            service="elasticloadbalancing",
            tags="0"
        ),
        ResourceRecord(
            identifier="blog-wordpress/8c0f1e8481be211d",
            arn="arn:aws:elasticloadbalancing:ca-central-1:123:targetgroup/blog-wordpress/8c0f1e8481be211d",
            resource_type="elasticloadbalancing:targetgroup",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::ElasticLoadBalancingV2::TargetGroup",
            last_reported_at="2026-10-10",
            service="elasticloadbalancing",
            tags="0"
        ),
        ResourceRecord(
            identifier="canaisdb-02",
            arn="arn:aws:rds:ca-central-1:123:db:canaisdb-02",
            resource_type="rds:db",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::RDS::DBInstance",
            last_reported_at="2026-10-10",
            service="rds",
            tags="0"
        ),
        ResourceRecord(
            identifier="i-0abcd1234efgh5678",
            arn="arn:aws:ec2:ca-central-1:123:instance/i-0abcd1234efgh5678",
            resource_type="ec2:instance",
            region="ca-central-1",
            aws_account="123",
            application_raw="multicanais-prod",
            cfn_resource_type="AWS::EC2::Instance",
            last_reported_at="2026-10-10",
            service="ec2",
            tags="1"
        ),
        ResourceRecord(
            identifier="secret-canais-prod",
            arn="arn:aws:secretsmanager:ca-central-1:123:secret:secret-canais-prod-1234",
            resource_type="secretsmanager:secret",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::SecretsManager::Secret",
            last_reported_at="2026-10-10",
            service="secretsmanager",
            tags="0"
        ),
        ResourceRecord(
            identifier="multicanais-assets",
            arn="arn:aws:s3:::multicanais-assets",
            resource_type="s3:bucket",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::S3::Bucket",
            last_reported_at="2026-10-10",
            service="s3",
            tags="0"
        )
    ]
    classified, clusters = correlate_and_classify_resources(records)
    wp_rec = next(r for r in classified if "wordpress" in r.identifier.lower())
    assert wp_rec.inferred_app == "WordPress / Blog"
    assert wp_rec.macro_domain == "Aplicação"
    
    canais_rec = next(r for r in classified if "canaisdb" in r.identifier.lower())
    assert canais_rec.inferred_app == "Canais Digitais"
    
    cluster_names = [c.name for c in clusters]
    assert "WordPress / Blog" in cluster_names
    assert "Canais Digitais" in cluster_names

    wp_cluster = next(c for c in clusters if c.name == "WordPress / Blog")
    assert "app/alb-blog-wordpress/71ffc2bd913c4691" in wp_cluster.load_balancers
    assert "blog-wordpress/8c0f1e8481be211d" in wp_cluster.target_groups

    canais_cluster = next(c for c in clusters if c.name == "Canais Digitais")
    assert "canaisdb-02" in canais_cluster.databases
    assert "i-0abcd1234efgh5678" in canais_cluster.compute_instances
    assert "secret-canais-prod" in canais_cluster.secrets
    assert "multicanais-assets" in canais_cluster.storage_buckets

def test_other_application_clusters():
    records = [
        ResourceRecord(
            identifier="docker-dev-app",
            arn="arn:aws:elasticloadbalancing:ca-central-1:123:loadbalancer/app/docker-dev-app/123",
            resource_type="elasticloadbalancing:loadbalancer",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
            last_reported_at="2026-10-10",
            service="elasticloadbalancing",
            tags="0"
        ),
        ResourceRecord(
            identifier="alb-vdo-promo",
            arn="arn:aws:elasticloadbalancing:ca-central-1:123:loadbalancer/app/alb-vdo-promo/123",
            resource_type="elasticloadbalancing:loadbalancer",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
            last_reported_at="2026-10-10",
            service="elasticloadbalancing",
            tags="0"
        ),
        ResourceRecord(
            identifier="elasticbeanstalk-ca-central-1-123",
            arn="arn:aws:s3:::elasticbeanstalk-ca-central-1-123",
            resource_type="s3:bucket",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::S3::Bucket",
            last_reported_at="2026-10-10",
            service="s3",
            tags="0"
        )
    ]
    classified, clusters = correlate_and_classify_resources(records)
    cluster_names = {c.name for c in clusters}
    assert "Docker-dev" in cluster_names
    assert "VDO & Promoção Digital" in cluster_names
    assert "Elastic Beanstalk / Legado" in cluster_names

    eb_cluster = next(c for c in clusters if c.name == "Elastic Beanstalk / Legado")
    assert "elasticbeanstalk-ca-central-1-123" in eb_cluster.storage_buckets
    assert eb_cluster.slug == "elastic-beanstalk-legado"

def test_shared_infrastructure_fallback():
    records = [
        ResourceRecord(
            identifier="vpc-0123456789abcdef0",
            arn="arn:aws:ec2:ca-central-1:123:vpc/vpc-0123456789abcdef0",
            resource_type="ec2:vpc",
            region="ca-central-1",
            aws_account="123",
            application_raw="-",
            cfn_resource_type="AWS::EC2::VPC",
            last_reported_at="2026-10-10",
            service="ec2",
            tags="0"
        )
    ]
    classified, clusters = correlate_and_classify_resources(records)
    assert len(classified) == 1
    assert classified[0].macro_domain == "Infraestrutura Compartilhada"
    assert classified[0].inferred_app == "Infraestrutura Compartilhada"
    assert len(clusters) == 0

def test_empty_resources():
    classified, clusters = correlate_and_classify_resources([])
    assert classified == []
    assert clusters == []

def test_compute_instances_ec2_only():
    records = [
        ResourceRecord(
            identifier="connect-instance-123",
            arn="arn:aws:connect:ca-central-1:123:instance/connect-instance-123",
            resource_type="connect:instance",
            region="ca-central-1",
            aws_account="123",
            application_raw="canais-dig",
            cfn_resource_type="AWS::Connect::Instance",
            last_reported_at="2026-10-10",
            service="connect",
            tags="0"
        ),
        ResourceRecord(
            identifier="i-valid-ec2-001",
            arn="arn:aws:ec2:ca-central-1:123:instance/i-valid-ec2-001",
            resource_type="ec2:instance",
            region="ca-central-1",
            aws_account="123",
            application_raw="canais-dig",
            cfn_resource_type="AWS::EC2::Instance",
            last_reported_at="2026-10-10",
            service="ec2",
            tags="0"
        )
    ]
    classified, clusters = correlate_and_classify_resources(records)
    canais_cl = next(c for c in clusters if c.name == "Canais Digitais")
    assert "i-valid-ec2-001" in canais_cl.compute_instances
    assert "connect-instance-123" not in canais_cl.compute_instances

def test_slug_generation_cleaning():
    assert generate_slug("VDO & Promoção Digital") == "vdo-promocao-digital"
    assert generate_slug("Elastic Beanstalk / Legado") == "elastic-beanstalk-legado"
    assert generate_slug("WordPress / Blog") == "wordpress-blog"
    assert generate_slug("App: Special @#$ Name!!") == "app-special-name"
