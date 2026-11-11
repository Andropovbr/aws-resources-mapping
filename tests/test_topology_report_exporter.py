import os
import tempfile
import pytest
from src.models import (
    TopologyComponent,
    ComponentConnection,
    ApplicationTopology,
    TopologyAnalysisResult
)
from src.exporters.topology_report import (
    export_topology_report_markdown,
    _sanitize_node_id,
    _generate_mermaid_diagram,
)

def test_sanitize_node_id():
    assert _sanitize_node_id("alb-vdo") == "node_alb_vdo"
    assert _sanitize_node_id("arn:aws:s3:::my-bucket") == "node_arn_aws_s3_my_bucket"
    assert _sanitize_node_id("my_component_123") == "node_my_component_123"
    assert _sanitize_node_id("---test---") == "node_test"

def test_generate_mermaid_diagram_with_and_without_connections():
    comp_alb = TopologyComponent(
        id="alb-vdo", name="alb-vdo", service="elasticloadbalancing",
        layer="Ingresso & Endpoints", arn="arn:aws:alb:123:alb-vdo",
        region="us-east-1", squad="Squad Marketing", downstream_ids=["tg-vdo-80"]
    )
    comp_ec2 = TopologyComponent(
        id="i-1234567890abcdef0", name="vdo-app-worker-instance-with-a-very-long-name-exceeding-limit",
        service="ec2", layer="Computação & Lógica", arn="arn:aws:ec2:123:i-123",
        region="us-east-1", squad="Squad Marketing"
    )

    app_with_conn = ApplicationTopology(
        app_name="App Com Conexões",
        slug="app-conn",
        squad="Squad Marketing",
        owner="techlead@vdo.com",
        criticality="Alta",
        description="Aplicação teste",
        components=[comp_alb, comp_ec2],
        connections=[
            ComponentConnection(source_id="alb-vdo", target_id="i-1234567890abcdef0", connection_type="Ingress", label="HTTPS 443"),
            ComponentConnection(source_id="alb-vdo", target_id="i-1234567890abcdef0", connection_type="Ingress", label="")
        ]
    )

    diagram = _generate_mermaid_diagram(app_with_conn)
    assert "```mermaid" in diagram
    assert "flowchart LR" in diagram
    assert 'subgraph Ingress["Camada de Entrada & Endpoints"]' in diagram
    assert 'subgraph Compute["Computação & Lógica"]' in diagram
    assert 'node_alb_vdo["alb-vdo (elasticloadbalancing)"]' in diagram
    assert "..." in diagram  # Truncated long name
    assert 'node_alb_vdo -->|"HTTPS 443"| node_i_1234567890abcdef0' in diagram
    assert 'node_alb_vdo --> node_i_1234567890abcdef0' in diagram

    app_without_conn = ApplicationTopology(
        app_name="App Sem Conexões",
        slug="app-no-conn",
        squad="Squad Marketing",
        owner=None,
        criticality="Média",
        description="Aplicação isolada",
        components=[comp_alb],
        connections=[]
    )
    diagram_no_conn = _generate_mermaid_diagram(app_without_conn)
    assert "%% Sem conexões diretas inferidas nos metadados estáticos" in diagram_no_conn

def test_export_topology_report_markdown():
    comp_alb = TopologyComponent(
        id="alb-vdo", name="alb-vdo", service="elasticloadbalancing",
        layer="Ingresso & Endpoints", arn="arn:aws:alb:123:alb-vdo",
        region="us-east-1", squad="Squad Marketing", downstream_ids=["tg-vdo-80"]
    )
    comp_tg = TopologyComponent(
        id="tg-vdo-80", name="tg-vdo-80", service="elasticloadbalancing",
        layer="Ingresso & Endpoints", arn="arn:aws:tg:123:tg-vdo-80",
        region="us-east-1", squad="Squad Marketing", upstream_ids=["alb-vdo"], downstream_ids=["i-123"]
    )
    comp_ec2 = TopologyComponent(
        id="i-123", name="vdo-app-01", service="ec2",
        layer="Computação & Lógica", arn="arn:aws:ec2:123:i-123",
        region="us-east-1", squad="Squad Marketing", upstream_ids=["tg-vdo-80"]
    )

    conn1 = ComponentConnection(source_id="alb-vdo", target_id="tg-vdo-80", connection_type="Ingress", label="Roteia tráfego")
    conn2 = ComponentConnection(source_id="tg-vdo-80", target_id="i-123", connection_type="Ingress", label="Encaminha para target")

    app = ApplicationTopology(
        app_name="VDO & Promoção Digital",
        slug="vdo-promocao",
        squad="Squad Marketing",
        owner="lead@vdo.com",
        criticality="Alta",
        description="Sistema de gestão de promoções",
        components=[comp_alb, comp_tg, comp_ec2],
        connections=[conn1, conn2]
    )

    shared_comp = TopologyComponent(
        id="shared-vpc-01", name="shared-vpc", service="vpc",
        layer="Infraestrutura Compartilhada", arn="arn:aws:ec2:123:vpc/shared",
        region="us-east-1", squad="Squad Infraestrutura / Core"
    )

    unassigned_comp = TopologyComponent(
        id="orphan-vol-01", name="vol-xyz", service="ebs",
        layer="A Classificar", arn="arn:aws:ec2:123:volume/vol-xyz",
        region="us-east-1", squad="A Definir"
    )

    analysis = TopologyAnalysisResult(
        account_id="807445251352",
        account_name="multicanais-dev",
        account_display="Conta multicanais-dev (807445251352)",
        total_applications=1,
        total_components=3,
        total_connections=2,
        assigned_squads_count=1,
        squad_distribution={"Squad Marketing": 3},
        layer_distribution={"Ingresso & Endpoints": 2, "Computação & Lógica": 1},
        applications=[app],
        shared_infrastructure=[shared_comp],
        unassigned_components=[unassigned_comp]
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = os.path.join(tmpdir, "relatorio_topologia.md")
        result_path = export_topology_report_markdown(analysis, out_file)

        assert result_path == out_file
        assert os.path.exists(out_file)
        with open(out_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "# Relatório de Arquitetura de Aplicações, Topologia e Governança" in content
        assert "multicanais-dev" in content
        assert "Conta multicanais-dev (807445251352)" in content
        assert "```mermaid" in content
        assert "flowchart LR" in content
        assert "subgraph Ingress" in content
        assert "alb-vdo" in content
        assert "Squad Marketing" in content
        assert "## 4. Infraestrutura Compartilhada e Serviços Comuns" in content
        assert "shared-vpc-01" in content
        assert "## 5. Gaps de Governança (Componentes a Classificar)" in content
        assert "orphan-vol-01" in content
