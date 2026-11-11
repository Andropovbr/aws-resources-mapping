from pathlib import Path
from typing import List
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from src.models import InventoryReportData, ResourceRecord

HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="Calibri", size=14, bold=True, color="1F4E79")
BORDER_THIN = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9")
)

def _style_header(ws, row_idx: int, num_cols: int):
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row_idx, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

def _autofit_columns(ws):
    for col in ws.columns:
        if not col:
            continue
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 60)

def generate_excel_workbook(data: InventoryReportData, output_file: str) -> None:
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # 1. Resumo Executivo
    ws_resumo = wb.create_sheet(title="Resumo Executivo")
    ws_resumo.cell(row=1, column=1, value=f"Inventário AWS & FinOps — {data.display_title}").font = TITLE_FONT
    ws_resumo.cell(row=3, column=1, value="Métrica").font = HEADER_FONT
    ws_resumo.cell(row=3, column=2, value="Valor").font = HEADER_FONT
    ws_resumo.cell(row=3, column=1).fill = HEADER_FILL
    ws_resumo.cell(row=3, column=2).fill = HEADER_FILL
    
    metrics = [
        ("Total de Recursos Canônicos", data.total_resources),
        ("Total de ARNs Únicos", data.unique_arns),
        ("Conta AWS Analisada", data.account_id)
    ]
    for idx, (m, v) in enumerate(metrics, start=4):
        ws_resumo.cell(row=idx, column=1, value=m)
        ws_resumo.cell(row=idx, column=2, value=v)

    # Sugestões FinOps table
    ws_resumo.cell(row=8, column=1, value="Sugestão FinOps").font = HEADER_FONT
    ws_resumo.cell(row=8, column=2, value="Quantidade").font = HEADER_FONT
    ws_resumo.cell(row=8, column=1).fill = HEADER_FILL
    ws_resumo.cell(row=8, column=2).fill = HEADER_FILL
    for idx, (sug, count) in enumerate(data.finops_summary.items(), start=9):
        ws_resumo.cell(row=idx, column=1, value=sug)
        ws_resumo.cell(row=idx, column=2, value=count)
    _autofit_columns(ws_resumo)

    # Helper for tabular resource sheets
    def _create_resource_table(sheet_name: str, records: List[ResourceRecord], is_finops_action: bool = False):
        ws = wb.create_sheet(title=sheet_name)
        if is_finops_action:
            headers = [
                "Identificador", "Nome do Recurso", "Serviço", "Região", "Aplicação Inferida",
                "Sugestão FinOps", "Impacto de Custo", "Justificativa da Sugestão",
                "Decisão do Time (Manter/Deletar/Em Análise)", "Responsável", "Observações do Time"
            ]
        else:
            headers = [
                "Identificador", "Nome do Recurso", "ARN", "Tipo de Recurso", "Região", "Serviço",
                "Domínio", "Aplicação Inferida", "Sugestão FinOps", "Impacto", "Arquivos de Origem"
            ]
        
        ws.append(headers)
        _style_header(ws, 1, len(headers))
        
        for r in records:
            if is_finops_action:
                ws.append([
                    r.identifier, r.resource_name, r.service, r.region, r.inferred_app,
                    r.finops_suggestion, r.finops_cost_impact, r.finops_rationale,
                    "", "", ""
                ])
            else:
                ws.append([
                    r.identifier, r.resource_name, r.arn, r.cfn_resource_type or r.resource_type, r.region, r.service,
                    r.macro_domain, r.inferred_app, r.finops_suggestion, r.finops_cost_impact,
                    ", ".join(r.source_files)
                ])
        ws.auto_filter.ref = ws.dimensions
        _autofit_columns(ws)

    # 2. FinOps & Ações do Time
    finops_records = [r for r in data.all_resources if "Investigar" in r.finops_suggestion]
    _create_resource_table("FinOps & Ações do Time", finops_records, is_finops_action=True)

    # 3. Aplicações & Compute
    app_records = [r for r in data.all_resources if r.macro_domain == "Aplicação" or r.service in ("ec2", "elasticloadbalancing")]
    _create_resource_table("Aplicações & Compute", app_records)

    # 4. Bancos & Armazenamento
    storage_records = [r for r in data.all_resources if r.service in ("rds", "s3", "secretsmanager", "elasticache", "memorydb")]
    _create_resource_table("Bancos & Armazenamento", storage_records)

    # 5. Governança & Segurança
    gov_records = [r for r in data.all_resources if r.macro_domain == "Governança"]
    _create_resource_table("Governança & Segurança", gov_records)

    # 6. Inventário Geral
    _create_resource_table("Inventário Geral", data.all_resources)

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_file)
