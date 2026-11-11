import pytest
from src.models import (
    OrphanCandidate,
    OrphanPlaybookGuide,
    OrphanAnalysisResult,
    ResourceRecord,
    InventoryReportData,
)
from src.exporters.orphan_report import export_orphan_report_markdown
from src.orphan_analyzer import analyze_orphaned_resources


def test_export_orphan_report_markdown_complete(tmp_path):
    output_file = tmp_path / "relatorio_orfaos_test.md"

    cand_ebs = OrphanCandidate(
        category="Armazenamento",
        resource_type="ec2:volume",
        resource_identifier="vol-0123456789abcdef0",
        resource_name="disco-legado",
        region="us-east-1",
        status="[CANDIDATO A ÓRFÃO]",
        confidence_rationale="Volume EBS em estado available sem anexação ativa",
        estimated_monthly_waste_usd=8.00,
        playbook_id="pb-orphan-ebs-volumes",
    )

    cand_eip = OrphanCandidate(
        category="Rede & Conectividade",
        resource_type="ec2:elastic-ip",
        resource_identifier="54.210.10.20",
        resource_name="-",
        region="us-east-1",
        status="[CONFIRMADO ÓRFÃO]",
        confidence_rationale="Elastic IP alocado sem associação a instância ou ENI",
        estimated_monthly_waste_usd=3.65,
        playbook_id="pb-orphan-elastic-ips",
    )

    pb_ebs = OrphanPlaybookGuide(
        playbook_id="pb-orphan-ebs-volumes",
        title="Playbook 1: Auditoria e Descarte de Volumes EBS Desanexados",
        category="Armazenamento",
        target_resources=["vol-0123456789abcdef0"],
        inspection_console_path="EC2 > Elastic Block Store > Volumes (Filtrar por Status: Available)",
        inspection_cli_command="aws ec2 describe-volumes --region us-east-1 --filters Name=status,Values=available",
        decision_criteria="Validar se o status do volume está available e dados residuais descartáveis.",
        safe_cleanup_cli_command="aws ec2 delete-volume --region us-east-1 --volume-id vol-0123456789abcdef0",
        safety_recommendation="Criar snapshot manual antes de excluir.",
    )

    pb_eip = OrphanPlaybookGuide(
        playbook_id="pb-orphan-elastic-ips",
        title="Playbook 3: Auditoria e Liberação de Elastic IPs Não Associados",
        category="Rede & Conectividade",
        target_resources=["54.210.10.20"],
        inspection_console_path="EC2 > Network & Security > Elastic IPs",
        inspection_cli_command="aws ec2 describe-addresses --region us-east-1",
        decision_criteria="Confirmar se o Elastic IP não possui NetworkInterfaceId.",
        safe_cleanup_cli_command="aws ec2 release-address --region us-east-1 --allocation-id eipalloc-12345",
        safety_recommendation="Verificar registros em zonas DNS antes da liberação.",
    )

    analysis = OrphanAnalysisResult(
        account_id="123456789012",
        total_candidates=2,
        confirmed_orphans_count=1,
        potential_orphans_count=1,
        total_estimated_monthly_waste_usd=11.65,
        categories_breakdown={
            "Armazenamento": [cand_ebs],
            "Rede & Conectividade": [cand_eip],
            "Balanceamento de Carga": [],
            "Cache & Dados In-Memory": [],
            "Segurança, Logs & Certificados": [],
        },
        playbooks=[pb_ebs, pb_eip],
    )

    export_orphan_report_markdown(analysis, str(output_file))

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")

    # Header & Advisory
    assert "# Relatório Executivo de Identificação de Recursos Órfãos — Conta 123456789012" in content
    assert "> **Aviso Consultivo:**" in content

    # Scorecard Executivo
    assert "## 1. Scorecard Executivo de Recursos Órfãos" in content
    assert "| Indicador | Valor Consolidado | Observações |" in content
    assert "~$11.65 USD/mês" in content
    assert f"~${11.65 * 12:,.2f} USD/ano" in content
    assert "| `2` |" in content
    assert "| `1` |" in content

    # Matriz de Priorização
    assert "### Matriz de Priorização (Esforço x Impacto)" in content
    assert "Quick Wins (Alto Impacto / Baixo Esforço)" in content
    assert "Projetos Estruturais (Alto Impacto / Médio Esforço)" in content
    assert "Higienização Operacional" in content

    # Categories
    assert "## 2. Armazenamento (EBS e Snapshots)" in content
    assert "## 3. Rede & Conectividade (Elastic IPs, ENIs, Security Groups)" in content
    assert "## 4. Balanceamento de Carga (ALBs e Target Groups)" in content
    assert "## 5. Cache & Dados In-Memory (ElastiCache e MemoryDB)" in content
    assert "## 6. Segurança, Logs & Certificados (ACM e CloudWatch)" in content

    # Candidate table headers & content
    table_header = "| Status | Tipo | Identificador | Nome / Tag | Região | Desperdício Est. | Justificativa | Playbook / Ação |"
    assert table_header in content
    assert "**[CANDIDATO A ÓRFÃO]**" in content
    assert "**[CONFIRMADO ÓRFÃO]**" in content
    assert "vol-0123456789abcdef0" in content
    assert "disco-legado" in content
    assert "~$8.00/mês" in content
    assert "~$3.65/mês" in content
    assert "[`pb-orphan-ebs-volumes`](#pb-orphan-ebs-volumes)" in content
    assert "[`pb-orphan-elastic-ips`](#pb-orphan-elastic-ips)" in content

    # Empty category indicator
    assert "_Nenhum candidato a recurso órfão identificado nesta categoria._" in content

    # Playbooks section
    assert "## 7. Playbooks Práticos de Investigação e Descarte Seguro" in content
    assert '<a id="pb-orphan-ebs-volumes"></a>' in content
    assert '<a id="pb-orphan-elastic-ips"></a>' in content
    assert "### Playbook 1: Auditoria e Descarte de Volumes EBS Desanexados" in content
    assert "- **Categoria:** Armazenamento" in content
    assert "- **Recursos Identificados:** `vol-0123456789abcdef0`" in content
    assert "- **Caminho no Console:** EC2 > Elastic Block Store > Volumes (Filtrar por Status: Available)" in content
    assert "- **Critério de Decisão:** Validar se o status do volume está available e dados residuais descartáveis." in content
    assert "- **Recomendação de Segurança (Guardrail):** Criar snapshot manual antes de excluir." in content
    assert "#### Passo 1: Validação e Inspeção (AWS CLI):" in content
    assert "aws ec2 describe-volumes --region us-east-1 --filters Name=status,Values=available" in content
    assert "#### Passo 2: Remoção Segura (AWS CLI):" in content
    assert "aws ec2 delete-volume --region us-east-1 --volume-id vol-0123456789abcdef0" in content


def test_orphan_report_title_with_account_name(tmp_path):
    output_file = tmp_path / "orphan_title.md"
    analysis = OrphanAnalysisResult(
        account_id="807445251352",
        total_candidates=0,
        confirmed_orphans_count=0,
        potential_orphans_count=0,
        total_estimated_monthly_waste_usd=0.0,
        categories_breakdown={},
        playbooks=[],
        account_name="multicanais-dev"
    )
    export_orphan_report_markdown(analysis, str(output_file))
    content = output_file.read_text(encoding="utf-8")
    assert "# Relatório Executivo de Identificação de Recursos Órfãos — Conta multicanais-dev (807445251352)" in content


def test_export_orphan_report_markdown_empty_and_subdirectories(tmp_path):
    nested_output = tmp_path / "deep" / "nested" / "relatorio_orfaos_vazio.md"

    analysis = OrphanAnalysisResult(
        account_id="empty-account",
        total_candidates=0,
        confirmed_orphans_count=0,
        potential_orphans_count=0,
        total_estimated_monthly_waste_usd=0.0,
        categories_breakdown={},
        playbooks=[],
    )

    export_orphan_report_markdown(analysis, str(nested_output))

    assert nested_output.exists()
    content = nested_output.read_text(encoding="utf-8")
    assert "Conta empty-account" in content
    assert "$0.00 USD/mês" in content
    assert "$0.00 USD/ano" in content
    assert content.count("_Nenhum candidato a recurso órfão identificado nesta categoria._") == 5


def test_export_orphan_report_markdown_large_resource_list_and_no_playbook(tmp_path):
    output_file = tmp_path / "relatorio_large.md"

    cand = OrphanCandidate(
        category="Armazenamento",
        resource_type="ec2:snapshot",
        resource_identifier="snap-zero-cost",
        resource_name="",
        region="sa-east-1",
        status="[CANDIDATO A ÓRFÃO]",
        confidence_rationale="Snapshot sem custo estimado",
        estimated_monthly_waste_usd=0.0,
        playbook_id="",  # Deve renderizar Ação Direta
    )

    pb = OrphanPlaybookGuide(
        playbook_id="pb-many-resources",
        title="Playbook Teste Mais de 10 Recursos",
        category="Armazenamento",
        target_resources=[f"res-{i}" for i in range(15)],
        inspection_console_path="Console",
        inspection_cli_command="aws test inspect",
        decision_criteria="Critério",
        safe_cleanup_cli_command="aws test cleanup",
        safety_recommendation="Guardrail",
    )

    analysis = OrphanAnalysisResult(
        account_id="test-acc",
        total_candidates=1,
        confirmed_orphans_count=0,
        potential_orphans_count=1,
        total_estimated_monthly_waste_usd=0.0,
        categories_breakdown={"Armazenamento": [cand]},
        playbooks=[pb],
    )

    export_orphan_report_markdown(analysis, str(output_file))

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")

    # Ação Direta for missing playbook_id
    assert "Ação Direta" in content
    # $0.00 formatted for zero waste
    assert "$0.00" in content
    # Nome / Tag fallback '-' when empty string
    assert "| - |" in content
    # (+ 5 adicionais) for target resources > 10
    assert "(+ 5 adicionais)" in content


def test_export_orphan_report_with_analyzer_integration(tmp_path):
    output_file = tmp_path / "relatorio_integrated.md"

    vol = ResourceRecord(
        identifier="vol-999",
        arn="arn:aws:ec2:us-east-1:111122223333:volume/vol-999",
        resource_type="ec2:volume",
        region="us-east-1",
        aws_account="111122223333",
        application_raw="-",
        cfn_resource_type="-",
        last_reported_at="2026-10-10",
        service="ec2",
        tags="0",
        resource_name="disco-extra",
    )

    data = InventoryReportData(
        account_id="111122223333",
        total_resources=1,
        unique_arns=1,
        regions={"us-east-1": 1},
        services={"ec2": 1},
        macro_domains={"Aplicação": 1},
        finops_summary={},
        clusters=[],
        all_resources=[vol],
    )

    analysis = analyze_orphaned_resources(data)
    export_orphan_report_markdown(analysis, str(output_file))

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "Conta 111122223333" in content
    assert "vol-999" in content
    assert "disco-extra" in content
    assert "pb-orphan-ebs-volumes" in content


def test_export_orphan_report_deduplicates_target_resources(tmp_path):
    output_file = tmp_path / "relatorio_dedup.md"

    pb = OrphanPlaybookGuide(
        playbook_id="pb-orphan-snapshots",
        title="Playbook 2: Auditoria e Descarte de Snapshots Residuais (EBS e RDS)",
        category="Armazenamento",
        target_resources=["snap-abc", "snap-abc", "snap-def", "snap-def", "snap-xyz"],
        inspection_console_path="Console",
        inspection_cli_command="aws test inspect",
        decision_criteria="Critério",
        safe_cleanup_cli_command="aws test cleanup",
        safety_recommendation="Guardrail",
    )

    analysis = OrphanAnalysisResult(
        account_id="acc-dedup",
        total_candidates=0,
        confirmed_orphans_count=0,
        potential_orphans_count=0,
        total_estimated_monthly_waste_usd=0.0,
        categories_breakdown={},
        playbooks=[pb],
    )

    export_orphan_report_markdown(analysis, str(output_file))

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "- **Recursos Identificados:** `snap-abc, snap-def, snap-xyz`" in content
    # Ensure duplicates are not in the display
    assert "snap-abc, snap-abc" not in content

