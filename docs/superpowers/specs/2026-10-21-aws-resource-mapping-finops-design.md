# Especificação de Design: Pipeline de Inventário AWS, Mapeamento de Aplicações e Recomendações FinOps

**Data:** 2026-10-21  
**Autor:** Antigravity (com aprovação do usuário)  
**Ambiente Inicial:** `multicanais-dev` (Conta AWS `807445251352`)  
**Status:** Validado e Aprovado

---

## 1. Visão Geral e Contexto

Em ambientes de nuvem em crescimento, a defasagem entre a infraestrutura provisionada e a documentação técnica gera riscos operacionais e custos desnecessários. Na conta `multicanais-dev`, foram exportados 19 arquivos CSV contendo o inventário de recursos reportados pela AWS. Devido ao limite de 1.000 itens do AWS Resource Groups / Tag Editor, o arquivo geral `resources.csv` está truncado, exigindo a unificação com exportações regionais (`resources sa-east.csv`) e arquivos específicos de serviço (ex.: `ec2.csv`, `elasticloadbalancing.csv`, `rds.csv`, `cloudformation.csv`).

Adicionalmente, uma frente de FinOps está em andamento para auditar os recursos, identificar possíveis custos ociosos/zumbis e determinar o que deve ser mantido versus descartado.

Este projeto estabelece uma ferramenta em Python modular, extensível e 100% reutilizável para outras contas AWS que processe esses CSVs sem necessidade de documentação prévia, correlacione as aplicações em execução em computação (EC2) e produza relatórios em Excel (`.xlsx`) e Markdown (`.md`) com sugestões consultivas de FinOps.

---

## 2. Objetivos e Requisitos

### 2.1 Requisitos Funcionais
1. **Ingestão e Desduplicação Automática:**
   - Ler dinamicamente todos os arquivos `*.csv` de um diretório de entrada (`--input-dir`).
   - Normalizar encodings (`UTF-8`, `UTF-8-SIG`, `ISO-8859-1`) e delimitadores.
   - Desduplicar registros utilizando o `ARN` canônico como chave primária (com fallback para `Serviço:Tipo:Região:Identificador`).
   - Consolidar metadados mais recentes (`LastReportedAt`) e registrar a lista de arquivos de origem onde o recurso foi encontrado.
2. **Segregação de Governança Corporativa:**
   - Detectar e isolar automaticamente componentes de conformidade e segurança da organização (AWS Control Tower, AWS Config, Security Hub, Prisma Cloud, CrowdStrike, IAM básico, SSM documents padrão).
   - Manter esses recursos em aba própria para não sobrecarregar as equipes de produto.
3. **Inferência Automática de Aplicações (100% Automática):**
   - Agrupar recursos por proximidade semântica de nomes, prefixos, sufixos e relações topológicas diretas.
   - Mapear a topologia de entrada: Application Load Balancers (ALBs) ➔ Listeners ➔ Target Groups ➔ Instâncias EC2 ➔ Bancos RDS / Subnet Groups ➔ SecretsManager.
   - Detectar clusters de aplicação (ex.: `Canais Digitais`, `WordPress / Blog`, `Docker-dev`, `VDO / Promoção Digital`, `Elastic Beanstalk / Legado`).
4. **Mapeamento de Cargas de Computação (EC2):**
   - Identificar instâncias EC2 ativas, Security Groups, ENIs e Key Pairs.
   - Diagnosticar o relacionamento entre instâncias de computação e os Load Balancers / Target Groups configurados.
5. **Motor de Regras FinOps Consultivas:**
   - Avaliar recursos contra regras de custo e ociosidade.
   - Rotular cada recurso com `Sugestão FinOps`:
     - `Manter (Governança)`
     - `Manter (Em Operação)`
     - `Investigar (Possível Órfão / Ocioso)`
     - `Investigar (Possível Teste / Temporário)`
   - Gerar `Justificativa da Sugestão` contextualizada.
   - Disponibilizar colunas interativas para o time: `Decisão do Time`, `Responsável`, `Observações`.
6. **Exportação de Múltiplos Entregáveis:**
   - **Planilha Excel (`.xlsx`):** Formatada, com filtros automáticos, largura de colunas ajustada e abas temáticas.
   - **Relatório Markdown (`.md`):** Sumário executivo, tabela de topologia, destaques de custos e guia de ação.

### 2.2 Requisitos Não-Funcionais
- **Portabilidade:** Executar em Python 3.10+ (testado em Python 3.15) no Windows/Linux/macOS sem dependências de banco de dados externo ou AWS CLI instalado.
- **Independência de Acesso:** Operar offline usando apenas os arquivos CSV fornecidos.
- **Reutilização:** Suportar qualquer conta AWS exportada no mesmo formato apenas alterando o diretório de entrada.
- **Testabilidade:** Cobertura de testes unitários com `pytest` para ingestão, correlação, FinOps e exportadores.

---

## 3. Arquitetura do Sistema e Estrutura de Módulos

### 3.1 Estrutura de Diretórios
```
resources multicanais-dev/
├── src/
│   ├── __init__.py
│   ├── main.py              # CLI entrypoint (argparse, pipeline orchestration)
│   ├── models.py            # Dataclasses de dados (ResourceRecord, AppCluster, FinOpsRecord)
│   ├── ingestion.py         # Leitura de CSVs, sanitização e deduplicação canônica
│   ├── correlator.py        # Extração de tokens, agrupamento de apps e topologia
│   ├── finops.py            # Motor de regras e heurísticas de sugestão FinOps
│   └── exporters/
│       ├── __init__.py
│       ├── excel.py         # Geração de pasta de trabalho openpyxl com abas especializadas
│       └── markdown.py      # Geração de relatório executivo em Markdown
├── tests/
│   ├── test_ingestion.py
│   ├── test_correlator.py
│   ├── test_finops.py
│   └── test_exporters.py
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-10-21-aws-resource-mapping-finops-design.md
```

### 3.2 Modelos de Dados (`src/models.py`)

- **`ResourceRecord`**:
  - `identifier: str`
  - `arn: str`
  - `resource_type: str`
  - `region: str`
  - `aws_account: str`
  - `application_raw: str`
  - `cfn_resource_type: str`
  - `last_reported_at: str`
  - `service: str`
  - `tags: str`
  - `source_files: list[str]`
  - `macro_domain: str` ("Governança", "Aplicação", "Infraestrutura Compartilhada")
  - `inferred_app: str` (ex.: "Canais Digitais", "WordPress", "Desconhecido")
  - `finops_suggestion: str`
  - `finops_cost_impact: str` ("Alto", "Médio", "Baixo/Zero")
  - `finops_rationale: str`

- **`ApplicationCluster`**:
  - `name: str`
  - `slug: str`
  - `resources: list[ResourceRecord]`
  - `compute_instances: list[str]`
  - `load_balancers: list[str]`
  - `target_groups: list[str]`
  - `databases: list[str]`
  - `secrets: list[str]`
  - `storage_buckets: list[str]`

---

## 4. Detalhamento dos Componentes

### 4.1 Ingestão e Deduplicação Canônica (`src/ingestion.py`)
1. Localiza todos os arquivos com extensão `.csv` em `--input-dir`.
2. Para cada arquivo, abre em modo texto com decodificação resiliente (`utf-8-sig` com fallback para `latin-1`).
3. Mapeia cabeçalhos esperados: `Identificador`, `ARN`, `Tipo de recurso`, `Região`, `Conta da AWS`, `Aplicação`, `CfnResourceType`, `LastReportedAt`, `Serviço`, `Tags`.
4. Utiliza o `ARN` canônico como chave primária.
5. Em caso de colisão de ARN:
   - Mantém o registro com `LastReportedAt` mais recente.
   - Concatena os nomes dos arquivos de origem no campo `source_files`.
   - Se um arquivo específico possuir dados de tags ou tipo mais detalhados que o arquivo geral de 1.000 itens, preenche as lacunas.

### 4.2 Classificação de Domínio e Correlação (`src/correlator.py`)
1. **Regras de Governança e Segurança:**
   - Padrões de identificador e ARN:
     - `StackSet-AWSControlTower.*`, `aws-controltower-.*`
     - `aws-service-rule/fms.amazonaws.com.*`, `config-rule-.*`
     - `StackSet-SH-.*`, `aws-service-rule/securityhub.*`
     - `StackSet-PrismaCloud.*`
     - `crowdstrike-cs-horizon.*`, `/CrowdStrike/.*`
     - `StackSet-VisionOne.*`
     - `StackSet-AWS-QuickSetup.*`, `aws-quicksetup-.*`
     - SSM Documents (`AWS-.*`, `Amazon.*`)
     - IAM Roles de serviço (`AWSServiceRole.*`)
   - Se atender aos padrões, define `macro_domain = "Governança"`.
2. **Extração de Tokens e Agrupamento de Aplicações:**
   - Analisa nomes de ALBs, Target Groups, Bancos e Secrets.
   - Aplica normalização de tokens (lowercase, remoção de prefixos `arn:...`, `app/`, `tg-`, `alb-`).
   - Clusters automáticos mapeados:
     - **Canais Digitais:** Recursos contendo `canais-dig`, `canaisdb`, `multicanais`.
     - **WordPress / Blog:** Recursos contendo `wordpress`, `blog`.
     - **Docker-dev:** Recursos contendo `docker-dev`.
     - **VDO & Promoção Digital:** Recursos contendo `vdo`, `promodigit` ou `promo-digital`.
     - **Elastic Beanstalk:** Recursos contendo `elasticbeanstalk`.
     - **Geral / Não Atribuído:** Recursos que não casam com nenhum cluster conhecido.
3. **Mapeamento de Topologia e Computação:**
   - Relaciona Load Balancers aos Target Groups e aos certificados ACM utilizados.
   - Relaciona o banco de dados `canaisdb-02` aos Secrets de conexão (`canais-db-01`, `canais-db-02`).
   - Destaca as 2 instâncias EC2 (`i-090d9b01ccf2af5ae`, `i-00899c1d967f6812a`), apontando que sustentam múltiplos serviços ou que há ALBs excedentes sem targets.

### 4.3 Motor de Heurísticas FinOps (`src/finops.py`)
Classifica cada recurso com base em regras determinísticas:

1. **Governança:**
   - Condição: `macro_domain == "Governança"`.
   - `finops_suggestion`: `Manter (Governança)`
   - `finops_cost_impact`: `Baixo/Zero` (a maioria das regras são gratuitas ou de custo irrisório de compliance).
   - `finops_rationale`: "Recurso obrigatório de baseline, segurança ou governança corporativa da organização."

2. **Recursos de Teste / Temporários:**
   - Condição: Nome contém `teste`, `test`, `temp`, `dummy` (ex.: bucket `teste123canais`, bucket `inventario-fullaws-teste`).
   - `finops_suggestion`: `Investigar (Possível Teste / Temporário)`
   - `finops_cost_impact`: `Médio`
   - `finops_rationale`: "Nome do recurso indica criação pontual para teste/validação; verificar se o teste já foi finalizado para exclusão."

3. **Recursos Ociosos / Potencialmente Órfãos:**
   - **ALBs Ociosos em Dev:**
     - Condição: `Serviço == "elasticloadbalancing"` e `CfnResourceType == "AWS::ElasticLoadBalancingV2::LoadBalancer"`.
     - `finops_suggestion`: `Investigar (Possível Órfão / Ocioso)`
     - `finops_cost_impact`: `Alto`
     - `finops_rationale`: "Existem 9 ALBs em ambiente de desenvolvimento para apenas 2 instâncias EC2. Cada ALB custa ~$20-$25/mês fixo. Avaliar se o ALB possui tráfego real ou pode ser consolidado via regras de rota em um ALB único."
   - **Elastic IPs Não Vinculados ou Excedentes:**
     - Condição: `Tipo == "ec2:elastic-ip"`.
     - `finops_suggestion`: `Investigar (Possível Órfão / Ocioso)`
     - `finops_cost_impact`: `Médio`
     - `finops_rationale`: "Existem 4 Elastic IPs alocados para apenas 2 instâncias EC2. EIPs desassociados são cobrados continuamente por hora."
   - **Snapshots e AMIs:**
     - Condição: `Tipo in ("ec2:snapshot", "ec2:image")`.
     - `finops_suggestion`: `Investigar (Possível Órfão / Ocioso)`
     - `finops_cost_impact`: `Médio`
     - `finops_rationale`: "Snapshots e AMIs antigas geram custo contínuo de EBS Storage; validar se a retenção ainda é exigida."
   - **Parameter Groups / Usuários de Cache Órfãos:**
     - Condição: `Serviço in ("memorydb", "elasticache", "neptune")` sem instâncias ou clusters ativos.
     - `finops_suggestion`: `Investigar (Possível Órfão / Ocioso)`
     - `finops_cost_impact`: `Baixo/Zero`
     - `finops_rationale`: "Configurações e usuários residuais de bancos sem clusters ativos provisionados."

4. **Recursos em Operação (Padrão para Cargas Centrais):**
   - Condição: Recursos em uso mapeados nas aplicações centrais (`canaisdb-02`, instâncias EC2, Target Groups ativos).
   - `finops_suggestion`: `Manter (Em Operação)`
   - `finops_cost_impact`: Variável (`Alto` para RDS e EC2).
   - `finops_rationale`: "Componente central em operação associado à aplicação detectada."

---

## 5. Especificação dos Entregáveis

### 5.1 Planilha Excel (`inventario_<conta>.xlsx`)
Desenvolvida usando `openpyxl`:
- **Estilos:** Cabeçalho azul corporativo escuro (`#1F4E79`) com texto branco em negrito; linhas com espaçamento e grade visível.
- **Abas Obrigatórias:**
  1. **`Resumo Executivo`:** Painel com total de recursos únicos, distribuição por região (`ca-central-1`, `sa-east-1`, etc.), distribuição por serviço e gráfico de barras/tabela com a divisão das sugestões FinOps.
  2. **`Aplicações & Compute`:** Matriz das aplicações detectadas, listando recursos, portas, componentes e alertas de topologia.
  3. **`FinOps & Ações do Time`:** Tabela contendo apenas os recursos que necessitam de avaliação humana (`Investigar - Possível Órfão` e `Investigar - Teste`), com as colunas editáveis:
     - `Identificador` | `Serviço` | `Região` | `Sugestão FinOps` | `Impacto Estimado` | `Justificativa` | `Decisão do Time (Manter/Deletar/Em Análise)` | `Responsável` | `Observações`
  4. **`Bancos & Armazenamento`:** RDS, S3, Secrets Manager, ElastiCache, MemoryDB.
  5. **`Governança & Segurança`:** Regras do Config, Control Tower, GuardDuty, Shield, Prisma, Crowdstrike, IAM.
  6. **`Inventário Canônico (Todos)`:** Tabela completa com os 1.902+ recursos consolidados com filtros habilitados em todas as colunas.

### 5.2 Relatório em Markdown (`relatorio_<conta>.md`)
Estrutura:
1. **Sumário Executivo:** Contagem de recursos únicos, conta analisada, distribuição geográfica e principais conclusões.
2. **Mapeamento de Cargas e Computação:** Análise detalhada das 2 instâncias EC2, relação com os 9 ALBs e clusters de aplicação.
3. **Quadro de Oportunidades FinOps:** Tabela consolidada com ações imediatas (quick wins) e potenciais economias estimadas.
4. **Análise de Arquitetura e Riscos:** Avaliação do uso de múltiplas regiões (`ca-central-1` vs `sa-east-1`), ausência de tags nos exports e dependências de governança.
5. **Instruções para Execução em Outras Contas:** Como rodar a ferramenta em novas pastas de exportação.

---

## 6. Estratégia de Testes

A suíte de testes unitários utilizará `pytest` no diretório `tests/`:
1. `tests/test_ingestion.py`:
   - Leitura de diretório com múltiplos arquivos CSV.
   - Deduplicação de itens com mesmo ARN presentes em arquivos gerais e específicos.
   - Tratamento de encodings especiais e arquivos com campos vazios.
2. `tests/test_correlator.py`:
   - Validação do isolamento de recursos de governança (Control Tower, Config, Prisma, CrowdStrike).
   - Extração correta dos clusters de aplicações (`Canais Digitais`, `WordPress`, `Docker-dev`, `VDO`).
3. `tests/test_finops.py`:
   - Classificação correta de ALBs e EIPs como `Investigar (Possível Órfão)`.
   - Identificação de nomes contendo termos de teste como `Investigar (Possível Teste)`.
   - Marcação de recursos corporativos como `Manter (Governança)`.
4. `tests/test_exporters.py`:
   - Verificação da criação do arquivo `.xlsx` com todas as abas e cabeçalhos corretos.
   - Validação da geração do relatório `.md` com sintaxe markdown válida.

---

## 7. Instruções de Execução da Ferramenta

```bash
# Instalação das dependências necessárias
pip install openpyxl pytest

# Execução padrão no diretório atual
python -m src.main --input-dir "./" --output-dir "./output" --account "multicanais-dev"

# Execução dos testes automatizados
pytest tests/ -v
```
