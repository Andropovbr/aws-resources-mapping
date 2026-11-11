import os
from typing import List
from src.models import FinOpsAnalysisResult, FinOpsOpportunity

def _format_opportunity_table(opportunities: List[FinOpsOpportunity]) -> str:
    if not opportunities:
        return "_Nenhuma oportunidade identificada neste pilar._\n\n"

    lines = [
        "| Status | Oportunidade | Impacto Financeiro Est. | Esforço | Recursos Afetados | Playbook / Ação |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for o in opportunities:
        savings = f"~${o.estimated_monthly_savings_usd:.2f}/mês" if o.estimated_monthly_savings_usd is not None else "A Auditar"
        playbook_ref = f"[`{o.playbook_id}`](#{o.playbook_id})" if o.playbook_id else "Ação Direta"
        status_badge = f"**{o.evidence_status}**"
        lines.append(
            f"| {status_badge} | **{o.title}**<br>{o.description} | **{savings}** | {o.effort_level} | {o.affected_resources_count} | {playbook_ref} |"
        )
    return "\n".join(lines) + "\n\n"

def export_finops_opportunities_markdown(analysis: FinOpsAnalysisResult, output_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    annual_savings = analysis.total_estimated_monthly_savings_usd * 12

    md = []
    md.append(f"# Relatório Executivo de Oportunidades FinOps — {analysis.display_title}\n")
    md.append("> **Aviso Consultivo:** Todas as estimativas financeiras e sugestões apresentadas constituem recomendações consultivas para priorização estratégica da equipe de engenharia e liderança. Nenhuma alteração destrutiva deve ser executada sem validação técnica prévia de negócio.\n")

    # 1. Scorecard Executivo
    md.append("## 1. Scorecard Executivo & Impacto Financeiro\n")
    md.append("| Indicador | Valor Consolidado | Observações |")
    md.append("| :--- | :--- | :--- |")
    md.append(f"| **Economia Mensal Estimada** | **~${analysis.total_estimated_monthly_savings_usd:,.2f} USD/mês** | Projeção combinada de ações diretas e agendamento |")
    md.append(f"| **Economia Anualizada Projetada** | **~${annual_savings:,.2f} USD/ano** | Projeção anual de budget liberado para inovação |")
    md.append(f"| **Total de Oportunidades** | `{analysis.total_opportunities}` | Mapeadas nos três pilares estratégicos |")
    md.append(f"| **Ações Imediatas (Quick Wins)** | `{analysis.immediate_actions_count}` | Evidência conclusiva presente no inventário |")
    md.append(f"| **Hipóteses com Playbook** | `{analysis.needs_analysis_count}` | Itens com dados parciais mantidos para validação |")
    md.append("\n")

    # Matriz de Priorização
    md.append("### Matriz de Priorização (Esforço x Impacto)\n")
    md.append("- **Quick Wins (Alto Impacto / Baixo Esforço):** Consolidação de ALBs excedentes e limpeza de recursos/snapshots residuais de teste.")
    md.append("- **Projetos Estruturais (Alto Impacto / Médio Esforço):** Implantação de agendamento automático 24x7 (Instance Scheduler) para EC2 e RDS em desenvolvimento.")
    md.append("- **Higienização Operacional (Médio/Baixo Impacto / Baixo Esforço):** Liberação de Elastic IPs soltos e encerramento de recursos em regiões não oficiais.\n\n")

    # 2. Pilar A
    md.append("## 2. Pilar A: Padrões de Consumo & Oportunidades de Agendamento\n")
    md.append(_format_opportunity_table(analysis.pillar_consumption_opportunities))

    # 3. Pilar B
    md.append("## 3. Pilar B: Recursos Superdimensionados (Right-sizing)\n")
    md.append(_format_opportunity_table(analysis.pillar_rightsizing_opportunities))

    # 4. Pilar C
    md.append("## 4. Pilar C: Serviços com Potencial de Redução de Custos\n")
    md.append(_format_opportunity_table(analysis.pillar_cost_reduction_opportunities))

    # 5. Playbooks de Investigação
    md.append("## 5. Playbooks Práticos de Investigação (Gaps de Telemetria)\n")
    md.append("Para os recursos onde o inventário estático não fornece séries temporais de consumo, utilize os roteiros e comandos AWS CLI abaixo para comprovar a ociosidade antes da tomada de decisão:\n\n")

    for pb in analysis.playbooks:
        md.append(f"<a id=\"{pb.playbook_id}\"></a>\n")
        md.append(f"### {pb.title}\n")
        md.append(f"- **Métrica-Alvo:** `{pb.target_metric}`")
        resources_display = f"`{', '.join(pb.target_resources[:10])}`" if pb.target_resources else "-"
        if len(pb.target_resources) > 10:
            resources_display += f" _(+ {len(pb.target_resources)-10} adicionais)_"
        md.append(f"- **Recursos Identificados:** {resources_display}")
        md.append(f"- **Caminho no Console:** {pb.console_path}")
        md.append(f"- **Critério de Decisão:** {pb.decision_criteria}")
        md.append(f"- **Ação Recomendada:** {pb.recommended_action}\n")
        md.append("#### Comando AWS CLI Pronto para Copiar:")
        md.append("```bash")
        md.append(pb.aws_cli_command)
        md.append("```\n")

    # 6. Roadmap
    md.append("## 6. Roadmap Recomendado de Execução (30 / 60 / 90 Dias)\n")
    md.append("1. **Primeiros 30 Dias (Quick Wins & Validação de Telemetria):**")
    md.append("   - Executar os comandos AWS CLI do Playbook 2 para verificar tráfego dos 9 ALBs e consolidar em 1 ou 2 balanceadores.")
    md.append("   - Liberar Elastic IPs desassociados e deletar snapshots de teste.")
    md.append("2. **60 Dias (Right-sizing e Agendamento Automático):**")
    md.append("   - Rodar consulta do AWS Compute Optimizer (Playbook 1) e redimensionar instâncias superdimensionadas.")
    md.append("   - Implantar rotina de Instance Scheduler (Playbook 3) para desligamento noturno em dev.")
    md.append("3. **90 Dias (Governança Contínua):**")
    md.append("   - Estabelecer alarmes de AWS Budgets e SCPs/políticas de tag para evitar proliferação regional descontrolada.\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
