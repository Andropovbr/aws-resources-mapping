import re
from pathlib import Path
from src.models import (
    TopologyAnalysisResult,
    ApplicationTopology,
    TopologyComponent
)

def _sanitize_node_id(text: str) -> str:
    """Sanitiza strings para identificadores válidos em diagramas Mermaid."""
    sanitized = re.sub(r"[^a-zA-Z0-9_]+", "_", text).strip("_")
    return f"node_{sanitized}" if sanitized else "node_unknown"

def _generate_mermaid_diagram(app: ApplicationTopology) -> str:
    """Gera bloco Mermaid flowchart LR com subgrafos por camada funcional."""
    lines = ["```mermaid", "flowchart LR"]

    # Subgrafos por camada
    layers = [
        ("Ingress", "Camada de Entrada & Endpoints", app.ingress_components),
        ("Compute", "Computação & Lógica", app.compute_components),
        ("Messaging", "Mensageria & Filas", app.messaging_components),
        ("Database", "Banco de Dados & Cache", app.database_components),
        ("Storage", "Armazenamento & Apoio", app.storage_components),
    ]

    for sg_id, sg_title, comps in layers:
        if comps:
            lines.append(f'  subgraph {sg_id}["{sg_title}"]')
            for c in comps:
                node_id = _sanitize_node_id(c.id)
                disp_name = c.name if c.name and c.name != "-" else c.id
                # Trunca se for muito longo
                if len(disp_name) > 35:
                    disp_name = disp_name[:32] + "..."
                label = f"{disp_name} ({c.service})"
                safe_label = label.replace('"', "'")
                lines.append(f'    {node_id}["{safe_label}"]')
            lines.append("  end")

    # Arestas / Conexões
    if app.connections:
        lines.append("")
        for conn in app.connections:
            src = _sanitize_node_id(conn.source_id)
            tgt = _sanitize_node_id(conn.target_id)
            lbl = conn.label or ""
            safe_lbl = lbl.replace('"', "'")
            if safe_lbl:
                lines.append(f'  {src} -->|"{safe_lbl}"| {tgt}')
            else:
                lines.append(f"  {src} --> {tgt}")
    else:
        # Se não houver conexões inferidas, gera nota informativa
        lines.append("  %% Sem conexões diretas inferidas nos metadados estáticos")

    lines.append("```")
    return "\n".join(lines)

def export_topology_report_markdown(analysis: TopologyAnalysisResult, output_path: str) -> str:
    """
    Gera o relatório executivo e técnico em Markdown contendo:
    - Scorecard executivo de arquitetura e governança
    - Matriz de Ownership e Squads
    - Visão detalhada por aplicação com diagramas Mermaid
    - Inventário tabular de componentes
    - Componentes de infraestrutura compartilhada
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Relatório de Arquitetura de Aplicações, Topologia e Governança",
        "",
        f"**Ambiente:** {analysis.display_title}  ",
        f"**Conta AWS:** `{analysis.account_id}`  ",
        "**Status:** Consolidado e Auditado  ",
        "",
        "---",
        "",
        "## 1. Resumo Executivo de Governança e Arquitetura",
        "",
        "| Métrica Estratégica | Valor Consolidado |",
        "|---|---|",
        f"| **Aplicações de Negócio Mapeadas** | {analysis.total_applications} |",
        f"| **Componentes Arquiteturais Catalogados** | {analysis.total_components} |",
        f"| **Conexões e Integrações Inferidas** | {analysis.total_connections} |",
        f"| **Squads / Times com Responsabilidade Atribuída** | {analysis.assigned_squads_count} |",
        f"| **Itens em Infraestrutura Compartilhada** | {len(analysis.shared_infrastructure)} |",
        f"| **Componentes a Classificar / Gaps de Governança** | {len(analysis.unassigned_components)} |",
        "",
        "### 1.1 Distribuição por Camada Funcional",
        "",
        "| Camada Arquitetural | Quantidade de Componentes |",
        "|---|---|",
    ]

    for layer, count in sorted(analysis.layer_distribution.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| **{layer}** | {count} |")

    lines.extend([
        "",
        "---",
        "",
        "## 2. Matriz de Governança e Ownership (Squads e Responsáveis)",
        "",
        "| Aplicação | Squad Responsável | Tech Lead / Owner | Criticidade | Qtd Componentes | Endpoints Expostos |",
        "|---|---|---|---|---|---|",
    ])

    for app in analysis.applications:
        ingress_count = len(app.ingress_components)
        owner_str = app.owner if app.owner else "A definir"
        lines.append(
            f"| **{app.app_name}** | {app.squad} | {owner_str} | `{app.criticality}` | {len(app.components)} | {ingress_count} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Visão Arquitetural Detalhada por Aplicação",
        ""
    ])

    for idx, app in enumerate(analysis.applications, start=1):
        lines.extend([
            f"### 3.{idx} {app.app_name}",
            "",
            f"*{app.description}*",
            "",
            f"- **Squad Responsável:** `{app.squad}`",
            f"- **Tech Lead / Ponto Focal:** `{app.owner or 'A definir'}`",
            f"- **Nível de Criticidade:** `{app.criticality}`",
            f"- **Total de Componentes:** `{len(app.components)}`",
            "",
            "#### Diagrama de Arquitetura e Fluxo de Integração",
            "",
            _generate_mermaid_diagram(app),
            "",
            "#### Inventário de Componentes e Interfaces",
            "",
            "| Componente (ID) | Serviço | Camada | Região | Origem (Upstream) | Destino (Downstream) |",
            "|---|---|---|---|---|---|",
        ])

        for comp in app.components:
            up_str = ", ".join(comp.upstream_ids) if comp.upstream_ids else "-"
            down_str = ", ".join(comp.downstream_ids) if comp.downstream_ids else "-"
            disp_id = comp.id
            if len(disp_id) > 40:
                disp_id = disp_id[:37] + "..."
            lines.append(f"| `{disp_id}` | `{comp.service}` | {comp.layer} | `{comp.region}` | {up_str} | {down_str} |")

        lines.append("")

    if analysis.shared_infrastructure:
        lines.extend([
            "---",
            "",
            "## 4. Infraestrutura Compartilhada e Serviços Comuns",
            "",
            "Recursos de suporte central (segurança, rede compartilhada, auditoria) que atendem a múltiplos domínios:",
            "",
            "| Identificador | Serviço | Camada | Squad Responsável | Região |",
            "|---|---|---|---|---|",
        ])
        for c in analysis.shared_infrastructure[:50]:  # Limita para não inflar desnecessariamente o relatório
            lines.append(f"| `{c.id}` | `{c.service}` | {c.layer} | {c.squad} | `{c.region}` |")
        lines.append("")
        if len(analysis.shared_infrastructure) > 50:
            lines.append(f"> *Nota: Exibindo os primeiros 50 itens de {len(analysis.shared_infrastructure)}. Consulte o Excel para a listagem integral.*")
            lines.append("")

    if analysis.unassigned_components:
        lines.extend([
            "---",
            "",
            "## 5. Gaps de Governança (Componentes a Classificar)",
            "",
            "Recursos identificados que necessitam de definição de Squad e aplicação responsável:",
            "",
            "| Identificador | Serviço AWS | Camada | Região |",
            "|---|---|---|---|",
        ])
        for c in analysis.unassigned_components[:50]:
            lines.append(f"| `{c.id}` | `{c.service}` | {c.layer} | `{c.region}` |")
        lines.append("")
        if len(analysis.unassigned_components) > 50:
            lines.append(f"> *Nota: Exibindo os primeiros 50 itens de {len(analysis.unassigned_components)}. Consulte o Excel para a listagem integral.*")
            lines.append("")

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return str(out)
