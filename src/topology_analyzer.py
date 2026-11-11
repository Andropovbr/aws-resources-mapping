import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from src.models import (
    ResourceRecord,
    TopologyComponent,
    ComponentConnection,
    ApplicationTopology,
    TopologyAnalysisResult,
    InventoryReportData
)

LAYER_INGRESS = "Ingresso & Endpoints"
LAYER_COMPUTE = "Computação & Lógica"
LAYER_MESSAGING = "Mensageria & Filas"
LAYER_DATABASE = "Banco de Dados & Cache"
LAYER_STORAGE = "Armazenamento & Apoio"

def load_application_catalog(catalog_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Carrega o catálogo declarativo de aplicações e governança.
    Busca no caminho fornecido ou em catalog/applications.json e applications.json.
    """
    candidates = []
    if catalog_path:
        candidates.append(Path(catalog_path))
    else:
        candidates.append(Path.cwd() / "catalog" / "applications.json")
        candidates.append(Path.cwd() / "applications.json")
        candidates.append(Path(__file__).resolve().parent.parent / "catalog" / "applications.json")

    for path in candidates:
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "applications" in data:
                        return data["applications"]
                    elif isinstance(data, dict):
                        return data
            except Exception:
                continue

    return {}

def classify_layer(record: ResourceRecord) -> str:
    """
    Determina a camada funcional do componente com base no serviço AWS e tipos de recurso.
    """
    svc = (record.service or "").lower()
    res_type = (record.resource_type or "").lower()
    cfn_type = (record.cfn_resource_type or "").lower()
    ident = (record.identifier or "").lower()

    # 1. Ingresso & Endpoints
    if (
        "loadbalancer" in res_type
        or "loadbalancer" in cfn_type
        or "targetgroup" in res_type
        or "targetgroup" in cfn_type
        or svc in ("elasticloadbalancing", "apigateway", "cloudfront", "route53")
    ):
        return LAYER_INGRESS

    # 2. Computação & Lógica
    if (
        svc == "lambda"
        or (svc == "ec2" and ("instance" in res_type or "instance" in cfn_type or ident.startswith("i-")))
        or svc in ("ecs", "elasticbeanstalk")
    ):
        return LAYER_COMPUTE

    # 3. Mensageria & Filas
    if svc in ("sqs", "sns") or "event" in svc or "events" in res_type:
        return LAYER_MESSAGING

    # 4. Banco de Dados & Cache
    if (
        svc in ("rds", "dynamodb", "elasticache", "memorydb", "docdb")
        or "cluster" in res_type
        or "dbinstance" in cfn_type
    ):
        return LAYER_DATABASE

    # 5. Armazenamento & Apoio
    if svc in ("s3", "secretsmanager", "efs", "fsx"):
        return LAYER_STORAGE

    # Fallback por serviço
    if svc in ("ec2", "autoscaling"):
        return LAYER_COMPUTE

    return LAYER_STORAGE

def resolve_ownership(
    record: ResourceRecord,
    catalog: Dict[str, Dict[str, Any]],
    inferred_app: str = ""
) -> Tuple[str, Optional[str], str]:
    """
    Determina a Squad, Tech Lead/Owner e Nível de Criticidade seguindo a precedência:
    1. Catálogo Declarativo (match patterns)
    2. Tags nativas do CSV
    3. Mapeamento por inferência de cluster / slug
    4. Fallback padrão
    """
    r_id = record.identifier or ""
    r_arn = record.arn or ""
    r_tags = record.tags or ""
    r_app_raw = record.application_raw or ""
    target_str = f"{r_id} {r_arn} {r_tags} {r_app_raw}".lower()

    # 1. Catálogo Declarativo
    for app_id, app_info in catalog.items():
        patterns = app_info.get("match_patterns", [])
        for pat in patterns:
            if pat and pat.lower() in target_str:
                return (
                    app_info.get("squad", "Squad A Definir"),
                    app_info.get("owner"),
                    app_info.get("criticality", "Padrão")
                )

    # 2. Tags do CSV
    tags_lower = r_tags.lower()
    if "squad=" in tags_lower or "team=" in tags_lower:
        match = re.search(r"(?:squad|team)=([^;,\s]+)", tags_lower)
        if match:
            squad_tag = match.group(1).strip()
            return f"Squad {squad_tag.title()}", None, "Padrão"

    # 3. Inferred App / Cluster
    if inferred_app and inferred_app not in ("Não Identificado", "Infraestrutura Compartilhada", "Governança & Segurança"):
        return f"Squad {inferred_app}", None, "Padrão"

    # 4. Fallbacks
    if record.macro_domain == "Governança" or inferred_app == "Governança & Segurança":
        return "Squad Segurança & Governança", None, "Padrão"
    elif record.macro_domain == "Infraestrutura Compartilhada" or inferred_app == "Infraestrutura Compartilhada":
        return "Squad Infraestrutura Cloud", None, "Padrão"

    return "Squad A Definir", None, "Padrão"

def infer_connections(components: List[TopologyComponent], slug: str = "") -> List[ComponentConnection]:
    """
    Infere as dependências diretas e conexões de fluxo entre componentes da aplicação:
    1. Load Balancer -> Target Group
    2. Target Group -> Computação (EC2, ECS, Lambda)
    3. Mensageria (SQS/SNS) -> Computação (Lambda)
    4. Computação -> Bancos de Dados, Cache e Buckets S3
    """
    connections: List[ComponentConnection] = []

    target_groups = [
        c for c in components
        if "targetgroup" in (c.id or "").lower() or "tg-" in (c.id or "").lower()
    ]
    load_balancers = [
        c for c in components
        if c not in target_groups and (
            (c.layer == LAYER_INGRESS and (
                "loadbalancer" in (c.service or "").lower()
                or "elasticloadbalancing" in (c.service or "").lower()
                or "loadbalancer" in (c.id or "").lower()
            ))
            or "alb" in (c.id or "").lower()
            or "nlb" in (c.id or "").lower()
        )
    ]
    compute_nodes = [c for c in components if c.layer == LAYER_COMPUTE]
    messaging_nodes = [c for c in components if c.layer == LAYER_MESSAGING]
    database_nodes = [c for c in components if c.layer == LAYER_DATABASE]
    storage_nodes = [c for c in components if c.layer == LAYER_STORAGE]

    # 1. LB -> Target Group
    for lb in load_balancers:
        for tg in target_groups:
            conn = ComponentConnection(
                source_id=lb.id,
                target_id=tg.id,
                connection_type="Ingress",
                label="Roteia tráfego"
            )
            connections.append(conn)
            if tg.id not in lb.downstream_ids:
                lb.downstream_ids.append(tg.id)
            if lb.id not in tg.upstream_ids:
                tg.upstream_ids.append(lb.id)

    # 2. Target Group -> Compute
    for tg in target_groups:
        for comp in compute_nodes:
            conn = ComponentConnection(
                source_id=tg.id,
                target_id=comp.id,
                connection_type="Ingress",
                label="Encaminha para target"
            )
            connections.append(conn)
            if comp.id not in tg.downstream_ids:
                tg.downstream_ids.append(comp.id)
            if tg.id not in comp.upstream_ids:
                comp.upstream_ids.append(tg.id)

    # Fallback se não houver Target Group explícito: LB -> Compute diretamente
    if load_balancers and not target_groups:
        for lb in load_balancers:
            for comp in compute_nodes:
                conn = ComponentConnection(
                    source_id=lb.id,
                    target_id=comp.id,
                    connection_type="Ingress",
                    label="Roteia tráfego"
                )
                connections.append(conn)
                if comp.id not in lb.downstream_ids:
                    lb.downstream_ids.append(comp.id)
                if lb.id not in comp.upstream_ids:
                    comp.upstream_ids.append(lb.id)

    # 3. Mensageria -> Compute
    for msg in messaging_nodes:
        for comp in compute_nodes:
            conn = ComponentConnection(
                source_id=msg.id,
                target_id=comp.id,
                connection_type="EventTrigger",
                label="Aciona processamento"
            )
            connections.append(conn)
            if comp.id not in msg.downstream_ids:
                msg.downstream_ids.append(comp.id)
            if msg.id not in comp.upstream_ids:
                comp.upstream_ids.append(msg.id)

    # 4. Compute -> Databases
    for comp in compute_nodes:
        for db in database_nodes:
            conn = ComponentConnection(
                source_id=comp.id,
                target_id=db.id,
                connection_type="DataAccess",
                label="Persiste dados"
            )
            connections.append(conn)
            if db.id not in comp.downstream_ids:
                comp.downstream_ids.append(db.id)
            if comp.id not in db.upstream_ids:
                db.upstream_ids.append(comp.id)

    # 5. Compute -> Storage
    for comp in compute_nodes:
        for st in storage_nodes:
            conn = ComponentConnection(
                source_id=comp.id,
                target_id=st.id,
                connection_type="DataAccess",
                label="Lê/Grava objetos"
            )
            connections.append(conn)
            if st.id not in comp.downstream_ids:
                comp.downstream_ids.append(st.id)
            if comp.id not in st.upstream_ids:
                st.upstream_ids.append(comp.id)

    return connections

def analyze_application_topology(
    report_data: InventoryReportData,
    catalog_path: Optional[str] = None
) -> TopologyAnalysisResult:
    """
    Executa a análise arquitetural completa do inventário:
    - Agrupa por aplicação
    - Classifica componentes em camadas
    - Atribui governança e ownership
    - Infere dependências
    - Consolida métricas gerais
    """
    catalog = load_application_catalog(catalog_path)
    all_components: List[TopologyComponent] = []
    applications: List[ApplicationTopology] = []
    shared_infra: List[TopologyComponent] = []
    unassigned: List[TopologyComponent] = []

    # Cria índice rápido de recursos pertencentes a clusters de aplicações
    cluster_resource_map: Dict[str, str] = {}
    for cl in report_data.clusters:
        for r in cl.resources:
            r_id = r.identifier or ""
            if r_id:
                cluster_resource_map[r_id] = cl.name

    for rec in report_data.all_resources:
        rec_id = rec.identifier or ""
        inferred_app = cluster_resource_map.get(rec_id, rec.inferred_app or "")
        layer = classify_layer(rec)
        squad, owner, crit = resolve_ownership(rec, catalog, inferred_app=inferred_app)

        r_name = rec.resource_name or ""
        comp_name = r_name if r_name and r_name != "-" else rec_id

        comp = TopologyComponent(
            id=rec_id,
            name=comp_name,
            service=rec.service or "",
            layer=layer,
            arn=rec.arn or "",
            region=rec.region or "",
            squad=squad,
            owner=owner,
            criticality=crit
        )

        if rec.macro_domain == "Infraestrutura Compartilhada" or inferred_app == "Infraestrutura Compartilhada":
            shared_infra.append(comp)
        elif rec.macro_domain == "Governança" or inferred_app == "Governança & Segurança":
            shared_infra.append(comp)
        elif inferred_app in ("Não Identificado", "A Classificar") and squad == "Squad A Definir":
            unassigned.append(comp)
        else:
            all_components.append(comp)

    # Agrupa componentes por aplicação a partir dos clusters
    for cl in report_data.clusters:
        cl_comps = [c for c in all_components if cluster_resource_map.get(c.id) == cl.name]
        if not cl_comps:
            continue

        # Metadados de aplicação
        app_squad = cl_comps[0].squad if cl_comps else "Squad A Definir"
        app_owner = cl_comps[0].owner if cl_comps else None
        app_crit = cl_comps[0].criticality if cl_comps else "Padrão"
        app_desc = f"Aplicação {cl.name} sustentada na infraestrutura AWS"

        # Se houver catálogo correspondente
        for app_info in catalog.values():
            if app_info.get("name") == cl.name:
                app_squad = app_info.get("squad", app_squad)
                app_owner = app_info.get("owner", app_owner)
                app_crit = app_info.get("criticality", app_crit)
                app_desc = app_info.get("description", app_desc)
                break

        # Infere conexões
        connections = infer_connections(cl_comps, slug=cl.slug)

        app_topo = ApplicationTopology(
            app_name=cl.name,
            slug=cl.slug,
            squad=app_squad,
            owner=app_owner,
            criticality=app_crit,
            description=app_desc,
            components=cl_comps,
            connections=connections
        )
        applications.append(app_topo)

    # Distribuições
    squad_dist: Dict[str, int] = {}
    layer_dist: Dict[str, int] = {}

    for c in all_components:
        squad_dist[c.squad] = squad_dist.get(c.squad, 0) + 1
        layer_dist[c.layer] = layer_dist.get(c.layer, 0) + 1

    total_conns = sum(len(app.connections) for app in applications)
    assigned_squads = len(set(c.squad for c in all_components if c.squad and c.squad != "Squad A Definir"))

    return TopologyAnalysisResult(
        account_id=report_data.account_id,
        account_name=report_data.account_name,
        account_display=report_data.account_display,
        total_applications=len(applications),
        total_components=len(all_components),
        total_connections=total_conns,
        assigned_squads_count=assigned_squads,
        squad_distribution=squad_dist,
        layer_distribution=layer_dist,
        applications=applications,
        shared_infrastructure=shared_infra,
        unassigned_components=unassigned
    )
