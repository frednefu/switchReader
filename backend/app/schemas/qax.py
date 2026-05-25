"""奇安信椒图 — Pydantic 请求/响应模型"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── 设备 CRUD ──

class QianXinDeviceCreate(BaseModel):
    name: str
    host: str
    uuid: str
    secret: str
    scan_interval: int = 86400


class QianXinDeviceUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    uuid: Optional[str] = None
    secret: Optional[str] = None
    scan_interval: Optional[int] = None
    enabled: Optional[bool] = None


class QianXinDeviceOut(BaseModel):
    id: int
    name: str
    host: str
    uuid: str
    enabled: bool
    scan_interval: int
    last_scan_status: Optional[str] = None
    last_scan_time: Optional[datetime] = None
    last_scan_duration: Optional[float] = None
    last_server_count: int = 0
    last_scan_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── 连接测试 ──

class QAXTestRequest(BaseModel):
    host: str
    uuid: str
    secret: str


class QAXTestResponse(BaseModel):
    ok: bool
    message: str


# ── 扫描数据输出 ──

class QianXinServerOut(BaseModel):
    id: int
    device_id: int
    machine_uuid: str
    machine_name: str = ""
    ipv4: str = ""
    intranet_ip: str = ""
    ipv6: str = ""
    operation_system: str = ""
    kernel_version: str = ""
    cpu: str = ""
    memory: str = ""
    disk_size_str: str = ""
    online_status: int = 0
    run_status: int = 0
    machine_group: str = ""
    port_count: int = 0
    process_count: int = 0
    software_count: int = 0
    web_count: int = 0
    web_server_count: int = 0
    database_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QianXinPortOut(BaseModel):
    id: int
    device_id: int
    server_id: int
    port: str = ""
    protocol: str = ""
    process_name: str = ""
    start_user: str = ""
    process_version: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class QianXinProcessOut(BaseModel):
    id: int
    device_id: int
    server_id: int
    process_name: str = ""
    pid: str = ""
    start_user: str = ""
    cpu_percent: str = ""
    mem_percent: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class QianXinSoftwareOut(BaseModel):
    id: int
    device_id: int
    server_id: int
    software_name: str = ""
    version: str = ""
    install_path: str = ""
    created_at: datetime

    class Config:
        from_attributes = True
