# AWS Orphan Resources Detector & Playbooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar ao pipeline do `resources multicanais-dev` um subsistema analítico de detecção de recursos órfãos na AWS, cálculo de custos mensais desperdiçados e geração do relatório executivo `output/relatorio_recursos_orfaos_<conta>.md` acompanhado de playbooks com comandos do AWS CLI para validação e remoção segura.

**Architecture:** Módulo analítico dedicado (`src/orphan_analyzer.py`) que avalia o `InventoryReportData` nos 5 domínios prioritários (Armazenamento, Rede, Balanceamento, Cache, Segurança/Logs), classifica achados em `[CONFIRMADO ÓRFÃO]` ou `[CANDIDATO A ÓRFÃO]` com cálculo de custo estimado em dólares, acopla playbooks práticos (`OrphanPlaybookGuide`), delega para o exportador (`src/exporters/orphan_report.py`) e integra a chamada no fluxo padrão do CLI (`src/main.py`), finalizando com atualização do `README.md`.

**Tech Stack:** Python 3.10+, dataclasses, pytest, openpyxl, Markdown.

**Spec:** [docs/superpowers/specs/2026-11-10-aws-orphan-resources-detector-design.md](file:///C:/Users/andre.luiz/Documents/resources%20multicanais-dev/docs/superpowers/specs/2026-11-10-aws-orphan-resources-detector-design.md)

## Global Constraints

- Python versions: 3.10+
- Execution entrypoint: `python -m src.main --input-dir <dir> --output-dir <dir>`
- Report output naming: `output/relatorio_recursos_orfaos_<account_id>.md`
- Status conventions: `[CONFIRMADO ÓRFÃO]` (quando matematicamente comprovado pelo inventário estático) e `[CANDIDATO A ÓRFÃO]` (quando depende de validação via AWS CLI)
- Unit costs: EIP ($3.65/mês), Volume EBS padrão ($8.00/mês), ALB ocioso ($22.50/mês), Snapshot EBS ($2.50/mês), Snapshot RDS ($5.00/mês), Log Group ($1.50/mês)
- Strict test-driven development (TDD) with 100% test coverage
- End with full README.md update describing the new orphan resources detection feature

---

### Task 1: Orphan Data Models

**Files:**
- Modify: `src/models.py:80-120`
- Modify: `tests/test_models.py`

**Interfaces:**
- Consumes: Nothing
- Produces: `OrphanPlaybookGuide`, `OrphanCandidate`, `OrphanAnalysisResult` dataclasses

- [ ] **Step 1: Write the failing test for orphan models**

Edite `tests/test_models.py` adicionando o teste para as três novas dataclasses:

```python
from src.models import OrphanPlaybookGuide, OrphanCandidate, OrphanAnalysisResult

def test_orphan_models():
    guide = OrphanPlaybookGuide(
        playbook_id="pb-test",
        title="Test Playbook",
        category="Armazenamento",
        target_resources=["vol-123"],
        inspection_console_path="Console > EC2",
        inspection_cli_command="aws ec2 describe-volumes",
        decision_criteria="Se status available",
        safe_cleanup_cli_command="aws ec2 delete-volume",
        safety_recommendation="Fazer snapshot antes"
    )
    assert guide.playbook_id == "pb-test"

    candidate = OrphanCandidate(
        category="Armazenamento",
        resource_type="ec2:volume",
        resource_identifier="vol-123",
        resource_name="DiscoTeste",
        region="sa-east-1",
        status="[CANDIDATO A ÓRFÃO]",
        confidence_rationale="Volume listado sem checagem de anexo",
        estimated_monthly_waste_usd=8.0,
        playbook_id="pb-test"
    )
    assert candidate.estimated_monthly_waste_usd == 8.0

    result = OrphanAnalysisResult(
        account_id="123456789012",
        total_candidates=1,
        confirmed_orphans_count=0,
        potential_orphans_count=1,
        total_estimated_monthly_waste_usd=8.0,
        categories_breakdown={"Armazenamento": [candidate]},
        playbooks=[guide]
    )
    assert result.total_candidates == 1
    assert result.total_estimated_monthly_waste_usd == 8.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -k test_orphan_models -v`  
Expected: FAIL with `ImportError: cannot import name 'OrphanPlaybookGuide' from 'src.models'`

- [ ] **Step 3: Write minimal implementation in `src/models.py`**

Adicione em `src/models.py`:

```python
@dataclass
class OrphanPlaybookGuide:
    playbook_id: str
    title: str
    category: str
    target_resources: List[str]
    inspection_console_path: str
    inspection_cli_command: str
    decision_criteria: str
    safe_cleanup_cli_command: str
    safety_recommendation: str

@dataclass
class OrphanCandidate:
    category: str
    resource_type: str
    resource_identifier: str
    resource_name: str
    region: str
    status: str
    confidence_rationale: str
    estimated_monthly_waste_usd: float
    playbook_id: str

@dataclass
class OrphanAnalysisResult:
    account_id: str
    total_candidates: int
    confirmed_orphans_count: int
    potential_orphans_count: int
    total_estimated_monthly_waste_usd: float
    categories_breakdown: Dict[str, List[OrphanCandidate]]
    playbooks: List[OrphanPlaybookGuide]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`  
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat(models): add orphan resources data models"
```

---

### Task 2: Core Orphan Analyzer Engine

**Files:**
- Create: `src/orphan_analyzer.py`
- Create: `tests/test_orphan_analyzer.py`

**Interfaces:**
- Consumes: `InventoryReportData`, `ResourceRecord`, `OrphanCandidate`, `OrphanPlaybookGuide`, `OrphanAnalysisResult`
- Produces: `analyze_orphaned_resources(report_data: InventoryReportData) -> OrphanAnalysisResult`

- [ ] **Step 1: Write failing tests for `src/orphan_analyzer.py`**

Crie `tests/test_orphan_analyzer.py` cobrindo:
1. Detecção de volumes EBS como candidatos a órfão com custo de $8.00/mês.
2. Detecção de Elastic IPs soltos com custo de $3.65/mês.
3. Confirmação direta de credenciais de cache (`[CONFIRMADO ÓRFÃO]`) quando clusters na região = 0.
4. Detecção de ALBs ociosos com custo de $22.50/mês e target groups.
5. Snapshots manuais EBS e RDS.
6. Resiliência a inventário vazio (sem erros de chave ou divisão).

```python
from src.models import ResourceRecord, InventoryReportData
from src.orphan_analyzer import analyze_orphaned_resources

def _make_resource(ident, r_type, service, region="ca-central-1", name="-", domain="Aplicação"):
    return ResourceRecord(
        identifier=ident,
        arn=f"arn:aws:{service}:{region}:123456789012:{ident}",
        resource_type=r_type,
        region=region,
        aws_account="123456789012",
        application_raw="-",
        cfn_resource_type="-",
        last_reported_at="2026-10-10",
        service=service,
        tags="0",
        resource_name=name,
        macro_domain=domain
    )

def test_orphan_analyzer_ebs_and_eip():
    vol = _make_resource("vol-0123456789abcdef0", "ec2:volume", "ec2")
    eip = _make_resource("18.230.1.2", "ec2:elastic-ip", "ec2")
    data = InventoryReportData(
        account_id="123456789012",
        generated_at="2026-11-10",
        all_resources=[vol, eip],
        applications={},
        unmapped_resources=[],
        governance_resources=[],
        regions={"ca-central-1": 2},
        services={"ec2": 2}
    )

    result = analyze_orphaned_resources(data)
    assert result.total_candidates == 2
    assert result.total_estimated_monthly_waste_usd == 8.0 + 3.65
    assert len(result.categories_breakdown["Armazenamento"]) == 1
    assert len(result.categories_breakdown["Rede"]) == 1
    assert result.categories_breakdown["Armazenamento"][0].status == "[CANDIDATO A ÓRFÃO]"
    assert any(pb.playbook_id == "pb-orphan-ebs-volumes" for pb in result.playbooks)
    assert any(pb.playbook_id == "pb-orphan-elastic-ips" for pb in result.playbooks)

def test_orphan_analyzer_cache_confirmed_orphan():
    cache_user = _make_resource("user-teste", "memorydb:user", "memorydb", region="sa-east-1")
    data = InventoryReportData(
        account_id="123456789012",
        generated_at="2026-11-10",
        all_resources=[cache_user],
        applications={},
        unmapped_resources=[],
        governance_resources=[],
        regions={"sa-east-1": 1},
        services={"memorydb": 1}
    )

    result = analyze_orphaned_resources(data)
    cache_items = result.categories_breakdown["Cache & Dados In-Memory"]
    assert len(cache_items) == 1
    assert cache_items[0].status == "[CONFIRMADO ÓRFÃO]"
    assert result.confirmed_orphans_count == 1

def test_orphan_analyzer_empty_inventory():
    data = InventoryReportData(
        account_id="123456789012",
        generated_at="2026-11-10",
        all_resources=[],
        applications={},
        unmapped_resources=[],
        governance_resources=[],
        regions={},
        services={}
    )
    result = analyze_orphaned_resources(data)
    assert result.total_candidates == 0
    assert result.total_estimated_monthly_waste_usd == 0.0
    assert result.confirmed_orphans_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orphan_analyzer.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.orphan_analyzer'`

- [ ] **Step 3: Implement `src/orphan_analyzer.py`**

Crie `src/orphan_analyzer.py` implementando a análise para os 5 domínios:
1. `Armazenamento`: `ec2:volume` ($8.00), `ec2:snapshot` ($2.50), `rds:snapshot` ($5.00).
2. `Rede & Conectividade`: `ec2:elastic-ip` ($3.65), `ec2:network-interface` ($0.0), `ec2:security-group` ($0.0, exceto se identificador for `default` ou nome `default`).
3. `Balanceamento de Carga`: `elasticloadbalancing:loadbalancer` ou `elasticloadbalancing:loadbalancer/app` ($22.50), `elasticloadbalancing:targetgroup` ($0.0).
4. `Cache & Dados In-Memory`: `elasticache:user`, `memorydb:user`, `memorydb:acl`, `memorydb:parametergroup`. Se na região não existirem clusters (`cluster` em `resource_type`), classifica como `[CONFIRMADO ÓRFÃO]`; caso contrário `[CANDIDATO A ÓRFÃO]`.
5. `Segurança, Logs & Certificados`: `acm:certificate` ($0.0), `logs:log-group` ($1.50).

Gere os `OrphanPlaybookGuide` correspondentes populando os IDs dos recursos identificados e comandos de inspeção + remoção segura.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orphan_analyzer.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/orphan_analyzer.py tests/test_orphan_analyzer.py
git commit -m "feat(orphan_analyzer): implement orphan resources detection engine and playbooks"
```

---

### Task 3: Orphan Markdown Report Exporter

**Files:**
- Create: `src/exporters/orphan_report.py`
- Create: `tests/test_orphan_report_exporter.py`

**Interfaces:**
- Consumes: `OrphanAnalysisResult`, `OrphanCandidate`, `OrphanPlaybookGuide`
- Produces: `export_orphan_report_markdown(analysis: OrphanAnalysisResult, output_path: str) -> None`

- [ ] **Step 1: Write failing tests for `src/exporters/orphan_report.py`**

Crie `tests/test_orphan_report_exporter.py`:

```python
import os
import tempfile
from src.models import OrphanAnalysisResult, OrphanCandidate, OrphanPlaybookGuide
from src.exporters.orphan_report import export_orphan_report_markdown

def test_export_orphan_report_markdown(tmp_path):
    output_file = tmp_path / "relatorio_recursos_orfaos_123456789012.md"
    
    cand = OrphanCandidate(
        category="Armazenamento",
        resource_type="ec2:volume",
        resource_identifier="vol-123456",
        resource_name="DataDisk",
        region="ca-central-1",
        status="[CANDIDATO A ÓRFÃO]",
        confidence_rationale="Volume listado sem validação de anexo",
        estimated_monthly_waste_usd=8.0,
        playbook_id="pb-orphan-ebs-volumes"
    )
    pb = OrphanPlaybookGuide(
        playbook_id="pb-orphan-ebs-volumes",
        title="Playbook 1: Auditoria de Volumes EBS Desanexados",
        category="Armazenamento",
        target_resources=["vol-123456"],
        inspection_console_path="EC2 > Volumes",
        inspection_cli_command="aws ec2 describe-volumes --filters Name=status,Values=available",
        decision_criteria="Se status available e sem tag de retenção",
        safe_cleanup_cli_command="aws ec2 delete-volume --volume-id vol-123456",
        safety_recommendation="Efetuar snapshot antes de deletar"
    )
    result = OrphanAnalysisResult(
        account_id="123456789012",
        total_candidates=1,
        confirmed_orphans_count=0,
        potential_orphans_count=1,
        total_estimated_monthly_waste_usd=8.0,
        categories_breakdown={"Armazenamento": [cand]},
        playbooks=[pb]
    )

    export_orphan_report_markdown(result, str(output_file))

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "# Relatório Executivo de Identificação de Recursos Órfãos" in content
    assert "123456789012" in content
    assert "~$8.00 USD/mês" in content
    assert "vol-123456" in content
    assert "pb-orphan-ebs-volumes" in content
    assert "```bash" in content
    assert "aws ec2 describe-volumes" in content
    assert "aws ec2 delete-volume" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orphan_report_exporter.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.exporters.orphan_report'`

- [ ] **Step 3: Implement `src/exporters/orphan_report.py`**

Crie `src/exporters/orphan_report.py` com:
1. `_format_category_table(candidates: List[OrphanCandidate]) -> str`
2. `export_orphan_report_markdown(analysis: OrphanAnalysisResult, output_path: str) -> None`
3. Renderização do Scorecard Executivo de Desperdício, Matriz de Priorização, Seções de Categoria e Playbooks com ancoragem (`<a id="..."></a>`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orphan_report_exporter.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/exporters/orphan_report.py tests/test_orphan_report_exporter.py
git commit -m "feat(exporters): implement orphan report markdown generator"
```

---

### Task 4: CLI Pipeline Integration & End-to-End Test

**Files:**
- Modify: `src/main.py:50-95`
- Modify: `tests/test_e2e.py`

**Interfaces:**
- Consumes: `analyze_orphaned_resources`, `export_orphan_report_markdown`
- Produces: `relatorio_recursos_orfaos_<conta>.md` in `output_dir` during `python -m src.main`

- [ ] **Step 1: Write failing test in `tests/test_e2e.py`**

Adicione verificação no teste E2E existente para checar a geração de `relatorio_recursos_orfaos_807445251352.md`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_e2e.py -v`  
Expected: FAIL (file does not exist yet)

- [ ] **Step 3: Integrate in `src/main.py`**

Em `src/main.py`, importe `analyze_orphaned_resources` e `export_orphan_report_markdown`.
Após a geração do relatório de FinOps, execute a análise de órfãos e exporte `output/relatorio_recursos_orfaos_<conta>.md`. Imprima no terminal a mensagem de sucesso correspondente.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_e2e.py -v`  
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest -v`  
Expected: All tests pass (100% passing)

- [ ] **Step 6: Commit**

```bash
git add src/main.py tests/test_e2e.py
git commit -m "feat(main): integrate orphan resources report into CLI pipeline"
```

---

### Task 5: Document Feature in README.md & Final Verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Documentation requirements from spec
- Produces: Updated and clear `README.md` with orphan detection guide

- [ ] **Step 1: Update `README.md`**

Adicione uma seção estruturada no `README.md` contendo:
- Descrição da nova funcionalidade: Identificação de Recursos Órfãos e Playbooks de Limpeza Segura.
- Os 4 relatórios gerados pelo pipeline (Excel, Markdown Técnico, FinOps e Recursos Órfãos).
- Os 5 domínios auditados (Armazenamento, Rede, Balanceamento, Cache, Segurança).
- Explicação dos status `[CONFIRMADO ÓRFÃO]` e `[CANDIDATO A ÓRFÃO]`.
- Exemplo do playbook de validação e descarte com AWS CLI.

- [ ] **Step 2: Run complete CLI on `contas/multicanais-dev` to generate real output**

Execute:
```bash
python -m src.main --input-dir contas/multicanais-dev --output-dir output
```
Verifique se `output/relatorio_recursos_orfaos_807445251352.md` foi gerado perfeitamente.

- [ ] **Step 3: Run full pytest suite**

Run: `python -m pytest -v`  
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document orphan resources detector feature in README"
```
