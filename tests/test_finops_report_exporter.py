import os
import pytest
from src.models import FinOpsOpportunity, PlaybookGuide, FinOpsAnalysisResult
from src.exporters.finops_report import export_finops_opportunities_markdown

def test_export_finops_opportunities_markdown(tmp_path):
    output_file = tmp_path / "relatorio_oportunidades_finops_test.md"

    opp = FinOpsOpportunity(
        pillar="Superdimensionamento",
        title="Desproporção de ALBs",
        description="9 ALBs para 2 instâncias",
        evidence_status="[AÇÃO IMEDIATA]",
        effort_level="Baixo (Quick Win)",
        impact_level="Alto",
        estimated_monthly_savings_usd=157.50,
        affected_resources_count=9,
        resource_identifiers=["app/Docker-dev/6de4d3f3d608fb4c"],
        playbook_id="pb-alb-traffic"
    )

    guide = PlaybookGuide(
        playbook_id="pb-alb-traffic",
        title="Playbook: Tráfego de ALBs",
        target_metric="RequestCount == 0",
        target_resources=["app/Docker-dev/6de4d3f3d608fb4c"],
        console_path="CloudWatch > Metrics > ALB",
        aws_cli_command="aws cloudwatch get-metric-statistics ...",
        decision_criteria="Se zero requisições",
        recommended_action="Consolidar ALBs"
    )

    analysis = FinOpsAnalysisResult(
        account_id="multicanais-dev",
        total_opportunities=1,
        immediate_actions_count=1,
        needs_analysis_count=0,
        total_estimated_monthly_savings_usd=157.50,
        pillar_consumption_opportunities=[],
        pillar_rightsizing_opportunities=[opp],
        pillar_cost_reduction_opportunities=[],
        playbooks=[guide]
    )

    export_finops_opportunities_markdown(analysis, str(output_file))

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "Relatório Executivo de Oportunidades FinOps" in content
    assert "multicanais-dev" in content
    assert "Scorecard Executivo & Impacto Financeiro" in content
    assert "Desproporção de ALBs" in content
    assert "$157.50" in content
    assert "Playbook: Tráfego de ALBs" in content
    assert "aws cloudwatch get-metric-statistics" in content
    assert "Roadmap Recomendado de Execução" in content
    # Verificar indicador de lista vazia no Pilar A e C
    assert "_Nenhuma oportunidade identificada neste pilar._" in content

def test_export_finops_opportunities_markdown_empty_and_subdirectories(tmp_path):
    nested_output = tmp_path / "deep" / "nested" / "relatorio.md"
    analysis = FinOpsAnalysisResult(
        account_id="empty-account",
        total_opportunities=0,
        immediate_actions_count=0,
        needs_analysis_count=0,
        total_estimated_monthly_savings_usd=0.0,
        pillar_consumption_opportunities=[],
        pillar_rightsizing_opportunities=[],
        pillar_cost_reduction_opportunities=[],
        playbooks=[]
    )

    export_finops_opportunities_markdown(analysis, str(nested_output))

    assert nested_output.exists()
    content = nested_output.read_text(encoding="utf-8")
    assert "Conta empty-account" in content
    assert "$0.00 USD/mês" in content
    assert "$0.00 USD/ano" in content

def test_export_finops_opportunities_markdown_large_resource_list_and_no_playbook(tmp_path):
    output_file = tmp_path / "relatorio_large.md"

    opp = FinOpsOpportunity(
        pillar="Redução de Custos",
        title="Elastic IPs Desassociados",
        description="EIPs sem instância",
        evidence_status="[AÇÃO IMEDIATA]",
        effort_level="Baixo (Quick Win)",
        impact_level="Baixo",
        estimated_monthly_savings_usd=None,  # Testa fallback "A Auditar"
        affected_resources_count=15,
        resource_identifiers=[f"eip-{i}" for i in range(15)],
        playbook_id=None  # Testa fallback "Ação Direta"
    )

    guide = PlaybookGuide(
        playbook_id="pb-large",
        title="Playbook 1: Teste com Mais de 10 Recursos",
        target_metric="Test Metric",
        target_resources=[f"res-{i}" for i in range(15)],
        console_path="Console",
        aws_cli_command="aws test command",
        decision_criteria="Critério",
        recommended_action="Ação"
    )

    analysis = FinOpsAnalysisResult(
        account_id="large-account",
        total_opportunities=1,
        immediate_actions_count=1,
        needs_analysis_count=0,
        total_estimated_monthly_savings_usd=0.0,
        pillar_consumption_opportunities=[],
        pillar_rightsizing_opportunities=[],
        pillar_cost_reduction_opportunities=[opp],
        playbooks=[guide]
    )

    export_finops_opportunities_markdown(analysis, str(output_file))

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "A Auditar" in content
    assert "Ação Direta" in content
    assert "(+ 5 adicionais)" in content
