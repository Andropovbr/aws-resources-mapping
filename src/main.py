import argparse
import sys
from pathlib import Path
from collections import Counter
from typing import Tuple

from src.ingestion import load_and_deduplicate_csvs
from src.correlator import correlate_and_classify_resources
from src.finops import evaluate_finops_rules
from src.exporters.excel import generate_excel_workbook
from src.exporters.markdown import generate_markdown_report
from src.models import InventoryReportData

def run_pipeline(input_dir: str, output_dir: str, account: str = "") -> Tuple[str, str]:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"[*] Lendo e desduplicando CSVs em: {input_dir}")
    resources = load_and_deduplicate_csvs(input_dir)
    print(f"[+] Total de recursos canônicos consolidados: {len(resources)}")

    if not resources:
        raise ValueError(f"Nenhum recurso encontrado no diretório: {input_dir}")

    account_id = account or resources[0].aws_account or "aws-account"

    print("[*] Correlacionando recursos e inferindo aplicações...")
    resources, clusters = correlate_and_classify_resources(resources)
    print(f"[+] Aplicações detectadas: {len(clusters)} clusters ({', '.join(c.name for c in clusters)})")

    print("[*] Avaliando matriz de regras FinOps...")
    resources = evaluate_finops_rules(resources)

    # Compute summaries
    regions = Counter(r.region for r in resources)
    services = Counter(r.service for r in resources)
    macro_domains = Counter(r.macro_domain for r in resources)
    finops_summary = Counter(r.finops_suggestion for r in resources)

    report_data = InventoryReportData(
        account_id=account_id,
        total_resources=len(resources),
        unique_arns=len(set(r.arn for r in resources if r.arn)),
        regions=dict(regions),
        services=dict(services),
        macro_domains=dict(macro_domains),
        finops_summary=dict(finops_summary),
        clusters=clusters,
        all_resources=resources
    )

    clean_account_name = account_id.replace(" ", "_")
    excel_file = str(out_path / f"inventario_{clean_account_name}.xlsx")
    md_file = str(out_path / f"relatorio_{clean_account_name}.md")

    print(f"[*] Gerando pasta de trabalho Excel: {excel_file}")
    generate_excel_workbook(report_data, excel_file)

    print(f"[*] Gerando relatório executivo Markdown: {md_file}")
    generate_markdown_report(report_data, md_file)

    print("[✓] Processamento concluído com sucesso!")
    return excel_file, md_file

def main():
    parser = argparse.ArgumentParser(description="Mapeador de Recursos AWS e FinOps Pipeline")
    parser.add_argument("--input-dir", default="./", help="Diretório contendo os arquivos CSV de exportação")
    parser.add_argument("--output-dir", default="./output", help="Diretório de saída para os relatórios gerados")
    parser.add_argument("--account", default="multicanais-dev", help="Nome ou ID da conta AWS para titulação")
    args = parser.parse_args()

    try:
        run_pipeline(args.input_dir, args.output_dir, args.account)
    except Exception as e:
        print(f"[!] Erro durante execução do pipeline: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
