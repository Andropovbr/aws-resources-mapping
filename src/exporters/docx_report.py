import os
import re
from pathlib import Path
from typing import List

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls


def _set_cell_background(cell, fill_hex: str) -> None:
    """Aplica cor de fundo a uma célula de tabela no Word."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)


def _set_cell_margins(cell, top=100, bottom=100, left=150, right=150) -> None:
    """Define margens internas de célula (em dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def _add_formatted_runs(paragraph, text: str, default_italic: bool = False) -> None:
    """Adiciona runs a um parágrafo interpretando formatações markdown básicas (**bold**, `code`, links)."""
    # Remove HTML tags como <a id="..."></a> e substitui <br> por quebra de linha
    text = re.sub(r'<a\s+id="[^"]*">\s*</a>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    # Remove links markdown [texto](url) mantendo apenas o texto
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Tokenizador regex para **negrito**, `código` e *itálico*
    pattern = re.compile(r'(\*\*[^*]+?\*\*|`[^`]+?`|\*[^*]+?\*)')
    tokens = pattern.split(text)

    for token in tokens:
        if not token:
            continue
        if token.startswith('**') and token.endswith('**') and len(token) >= 4:
            run = paragraph.add_run(token[2:-2])
            run.bold = True
            if default_italic:
                run.italic = True
        elif token.startswith('`') and token.endswith('`') and len(token) >= 2:
            run = paragraph.add_run(token[1:-1])
            run.font.name = 'Consolas'
            run.font.size = Pt(9.5)
            run.font.color.rgb = RGBColor(199, 37, 78)  # cor vinho/código
            if default_italic:
                run.italic = True
        elif token.startswith('*') and token.endswith('*') and len(token) >= 2:
            run = paragraph.add_run(token[1:-1])
            run.italic = True
        else:
            run = paragraph.add_run(token)
            if default_italic:
                run.italic = True


def _render_table(doc: docx.Document, table_lines: List[str]) -> None:
    """Processa e renderiza uma tabela Markdown no documento Word."""
    rows_data: List[List[str]] = []
    for line in table_lines:
        line_clean = line.strip()
        if not line_clean.startswith('|') or not line_clean.endswith('|'):
            continue
        cells = [c.strip() for c in line_clean[1:-1].split('|')]
        # Ignora linhas divisórias de cabeçalho tipo | :--- | :--- |
        if all(re.match(r'^:?-+:?$', c) for c in cells if c):
            continue
        rows_data.append(cells)

    if not rows_data:
        return

    num_cols = max(len(r) for r in rows_data)
    # Normaliza linhas para terem o mesmo número de colunas
    normalized_rows = [r + [''] * (num_cols - len(r)) for r in rows_data]

    table = doc.add_table(rows=len(normalized_rows), cols=num_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'

    for row_idx, row_values in enumerate(normalized_rows):
        is_header = (row_idx == 0)
        row = table.rows[row_idx]
        for col_idx, cell_value in enumerate(row_values):
            cell = row.cells[col_idx]
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)

            if is_header:
                _set_cell_background(cell, 'E8EEF5')
                run = p.add_run(cell_value)
                run.bold = True
                run.font.name = 'Segoe UI'
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(26, 54, 93)  # azul corporativo escuro
            else:
                _add_formatted_runs(p, cell_value)
                for r in p.runs:
                    if not r.font.name:
                        r.font.name = 'Segoe UI'
                    if not r.font.size:
                        r.font.size = Pt(9.0)

            _set_cell_margins(cell, top=100, bottom=100, left=120, right=120)

    # Adiciona espaçamento após a tabela
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(2)
    spacer.paragraph_format.space_after = Pt(6)


def convert_markdown_to_docx(markdown_path: str, output_docx_path: str) -> str:
    """
    Converte um relatório em formato Markdown para um documento Word (.docx)
    com estilização executiva profissional (títulos, tabelas, blocos de código e alertas).
    """
    out_dir = os.path.dirname(os.path.abspath(output_docx_path))
    os.makedirs(out_dir, exist_ok=True)

    doc = docx.Document()

    # Configuração de margens da página (Normal - 2.5 cm / 1 polegada)
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    if not os.path.exists(markdown_path):
        doc.save(output_docx_path)
        return output_docx_path

    with open(markdown_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    in_code_block = False
    code_block_lines: List[str] = []
    in_table = False
    table_lines: List[str] = []

    def flush_table():
        nonlocal in_table, table_lines
        if in_table and table_lines:
            _render_table(doc, table_lines)
            table_lines = []
            in_table = False

    def flush_code_block():
        nonlocal in_code_block, code_block_lines
        if in_code_block and code_block_lines:
            code_text = "".join(code_block_lines).rstrip()
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.right_indent = Inches(0.25)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(8)
            run = p.add_run(code_text)
            run.font.name = 'Consolas'
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(34, 34, 34)
            code_block_lines = []
            in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Bloco de código (```)
        if stripped.startswith('```'):
            if in_code_block:
                flush_code_block()
            else:
                flush_table()
                in_code_block = True
                code_block_lines = []
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # Tabela (| ... |)
        if stripped.startswith('|') and stripped.endswith('|'):
            in_table = True
            table_lines.append(line)
            continue
        elif in_table:
            flush_table()

        # Linhas em branco
        if not stripped:
            continue

        # HTML anchor tags ignoradas
        if re.match(r'^<a\s+id="[^"]*">\s*</a>$', stripped, re.IGNORECASE):
            continue

        # Títulos (# ...)
        if stripped.startswith('# '):
            h = doc.add_heading(level=1)
            h.paragraph_format.space_before = Pt(14)
            h.paragraph_format.space_after = Pt(6)
            _add_formatted_runs(h, stripped[2:].strip())
            continue
        elif stripped.startswith('## '):
            h = doc.add_heading(level=2)
            h.paragraph_format.space_before = Pt(12)
            h.paragraph_format.space_after = Pt(4)
            _add_formatted_runs(h, stripped[3:].strip())
            continue
        elif stripped.startswith('### '):
            h = doc.add_heading(level=3)
            h.paragraph_format.space_before = Pt(8)
            h.paragraph_format.space_after = Pt(3)
            _add_formatted_runs(h, stripped[4:].strip())
            continue
        elif stripped.startswith('#### '):
            h = doc.add_heading(level=4)
            h.paragraph_format.space_before = Pt(6)
            h.paragraph_format.space_after = Pt(2)
            _add_formatted_runs(h, stripped[5:].strip())
            continue

        # Blockquote / Avisos consultivos (> ...)
        if stripped.startswith('> '):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.3)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(6)
            _add_formatted_runs(p, stripped[2:].strip(), default_italic=True)
            continue

        # Listas não ordenadas (- ou * )
        if stripped.startswith('- ') or stripped.startswith('* '):
            p = doc.add_paragraph(style='List Bullet')
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(2)
            _add_formatted_runs(p, stripped[2:].strip())
            continue

        # Listas ordenadas (1. , 2. )
        list_num_match = re.match(r'^\d+\.\s+(.*)$', stripped)
        if list_num_match:
            p = doc.add_paragraph(style='List Number')
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(2)
            _add_formatted_runs(p, list_num_match.group(1).strip())
            continue

        # Parágrafo comum
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        _add_formatted_runs(p, stripped)

    # Flush final se o arquivo terminar com tabela ou código
    flush_table()
    flush_code_block()

    doc.save(output_docx_path)
    return output_docx_path
