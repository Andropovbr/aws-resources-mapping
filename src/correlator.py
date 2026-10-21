import re
from typing import List, Tuple, Dict
from src.models import ResourceRecord, ApplicationCluster

GOVERNANCE_PATTERNS = [
    r"StackSet-AWSControlTower",
    r"aws-controltower",
    r"aws-service-rule/fms",
    r"aws-service-rule/securityhub",
    r"StackSet-SH-",
    r"StackSet-PrismaCloud",
    r"crowdstrike",
    r"/CrowdStrike/",
    r"StackSet-VisionOne",
    r"StackSet-AWS-QuickSetup",
    r"aws-quicksetup",
    r"StackSet-CustomControlTow",
    r"StackSet-sra-",
    r"StackSet-PSG-",
    r"^AWS-",
    r"^Amazon",
    r"AWSServiceRole",
    r"config-rule-"
]

KNOWN_APP_SLUGS = [
    ("canais-dig", "Canais Digitais"),
    ("canaisdb", "Canais Digitais"),
    ("canais-db", "Canais Digitais"),
    ("canais", "Canais Digitais"),
    ("multicanais", "Canais Digitais"),
    ("wordpress", "WordPress / Blog"),
    ("blog", "WordPress / Blog"),
    ("docker-dev", "Docker-dev"),
    ("promo-digital", "VDO & Promoção Digital"),
    ("promodb", "VDO & Promoção Digital"),
    ("porto-vdo", "VDO & Promoção Digital"),
    ("alb-vdo", "VDO & Promoção Digital"),
    ("ftp-vdo", "VDO & Promoção Digital"),
    ("vdo", "VDO & Promoção Digital"),
    ("elasticbeanstalk", "Elastic Beanstalk / Legado")
]

def _is_governance(record: ResourceRecord) -> bool:
    target_str = f"{record.identifier} {record.arn} {record.service} {record.application_raw}"
    for pat in GOVERNANCE_PATTERNS:
        if re.search(pat, target_str, re.IGNORECASE):
            return True
    if record.service.lower() in ("config", "shield", "servicecatalog") and not any(k[0] in target_str.lower() for k in KNOWN_APP_SLUGS):
        return True
    return False

def _infer_app_name(record: ResourceRecord) -> str:
    target_str = f"{record.identifier} {record.arn} {record.application_raw}".lower()
    for slug, app_name in KNOWN_APP_SLUGS:
        if slug in target_str:
            return app_name
    return "Infraestrutura Compartilhada"

def correlate_and_classify_resources(resources: List[ResourceRecord]) -> Tuple[List[ResourceRecord], List[ApplicationCluster]]:
    cluster_map: Dict[str, ApplicationCluster] = {}

    for rec in resources:
        if _is_governance(rec):
            rec.macro_domain = "Governança"
            rec.inferred_app = "Governança & Segurança"
        else:
            app_name = _infer_app_name(rec)
            rec.inferred_app = app_name
            if app_name != "Infraestrutura Compartilhada":
                rec.macro_domain = "Aplicação"
            else:
                rec.macro_domain = "Infraestrutura Compartilhada"

            if app_name not in ("Infraestrutura Compartilhada", "Governança & Segurança"):
                if app_name not in cluster_map:
                    cluster_map[app_name] = ApplicationCluster(
                        name=app_name,
                        slug=app_name.lower().replace(" / ", "-").replace(" ", "-"),
                        resources=[]
                    )
                cl = cluster_map[app_name]
                cl.resources.append(rec)
                
                # Link compute, load balancers, etc.
                ident = rec.identifier
                res_type = rec.resource_type.lower()
                cfn_type = rec.cfn_resource_type
                svc = rec.service.lower()

                if "instance" in res_type:
                    cl.compute_instances.append(ident)
                elif "loadbalancer" in res_type or "LoadBalancer" in cfn_type:
                    cl.load_balancers.append(ident)
                elif "targetgroup" in res_type or "TargetGroup" in cfn_type:
                    cl.target_groups.append(ident)
                elif svc in ("rds", "memorydb", "elasticache"):
                    cl.databases.append(ident)
                elif svc == "secretsmanager":
                    cl.secrets.append(ident)
                elif svc == "s3":
                    cl.storage_buckets.append(ident)

    return resources, list(cluster_map.values())
