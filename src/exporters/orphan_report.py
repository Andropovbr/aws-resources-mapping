import os
from typing import List
from src.models import OrphanAnalysisResult, OrphanCandidate

CATEGORY_SECTIONS = [
    ("## 2. Armazenamento (EBS e Snapshots)", ["Armazenamento"]),
    ("## 3. Rede & Conectividade (Elastic IPs, ENIs, Security Groups)", ["Rede & Conectividade", "Rede"]),
    ("## 4. Balanceamento de Carga (ALBs e Target Groups)", ["Balanceamento de Carga"]),
    ("## 5. Cache & Dados In-Memory (ElastiCache e MemoryDB)", ["Cache & Dados In-Memory"]),
    ("## 6. Segurança, Logs & Certificados (ACM e CloudWatch)", ["Segurança, Logs & Certificados"]),
]


def _format_candidate_table(candidates: List[OrphanCandidate]) -> str:
    if not candidates:
        return "_Nenhum candidato a recurso órfão identificado nesta categoria._\n\n"

    lines = [
        "| Status | Tipo | Identificador | Nome / Tag | Região | Desperdício Est. | Justificativa | Playbook / Ação |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for cand in candidates:
        status_badge = f"**{cand.status}**"
        waste_str = f"~${cand.estimated_monthly_waste_usd:.2f}/mês" if cand.estimated_monthly_waste_usd > 0 else "$0.00"
        playbook_ref = f"[`{cand.playbook_id}`](#{cand.playbook_id})" if cand.playbook_id else "Ação Direta"
        name_tag = cand.resource_name if cand.resource_name else "-"
        lines.append(
            f"| {status_badge} | {cand.resource_type} | {cand.resource_identifier} | {name_tag} | {cand.region} | {waste_str} | {cand.confidence_rationale} | {playbook_ref} |"
        )
    return "\n".join(lines) + "\n\n"


def export_orphan_report_markdown(analysis: OrphanAnalysisResult, output_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    annual_waste = analysis.total_estimated_monthly_waste_usd * 12

    md = []
    # Header & Advisory Warning
    md.append(f"# Relatório Executivo de Identificação de Recursos Órfãos — {analysis.display_title}\n")
    md.append(
        "> **Aviso Consultivo:** Todas as estimativas financeiras e sugestões apresentadas constituem "
        "recomendações consultivas de engenharia. Nenhuma exclusão de infraestrutura deve ser realizada sem "
        "validação prévia de negócio e execução dos passos de segurança recomendados nos playbooks.\n"
    )

    # 1. Scorecard Executivo de Recursos Órfãos
    md.append("## 1. Scorecard Executivo de Recursos Órfãos\n")
    md.append("| Indicador | Valor Consolidado | Observações |")
    md.append("| :--- | :--- | :--- |")
    md.append(f"| **Desperdício Mensal Estimado** | **~${analysis.total_estimated_monthly_waste_usd:,.2f} USD/mês** | Projeção combinada de custos diretos elimináveis |")
    md.append(f"| **Desperdício Anualizado Projetado** | **~${annual_waste:,.2f} USD/ano** | Projeção anual de budget recuperável |")
    md.append(f"| **Total de Recursos Auditados** | `{analysis.total_candidates}` | Recursos avaliados com potencial de ociosidade |")
    md.append(f"| **Recursos Confirmados Órfãos** | `{analysis.confirmed_orphans_count}` | Recursos sem vínculo ativo identificados no inventário |")
    md.append(f"| **Candidatos que Necessitam Validação** | `{analysis.potential_orphans_count}` | Recursos requerendo validação de tráfego/uso via playbook |")
    md.append("\n")

    # Matriz de Priorização (Esforço x Impacto)
    md.append("### Matriz de Priorização (Esforço x Impacto)\n")
    md.append("- **Quick Wins (Alto Impacto / Baixo Esforço):** Elastic IPs desassociados e volumes EBS disponíveis.")
    md.append("- **Projetos Estruturais (Alto Impacto / Médio Esforço):** Descomissionamento de ALBs ociosos e consolidação de Target Groups.")
    md.append("- **Higienização Operacional:** Exclusão de ENIs soltas, Security Groups sem uso e snapshots manuais residuais.\n\n")

    # Tabelas de Achados por Categoria (2 a 6)
    breakdown = analysis.categories_breakdown or {}
    for section_title, keys in CATEGORY_SECTIONS:
        md.append(f"{section_title}\n")
        candidates = []
        for key in keys:
            if key in breakdown:
                candidates = breakdown[key]
                if candidates:
                    break
        md.append(_format_candidate_table(candidates))

    # 7. Playbooks Práticos de Investigação e Descarte Seguro
    md.append("## 7. Playbooks Práticos de Investigação e Descarte Seguro\n")
    md.append("Roteiros técnicos operacionais e comandos AWS CLI com guardrails de segurança para validação e exclusão definitiva de recursos comprovadamente órfãos:\n\n")

    if not analysis.playbooks:
        md.append("_Nenhum playbook gerado._\n\n")
    else:
        for pb in analysis.playbooks:
            md.append(f"<a id=\"{pb.playbook_id}\"></a>\n")
            md.append(f"### {pb.title}\n")
            md.append(f"- **Categoria:** {pb.category}")
            unique_targets = list(dict.fromkeys(pb.target_resources)) if pb.target_resources else []
            resources_display = f"`{', '.join(unique_targets[:10])}`" if unique_targets else "-"
            if len(unique_targets) > 10:
                resources_display += f" _(+ {len(unique_targets)-10} adicionais)_"
            md.append(f"- **Recursos Identificados:** {resources_display}")
            md.append(f"- **Caminho no Console:** {pb.inspection_console_path}")
            md.append(f"- **Critério de Decisão:** {pb.decision_criteria}")
            md.append(f"- **Recomendação de Segurança (Guardrail):** {pb.safety_recommendation}\n")
            md.append("#### Passo 1: Validação e Inspeção (AWS CLI):")
            md.append("```bash")
            md.append(pb.inspection_cli_command)
            md.append("```\n")
            md.append("#### Passo 2: Remoção Segura (AWS CLI):")
            md.append("```bash")
            md.append(pb.safe_cleanup_cli_command)
            md.append("```\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
