import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Union

@dataclass
class AccountInfo:
    account_id: str
    account_name: Optional[str] = None

    @property
    def display_title(self) -> str:
        if self.account_name and self.account_name != self.account_id:
            return f"Conta {self.account_name} ({self.account_id})"
        return f"Conta {self.account_id}"

    @property
    def file_slug(self) -> str:
        name = self.account_name if self.account_name else self.account_id
        return re.sub(r'[^\w\-.]', '_', name)

def load_account_mappings(config_path: Optional[Union[str, Path]] = None) -> Dict[str, str]:
    """
    Carrega o mapeamento de ID da conta -> Nome da conta a partir de um arquivo JSON.
    Se não informado, busca accounts.json no diretório de trabalho atual ou na raiz do projeto.
    """
    candidates = []
    if config_path:
        candidates.append(Path(config_path))
    else:
        candidates.append(Path.cwd() / "accounts.json")
        candidates.append(Path(__file__).resolve().parent.parent / "accounts.json")

    for path in candidates:
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return {str(k).strip(): str(v).strip() for k, v in data.items()}
            except Exception:
                continue

    return {}

def resolve_account_info(
    account_arg: str = "",
    raw_account_id: str = "",
    input_dir: str = "",
    config_path: Optional[Union[str, Path]] = None
) -> AccountInfo:
    """
    Resolve com segurança o ID e o Nome Amigável da conta AWS com base em:
    1. accounts.json (lookup por ID ou Nome)
    2. Parâmetro explícito (--account)
    3. Inferência de diretório de entrada (ex: contas/multicanais-dev)
    4. ID numérico bruto extraído dos dados
    """
    id_to_name = load_account_mappings(config_path)
    name_to_id = {v: k for k, v in id_to_name.items()}

    account_arg = (account_arg or "").strip()
    raw_account_id = (raw_account_id or "").strip()

    # 1. Se account_arg foi fornecido explicitamente
    if account_arg:
        if account_arg in id_to_name:
            return AccountInfo(account_id=account_arg, account_name=id_to_name[account_arg])
        if account_arg in name_to_id:
            return AccountInfo(account_id=name_to_id[account_arg], account_name=account_arg)
        
        # Se for numérico, assume como account_id sem nome mapeado
        if account_arg.isdigit():
            return AccountInfo(account_id=account_arg, account_name=None)
        
        # Se for nome amigável não mapeado no json
        if raw_account_id and raw_account_id.isdigit():
            return AccountInfo(account_id=raw_account_id, account_name=account_arg)
        return AccountInfo(account_id=account_arg, account_name=account_arg)

    # 2. Se account_arg não foi fornecido, verificar raw_account_id no accounts.json
    if raw_account_id and raw_account_id in id_to_name:
        return AccountInfo(account_id=raw_account_id, account_name=id_to_name[raw_account_id])

    # 3. Inferência através do input_dir (ex: contas/multicanais-dev)
    if input_dir:
        input_path = Path(input_dir).resolve()
        folder_name = input_path.name
        parent_name = input_path.parent.name.lower()

        if folder_name in name_to_id:
            return AccountInfo(
                account_id=name_to_id[folder_name],
                account_name=folder_name
            )

        if parent_name in ("contas", "accounts") and folder_name not in (".", ""):
            return AccountInfo(
                account_id=raw_account_id or folder_name,
                account_name=folder_name
            )

    # 4. Fallback padrão
    fallback_id = raw_account_id or "aws-account"
    return AccountInfo(account_id=fallback_id, account_name=None)
