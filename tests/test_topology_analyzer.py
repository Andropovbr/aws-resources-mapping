import pytest
from src.models import (
    ResourceRecord,
    TopologyComponent,
    InventoryReportData,
    ApplicationCluster
)
from src.topology_analyzer import (
    load_application_catalog,
    classify_layer,
    resolve_ownership,
    infer_connections,
    analyze_application_topology
)

def test_classify_layer():
    # Endpoints
    r1 = ResourceRecord(
        identifier="my-alb", arn="arn:aws:elasticloadbalancing:us-east-1:123:loadbalancer/app/my-alb",
        resource_type="elasticloadbalancing:loadbalancer", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer",
        last_reported_at="", service="elasticloadbalancing", tags=""
    )
    assert classify_layer(r1) == "Ingresso & Endpoints"

    # Compute
    r2 = ResourceRecord(
        identifier="my-func", arn="arn:aws:lambda:us-east-1:123:function:my-func",
        resource_type="lambda:function", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="AWS::Lambda::Function",
        last_reported_at="", service="lambda", tags=""
    )
    assert classify_layer(r2) == "Computação & Lógica"

    # Messaging
    r3 = ResourceRecord(
        identifier="my-queue", arn="arn:aws:sqs:us-east-1:123:my-queue",
        resource_type="sqs:queue", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="AWS::SQS::Queue",
        last_reported_at="", service="sqs", tags=""
    )
    assert classify_layer(r3) == "Mensageria & Filas"

    # Database
    r4 = ResourceRecord(
        identifier="my-db", arn="arn:aws:rds:us-east-1:123:db:my-db",
        resource_type="rds:db", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="AWS::RDS::DBInstance",
        last_reported_at="", service="rds", tags=""
    )
    assert classify_layer(r4) == "Banco de Dados & Cache"

    # Storage
    r5 = ResourceRecord(
        identifier="my-bucket", arn="arn:aws:s3:::my-bucket",
        resource_type="s3:bucket", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="AWS::S3::Bucket",
        last_reported_at="", service="s3", tags=""
    )
    assert classify_layer(r5) == "Armazenamento & Apoio"

    # Storage - EBS Volume (service=ec2)
    r6 = ResourceRecord(
        identifier="vol-0123456789abcdef0", arn="arn:aws:ec2:us-east-1:123:volume/vol-0123456789abcdef0",
        resource_type="ec2:volume", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="AWS::EC2::Volume",
        last_reported_at="", service="ec2", tags=""
    )
    assert classify_layer(r6) == "Armazenamento & Apoio"

def test_resolve_ownership():
    catalog = {
        "vdo-promocao": {
            "name": "VDO & Promoção Digital",
            "squad": "Squad Marketing & Promoções",
            "owner": "techlead-vdo@empresa.com",
            "criticality": "Alta",
            "match_patterns": ["vdo", "promo-digital"]
        }
    }

    # Match via catálogo
    r1 = ResourceRecord(
        identifier="alb-vdo-main", arn="arn:aws:alb:123:alb-vdo-main",
        resource_type="alb", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="", last_reported_at="",
        service="elasticloadbalancing", tags=""
    )
    squad, owner, crit = resolve_ownership(r1, catalog, inferred_app="VDO & Promoção Digital")
    assert squad == "Squad Marketing & Promoções"
    assert owner == "techlead-vdo@empresa.com"
    assert crit == "Alta"

    # Fallback governança
    r_gov = ResourceRecord(
        identifier="config-rule-1", arn="arn:aws:config:123:config-rule-1",
        resource_type="config", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="", last_reported_at="",
        service="config", tags="", macro_domain="Governança"
    )
    squad_gov, _, _ = resolve_ownership(r_gov, catalog, inferred_app="Governança & Segurança")
    assert squad_gov == "Squad Segurança & Governança"

    # Fallback infraestrutura compartilhada
    r_infra = ResourceRecord(
        identifier="shared-vpc", arn="arn:aws:ec2:123:vpc/vpc-123",
        resource_type="ec2:vpc", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="AWS::EC2::VPC", last_reported_at="",
        service="ec2", tags="", macro_domain="Infraestrutura Compartilhada"
    )
    squad_infra, _, _ = resolve_ownership(r_infra, catalog, inferred_app="Infraestrutura Compartilhada")
    assert squad_infra == "Squad Infraestrutura Cloud"

    # Tag squad/team fallback com owner e criticality
    r_tag = ResourceRecord(
        identifier="custom-worker", arn="arn:aws:ec2:123:instance/i-custom",
        resource_type="ec2:instance", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="", last_reported_at="",
        service="ec2", tags="env=prod;squad=payments;owner=lead"
    )
    squad_tag, owner_tag, crit_tag = resolve_ownership(r_tag, catalog)
    assert squad_tag == "Squad Payments"
    assert owner_tag == "lead"
    assert crit_tag == "Padrão"

    # Tag com responsavel e criticidade
    r_tag2 = ResourceRecord(
        identifier="custom-db", arn="arn:aws:rds:123:db/custom-db",
        resource_type="rds:db", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="", last_reported_at="",
        service="rds", tags="responsavel=mariana;criticidade=alta;team=checkout"
    )
    squad_tag2, owner_tag2, crit_tag2 = resolve_ownership(r_tag2, catalog)
    assert squad_tag2 == "Squad Checkout"
    assert owner_tag2 == "mariana"
    assert crit_tag2 == "Alta"

    # Inferred app
    r_app = ResourceRecord(
        identifier="billing-worker", arn="arn:aws:ec2:123:instance/i-billing",
        resource_type="ec2:instance", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="", last_reported_at="",
        service="ec2", tags=""
    )
    squad_app, _, _ = resolve_ownership(r_app, catalog, inferred_app="Billing Service")
    assert squad_app == "Squad Billing Service"

    # Fallback genérico
    r_unknown = ResourceRecord(
        identifier="generic-item", arn="arn:aws:ec2:123:item",
        resource_type="ec2", region="us-east-1", aws_account="123",
        application_raw="", cfn_resource_type="", last_reported_at="",
        service="ec2", tags="", macro_domain="A Classificar"
    )
    squad_unk, _, crit_unk = resolve_ownership(r_unknown, catalog, inferred_app="Não Identificado")
    assert squad_unk == "Squad A Definir"
    assert crit_unk == "Padrão"

def test_load_application_catalog():
    cat = load_application_catalog()
    assert isinstance(cat, dict)
    assert "canais-digitais" in cat
    assert cat["canais-digitais"]["squad"] == "Squad Canais & Portais"

    cat_none = load_application_catalog("nonexistent_path_xyz.json")
    assert cat_none == {}

def test_infer_connections():
    comp_alb = TopologyComponent(
        id="alb-vdo", name="alb-vdo", service="elasticloadbalancing",
        layer="Ingresso & Endpoints", arn="arn:aws:alb:123:alb-vdo",
        region="us-east-1", squad="Squad Marketing"
    )
    comp_tg = TopologyComponent(
        id="tg-vdo-80", name="tg-vdo-80", service="elasticloadbalancing",
        layer="Ingresso & Endpoints", arn="arn:aws:tg:123:tg-vdo-80",
        region="us-east-1", squad="Squad Marketing"
    )
    comp_ec2 = TopologyComponent(
        id="i-0123vdo", name="vdo-web-server", service="ec2",
        layer="Computação & Lógica", arn="arn:aws:ec2:123:i-0123vdo",
        region="us-east-1", squad="Squad Marketing"
    )
    comp_rds = TopologyComponent(
        id="vdo-mysql-prd", name="vdo-mysql-prd", service="rds",
        layer="Banco de Dados & Cache", arn="arn:aws:rds:123:db:vdo-mysql-prd",
        region="us-east-1", squad="Squad Marketing"
    )
    comp_sqs = TopologyComponent(
        id="queue-vdo-events", name="queue-vdo-events", service="sqs",
        layer="Mensageria & Filas", arn="arn:aws:sqs:us-east-1:123:queue-vdo-events",
        region="us-east-1", squad="Squad Marketing"
    )
    comp_lambda = TopologyComponent(
        id="func-vdo-processor", name="func-vdo-processor", service="lambda",
        layer="Computação & Lógica", arn="arn:aws:lambda:us-east-1:123:function:func-vdo-processor",
        region="us-east-1", squad="Squad Marketing"
    )
    comp_s3 = TopologyComponent(
        id="bucket-vdo-assets", name="bucket-vdo-assets", service="s3",
        layer="Armazenamento & Apoio", arn="arn:aws:s3:::bucket-vdo-assets",
        region="us-east-1", squad="Squad Marketing"
    )

    components = [comp_alb, comp_tg, comp_ec2, comp_rds, comp_sqs, comp_lambda, comp_s3]
    connections = infer_connections(components, slug="vdo")

    # Verifica se conexões foram criadas
    assert len(connections) >= 5
    # Verifica vínculo ALB -> TG
    assert any(c.source_id == "alb-vdo" and c.target_id == "tg-vdo-80" for c in connections)
    # Verifica vínculo TG -> EC2
    assert any(c.source_id == "tg-vdo-80" and c.target_id == "i-0123vdo" for c in connections)
    # Verifica vínculo EC2 -> RDS
    assert any(c.source_id == "i-0123vdo" and c.target_id == "vdo-mysql-prd" for c in connections)
    # Verifica vínculo SQS -> Lambda (Mensageria -> Computação)
    assert any(c.source_id == "queue-vdo-events" and c.target_id == "func-vdo-processor" for c in connections)
    # Verifica vínculo Computação -> S3 (Compute -> Storage)
    assert any(c.source_id == "i-0123vdo" and c.target_id == "bucket-vdo-assets" for c in connections)
    assert any(c.source_id == "func-vdo-processor" and c.target_id == "bucket-vdo-assets" for c in connections)

    # Verifica se upstream_ids e downstream_ids foram preenchidos
    assert "tg-vdo-80" in comp_alb.downstream_ids
    assert "alb-vdo" in comp_tg.upstream_ids
    assert "i-0123vdo" in comp_tg.downstream_ids
    assert "vdo-mysql-prd" in comp_ec2.downstream_ids
    assert "func-vdo-processor" in comp_sqs.downstream_ids
    assert "queue-vdo-events" in comp_lambda.upstream_ids
    assert "bucket-vdo-assets" in comp_ec2.downstream_ids
    assert "bucket-vdo-assets" in comp_lambda.downstream_ids
    assert "i-0123vdo" in comp_s3.upstream_ids
    assert "func-vdo-processor" in comp_s3.upstream_ids

def test_analyze_application_topology_e2e_structure():
    r_alb = ResourceRecord(
        identifier="alb-vdo", arn="arn:aws:alb:123:alb-vdo", resource_type="elasticloadbalancing:loadbalancer",
        region="us-east-1", aws_account="807445251352", application_raw="VDO & Promoção Digital",
        cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer", last_reported_at="",
        service="elasticloadbalancing", tags="", inferred_app="VDO & Promoção Digital"
    )
    r_ec2 = ResourceRecord(
        identifier="i-1234vdo", arn="arn:aws:ec2:123:i-1234vdo", resource_type="ec2:instance",
        region="us-east-1", aws_account="807445251352", application_raw="VDO & Promoção Digital",
        cfn_resource_type="AWS::EC2::Instance", last_reported_at="",
        service="ec2", tags="", inferred_app="VDO & Promoção Digital"
    )
    r_shared = ResourceRecord(
        identifier="shared-vpc", arn="arn:aws:ec2:123:vpc/shared-vpc", resource_type="ec2:vpc",
        region="us-east-1", aws_account="807445251352", application_raw="",
        cfn_resource_type="AWS::EC2::VPC", last_reported_at="",
        service="ec2", tags="", macro_domain="Infraestrutura Compartilhada", inferred_app="Infraestrutura Compartilhada"
    )

    cluster_vdo = ApplicationCluster(
        name="VDO & Promoção Digital",
        slug="vdo-promocao",
        resources=[r_alb, r_ec2]
    )

    report_data = InventoryReportData(
        account_id="807445251352",
        total_resources=3,
        unique_arns=3,
        regions={"us-east-1": 3},
        services={"elasticloadbalancing": 1, "ec2": 2},
        macro_domains={"Aplicação": 2, "Infraestrutura Compartilhada": 1},
        finops_summary={"Avaliar": 3},
        clusters=[cluster_vdo],
        all_resources=[r_alb, r_ec2, r_shared],
        account_name="multicanais-dev"
    )

    result = analyze_application_topology(report_data)

    assert result.total_applications == 1
    assert result.total_components == 2
    assert len(result.applications) == 1
    assert result.applications[0].app_name == "VDO & Promoção Digital"
    assert len(result.shared_infrastructure) == 1
    assert result.shared_infrastructure[0].id == "shared-vpc"

def test_analyze_application_topology_catalog_lookup_by_slug():
    r_item = ResourceRecord(
        identifier="portal-alb", arn="arn:aws:alb:123:portal-alb", resource_type="elasticloadbalancing:loadbalancer",
        region="us-east-1", aws_account="807445251352", application_raw="portal",
        cfn_resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer", last_reported_at="",
        service="elasticloadbalancing", tags="", inferred_app="portal"
    )
    # Nome não bate ("Portal do Cliente"), mas slug bate com a chave do catálogo ("canais-digitais")
    cluster = ApplicationCluster(
        name="Portal do Cliente",
        slug="canais-digitais",
        resources=[r_item]
    )
    report_data = InventoryReportData(
        account_id="807445251352",
        total_resources=1,
        unique_arns=1,
        regions={"us-east-1": 1},
        services={"elasticloadbalancing": 1},
        macro_domains={"Aplicação": 1},
        finops_summary={},
        clusters=[cluster],
        all_resources=[r_item]
    )
    result = analyze_application_topology(report_data)
    assert len(result.applications) == 1
    app = result.applications[0]
    assert app.squad == "Squad Canais & Portais"
    assert app.owner == "techlead-canais@empresa.com"
    assert app.criticality == "Crítica / Tier 1"
