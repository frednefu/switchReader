from sqlalchemy import Column, Integer, String, Boolean, Enum, DateTime, ForeignKey, Float, Text, func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class MibType(str, enum.Enum):
    standard = "standard"
    huawei = "huawei"


class Switch(Base):
    __tablename__ = "switches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    ip_address = Column(String(255), nullable=False, unique=True, index=True)
    community = Column(String(64), nullable=False)
    mib_type = Column(Enum(MibType), nullable=False, default=MibType.standard)
    snmp_port = Column(Integer, nullable=False, default=161)
    snmp_timeout = Column(Integer, nullable=False, default=3)
    snmp_retries = Column(Integer, nullable=False, default=2)
    scan_interval = Column(Integer, nullable=False, default=86400)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # 扫描状态（持久化，与其他数据源一致）
    last_scan_status = Column(String(16), nullable=True)
    last_scan_time = Column(DateTime, nullable=True)
    last_scan_duration = Column(Float, nullable=True)
    last_hosts_found = Column(Integer, nullable=False, default=0)
    last_routes_found = Column(Integer, nullable=False, default=0)
    last_scan_error = Column(Text, nullable=True)

    scan_results = relationship("ScanResult", back_populates="switch", cascade="all, delete-orphan")
    route_tables = relationship("RouteTable", back_populates="switch", cascade="all, delete-orphan")
    scan_logs = relationship("ScanLog", back_populates="switch", cascade="all, delete-orphan")
    history_records = relationship("History", back_populates="switch", cascade="all, delete-orphan")
