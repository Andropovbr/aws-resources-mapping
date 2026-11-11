import pytest
from src.models import (
    TopologyComponent,
    ComponentConnection,
    ApplicationTopology,
    TopologyAnalysisResult
)

def test_topology_models_instantiation():
    comp_ingress = TopologyComponent(
        id="alb-vdo",
        name="alb-vdo",
        service="elasticloadbalancing",
        layer="Ingresso & Endpoints",
        arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/alb-vdo/1",
        region="us-east-1",
        squad="Squad Marketing & Promoções",
        owner="techlead-vdo@empresa.com",
        criticality="Alta",
        upstream_ids=[],
        downstream_ids=["tg-vdo-80"]
    )

    comp_compute = TopologyComponent(
        id="i-0123456789abcdef0",
        name="i-0123456789abcdef0",
        service="ec2",
        layer="Computação & Lógica",
        arn="arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
        region="us-east-1",
        squad="Squad Marketing & Promoções",
        owner="techlead-vdo@empresa.com",
        criticality="Alta",
        upstream_ids=["tg-vdo-80"],
        downstream_ids=["vdo-mysql-prd"]
    )

    conn = ComponentConnection(
        source_id="alb-vdo",
        target_id="tg-vdo-80",
        connection_type="Ingress",
        label="Roteia tráfego"
    )

    app_topo = ApplicationTopology(
        app_name="VDO & Promoção Digital",
        slug="vdo-promocao",
        squad="Squad Marketing & Promoções",
        owner="techlead-vdo@empresa.com",
        criticality="Alta",
        description="Sistema de gestão e veiculação de promoções",
        components=[comp_ingress, comp_compute],
        connections=[conn]
    )

    assert len(app_topo.ingress_components) == 1
    assert app_topo.ingress_components[0].id == "alb-vdo"
    assert len(app_topo.compute_components) == 1
    assert len(app_topo.messaging_components) == 0
    assert len(app_topo.database_components) == 0
    assert len(app_topo.storage_components) == 0

    comp_storage = TopologyComponent(
        id="s3-vdo-assets",
        name="s3-vdo-assets",
        service="s3",
        layer="Armazenamento & Apoio",
        arn="arn:aws:s3:::s3-vdo-assets",
        region="us-east-1",
        squad="Squad Marketing & Promoções"
    )
    app_topo.components.append(comp_storage)
    assert len(app_topo.storage_components) == 1
    assert app_topo.storage_components[0].id == "s3-vdo-assets"

    analysis_result = TopologyAnalysisResult(
        account_id="123456789012",
        account_name="multicanais-dev",
        total_applications=1,
        total_components=3,
        total_connections=1,
        assigned_squads_count=1,
        squad_distribution={"Squad Marketing & Promoções": 3},
        layer_distribution={"Ingresso & Endpoints": 1, "Computação & Lógica": 1, "Armazenamento & Apoio": 1},
        applications=[app_topo],
        shared_infrastructure=[],
        unassigned_components=[]
    )

    assert analysis_result.display_title == "Conta multicanais-dev (123456789012)"

    # Testa com account_display explícito
    analysis_result.account_display = "Conta Produção Multicanais"
    assert analysis_result.display_title == "Conta Produção Multicanais"

    # Testa fallback apenas com account_id
    analysis_result.account_display = None
    analysis_result.account_name = None
    assert analysis_result.display_title == "Conta 123456789012"
