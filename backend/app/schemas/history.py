from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class HistoryOut(BaseModel):
    id: int
    switch_id: Optional[int] = None
    switch_name: str = ""
    switch_ip: str = ""
    scan_log_id: Optional[int] = None
    change_type: str
    ip_address: str
    mac_address: str
    old_vlan_bd: Optional[int] = None
    new_vlan_bd: Optional[int] = None
    old_vlan_type: str = ""
    new_vlan_type: str = ""
    old_physical_port: str = ""
    new_physical_port: str = ""
    old_virtual_port: str = ""
    new_virtual_port: str = ""
    old_switch_type: str = ""
    new_switch_type: str = ""
    source_type: str = "switch"
    source_id: Optional[int] = None
    source_name: str = ""
    dedup_key: str = ""
    change_detail: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True
