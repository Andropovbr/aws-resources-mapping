import re
from typing import List
from src.models import ResourceRecord

TEST_KEYWORDS = [r"teste", r"test\b", r"temp", r"dummy", r"sample"]

def evaluate_finops_rules(resources: List[ResourceRecord]) -> List[ResourceRecord]:
    for rec in resources:
        ident_lower = rec.identifier.lower()
        res_type_lower = rec.resource_type.lower()
        cfn_type_lower = rec.cfn_resource_type.lower()
        svc_lower = rec.service.lower()
        
        # 1. Governança
        if rec.macro_domain == "Governança":
            rec.finops_suggestion = "Manter (Governança)"
            rec.finops_cost_impact = "Baixo/Zero"
            rec.finops_rationale = "Recurso mandatório de baseline, segurança ou governança corporativa da organização."
            continue

        # 2. Testes / Temporários
        is_test = any(re.search(pat, ident_lower) for pat in TEST_KEYWORDS)
        if is_test:
            rec.finops_suggestion = "Investigar (Possível Teste / Temporário)"
            rec.finops_cost_impact = "Alto" if svc_lower in ("elasticloadbalancing", "ec2", "rds") else ("Médio" if svc_lower == "s3" else "Baixo/Zero")
            rec.finops_rationale = "Nome do recurso indica criação pontual para teste/validação; verificar se o teste já foi finalizado para exclusão."
            continue

        # 3. ALBs / Load Balancers em dev
        if "loadbalancer" in res_type_lower or "loadbalancer" in cfn_type_lower:
            rec.finops_suggestion = "Investigar (Possível Órfão / Ocioso)"
            rec.finops_cost_impact = "Alto"
            rec.finops_rationale = (
                "ALB identificado em ambiente dev. Na AWS, cada ALB custa ~$20-$25/mês fixo. "
                "Avaliar se possui tráfego real ou se pode ser consolidado via regras de rota num ALB compartilhado."
            )
            continue

        # 4. Elastic IPs
        if "elastic-ip" in res_type_lower or "eip" in cfn_type_lower:
            rec.finops_suggestion = "Investigar (Possível Órfão / Ocioso)"
            rec.finops_cost_impact = "Médio"
            rec.finops_rationale = (
                "Elastic IP alocado. EIPs desassociados de instâncias ativas sofrem cobrança contínua por hora. "
                "Validar se está acoplado a uma instância rodando."
            )
            continue

        # 5. Snapshots e AMIs
        if res_type_lower in ("ec2:snapshot", "ec2:image"):
            rec.finops_suggestion = "Investigar (Possível Órfão / Ocioso)"
            rec.finops_cost_impact = "Médio"
            rec.finops_rationale = "Snapshots e AMIs acumulam custos de armazenamento EBS; validar necessidade de retenção."
            continue

        # 6. Usuários e grupos de cache sem cluster
        if svc_lower in ("memorydb", "elasticache") and res_type_lower != "cluster":
            rec.finops_suggestion = "Investigar (Possível Órfão / Ocioso)"
            rec.finops_cost_impact = "Baixo/Zero"
            rec.finops_rationale = "Configuração ou usuário residual de banco em memória sem cluster ativo associado."
            continue

        # 7. Cargas em Operação padrão
        if rec.macro_domain == "Aplicação":
            rec.finops_suggestion = "Manter (Em Operação)"
            rec.finops_cost_impact = "Alto" if svc_lower in ("rds", "ec2") else "Médio"
            rec.finops_rationale = "Componente associado a uma aplicação ativa identificada no mapeamento topológico."
        else:
            rec.finops_suggestion = "Manter (Em Operação)"
            rec.finops_cost_impact = "Baixo/Zero"
            rec.finops_rationale = "Recurso de infraestrutura compartilhada (ex.: VPC, rede, DNS ou chave KMS)."

    return resources
