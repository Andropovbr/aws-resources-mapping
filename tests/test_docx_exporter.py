from pathlib import Path
import docx
import pytest

from src.exporters.docx_report import convert_markdown_to_docx


def test_convert_markdown_to_docx_basic(tmp_path: Path):
    md_file = tmp_path / "test.md"
    docx_file = tmp_path / "docs" / "test.docx"

    content = (
        "# Título Principal\n\n"
        "> Este é um aviso consultivo importante.\n\n"
        "## Subtítulo 1\n\n"
        "Este é um parágrafo normal com texto **em negrito** e código `inline`.\n\n"
        "### Listas e Comandos\n\n"
        "- Item de lista 1\n"
        "- Item de lista 2\n\n"
        "1. Primeiro passo\n"
        "2. Segundo passo\n\n"
        "```bash\n"
        "aws ec2 describe-instances --output table\n"
        "aws s3 ls\n"
        "```\n\n"
        "## Tabela de Dados\n\n"
        "| Coluna A | Coluna B | Coluna C |\n"
        "| :--- | :--- | :--- |\n"
        "| Valor 1 | Valor 2<br>Linha 2 | [`Link`](#pb-1) |\n"
        "| **Negrito** | `Código` | *Itálico* |\n"
    )
    md_file.write_text(content, encoding="utf-8")

    result_path = convert_markdown_to_docx(str(md_file), str(docx_file))
    assert Path(result_path).exists()

    doc = docx.Document(result_path)

    # Paragraphs check
    paras = [p.text for p in doc.paragraphs if p.text.strip()]
    assert any("Título Principal" in p for p in paras)
    assert any("Este é um aviso consultivo importante." in p for p in paras)
    assert any("Subtítulo 1" in p for p in paras)
    assert any("Item de lista 1" in p for p in paras)
    assert any("Primeiro passo" in p for p in paras)
    assert any("aws ec2 describe-instances" in p for p in paras)

    # Tables check
    assert len(doc.tables) == 1
    table = doc.tables[0]
    assert len(table.rows) == 3
    assert table.rows[0].cells[0].text == "Coluna A"
    assert "Linha 2" in table.rows[1].cells[1].text
    assert table.rows[1].cells[2].text == "Link"
    assert table.rows[2].cells[0].text == "Negrito"


def test_convert_markdown_to_docx_empty(tmp_path: Path):
    md_file = tmp_path / "empty.md"
    docx_file = tmp_path / "empty.docx"
    md_file.write_text("", encoding="utf-8")

    result_path = convert_markdown_to_docx(str(md_file), str(docx_file))
    assert Path(result_path).exists()
    doc = docx.Document(result_path)
    assert len(doc.paragraphs) == 0 or all(p.text == "" for p in doc.paragraphs)


def test_convert_markdown_to_docx_nested_dir(tmp_path: Path):
    md_file = tmp_path / "report.md"
    md_file.write_text("# Test Title\nParagraph", encoding="utf-8")
    nested_docx = tmp_path / "deep" / "nested" / "subfolder" / "report.docx"

    convert_markdown_to_docx(str(md_file), str(nested_docx))
    assert nested_docx.exists()
