"""奇安信椒图（云锁）服务器安全管理 — 设备与扫描数据模型"""
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from app.database import Base


class QianXinDevice(Base):
    __tablename__ = "qax_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    host = Column(String(255), nullable=False, unique=True, index=True)
    uuid = Column(String(255), nullable=False)
    secret = Column(String(255), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    scan_interval = Column(Integer, nullable=False, default=86400)

    last_scan_status = Column(String(16), nullable=True)
    last_scan_time = Column(DateTime, nullable=True)
    last_scan_duration = Column(Float, nullable=True)
    last_server_count = Column(Integer, nullable=False, default=0)
    last_scan_error = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    servers = relationship("QianXinServer", back_populates="device", cascade="all, delete-orphan")


class QianXinServer(Base):
    """服务器清单 — 每次扫描全量刷新"""
    __tablename__ = "qax_servers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("qax_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_uuid = Column(String(64), nullable=False, index=True)
    machine_name = Column(String(255), default="")
    ipv4 = Column(String(255), default="")
    intranet_ip = Column(String(255), default="")
    ipv6 = Column(String(512), default="")
    operation_system = Column(String(255), default="")
    kernel_version = Column(String(128), default="")
    cpu = Column(String(128), default="")
    memory = Column(String(32), default="")
    disk_size_str = Column(String(64), default="")
    online_status = Column(Integer, default=0)
    run_status = Column(Integer, default=0)
    machine_group = Column(String(128), default="")
    port_count = Column(Integer, default=0)
    process_count = Column(Integer, default=0)
    software_count = Column(Integer, default=0)
    web_count = Column(Integer, default=0)
    web_server_count = Column(Integer, default=0)
    database_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    device = relationship("QianXinDevice", back_populates="servers")
    ports = relationship("QianXinPort", back_populates="server", cascade="all, delete-orphan")
    processes = relationship("QianXinProcess", back_populates="server", cascade="all, delete-orphan")
    software = relationship("QianXinSoftware", back_populates="server", cascade="all, delete-orphan")


class QianXinPort(Base):
    __tablename__ = "qax_ports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("qax_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    server_id = Column(Integer, ForeignKey("qax_servers.id", ondelete="CASCADE"), nullable=False, index=True)
    port = Column(String(16), default="")
    protocol = Column(String(16), default="")
    process_name = Column(String(255), default="")
    start_user = Column(String(128), default="")
    process_version = Column(String(128), default="")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    server = relationship("QianXinServer", back_populates="ports")


class QianXinProcess(Base):
    __tablename__ = "qax_processes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("qax_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    server_id = Column(Integer, ForeignKey("qax_servers.id", ondelete="CASCADE"), nullable=False, index=True)
    process_name = Column(String(255), default="")
    pid = Column(String(16), default="")
    start_user = Column(String(128), default="")
    cpu_percent = Column(String(16), default="")
    mem_percent = Column(String(16), default="")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    server = relationship("QianXinServer", back_populates="processes")


class QianXinSoftware(Base):
    __tablename__ = "qax_software"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("qax_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    server_id = Column(Integer, ForeignKey("qax_servers.id", ondelete="CASCADE"), nullable=False, index=True)
    software_name = Column(String(255), default="")
    version = Column(String(128), default="")
    install_path = Column(String(512), default="")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    server = relationship("QianXinServer", back_populates="software")
