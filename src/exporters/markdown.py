from pathlib import Path
from src.models import InventoryReportData

def generate_markdown_report(data: InventoryReportData, output_file: str) -> str:
    md = []
    md.append(f"# Relatório Executivo de Inventário AWS e FinOps — {data.display_title}\n")
    md.append("> **Aviso Legal:** Todas as classificações de FinOps constituem sugestões consultivas para suporte à auditoria do time técnico e não devem ser executadas sem validação prévia de negócio.\n")
    
    # 1. Sumário Executivo
    md.append("## 1. Sumário Executivo")
    md.append(f"- **Total de Recursos Únicos Analisados:** `{data.total_resources}`")
    md.append(f"- **Conta AWS:** `{data.display_title}`")
    md.append(f"- **Regiões Detectadas:** {', '.join(f'`{r}` ({c})' for r, c in sorted(data.regions.items(), key=lambda x: x[1], reverse=True))}")
    md.append(f"- **Divisão Macro por Domínio:**")
    for dom, count in data.macro_domains.items():
        md.append(f"  - **{dom}:** `{count}` recursos")
    md.append("")

    # 2. Painel FinOps
    md.append("## 2. Painel de Sugestões FinOps")
    md.append("| Sugestão FinOps | Quantidade de Recursos |")
    md.append("| :--- | :--- |")
    for sug, count in data.finops_summary.items():
        md.append(f"| **{sug}** | `{count}` |")
    md.append("")

    # 3. Aplicações Descobertas
    md.append("## 3. Mapeamento de Aplicações e Cargas em Computação")
    for cl in data.clusters:
        md.append(f"### Aplicação: {cl.name}")
        md.append(f"- **Total de Recursos Mapeados:** `{len(cl.resources)}`")
        if cl.load_balancers:
            md.append(f"- **Load Balancers (ALBs):** {', '.join(f'`{lb}`' for lb in cl.load_balancers)}")
        if cl.target_groups:
            md.append(f"- **Target Groups:** {', '.join(f'`{tg}`' for tg in cl.target_groups)}")
        if cl.compute_instances:
            md.append(f"- **Instâncias EC2:** {', '.join(f'`{i}`' for i in cl.compute_instances)}")
        if cl.databases:
            md.append(f"- **Bancos de Dados:** {', '.join(f'`{db}`' for db in cl.databases)}")
        if cl.secrets:
            md.append(f"- **Secrets Manager:** {', '.join(f'`{s}`' for s in cl.secrets)}")
        if cl.storage_buckets:
            md.append(f"- **Buckets S3:** {', '.join(f'`{b}`' for b in cl.storage_buckets)}")
        md.append("")

    def _format_resource_label(r) -> str:
        if r.resource_name and r.resource_name != "-" and r.resource_name != r.identifier:
            return f"{r.resource_name} ({r.identifier})"
        return r.identifier

    shared_compute = [
        r for r in data.all_resources
        if r.macro_domain == "Infraestrutura Compartilhada"
        and r.service.lower() == "ec2"
        and "instance" in r.resource_type.lower()
    ]
    if shared_compute:
        md.append("### Cargas de Computação Compartilhadas / A Auditar")
        md.append(f"- **Total de Instâncias Não Associadas:** `{len(shared_compute)}`")
        md.append(f"- **Instâncias EC2:** {', '.join(f'`{_format_resource_label(r)}`' for r in shared_compute)}")
        md.append("")

    # 4. Ações Prioritárias de Investigação
    md.append("## 4. Oportunidades Prioritárias de Otimização (Quick Wins)")
    investigate_items = [r for r in data.all_resources if "Investigar" in r.finops_suggestion and r.finops_cost_impact in ("Alto", "Médio")]
    if investigate_items:
        md.append("| Recurso | Nome | Tipo / Serviço | Região | Impacto | Justificativa |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for r in investigate_items[:20]:
            name_val = f"`{r.resource_name}`" if r.resource_name != "-" else "-"
            md.append(f"| `{r.identifier}` | {name_val} | `{r.cfn_resource_type or r.resource_type}` | `{r.region}` | **{r.finops_cost_impact}** | {r.finops_rationale} |")
        if len(investigate_items) > 20:
            md.append(f"\n*(Mostrando 20 de {len(investigate_items)} itens de atenção; veja lista completa na planilha Excel)*")
    else:
        md.append("Nenhum recurso de alto ou médio impacto necessitando de investigação imediata.")
    md.append("")

    # 5. Guia de Uso em Novas Contas
    md.append("## 5. Instruções para Reutilização em Outras Contas")
    md.append("Para rodar esta análise em outras contas AWS exportadas:")
    md.append("```bash")
    md.append("python -m src.main --input-dir \"/caminho/para/csvs\" --output-dir \"/caminho/para/saida\"")
    md.append("```")

    full_text = "\n".join(md)
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full_text, encoding="utf-8")
    return full_text
