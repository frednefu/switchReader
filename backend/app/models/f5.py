"""F5 BIG-IP 负载均衡器模型"""
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from app.database import Base


class F5Device(Base):
    __tablename__ = "f5_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    host = Column(String(255), nullable=False, unique=True, index=True)
    username = Column(String(128), nullable=False)
    password = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False, default=443)
    scan_interval = Column(Integer, nullable=False, default=86400)
    is_active = Column(Boolean, nullable=False, default=True)

    last_scan_status = Column(String(16), nullable=True)
    last_scan_time = Column(DateTime, nullable=True)
    last_scan_duration = Column(Float, nullable=True)
    last_vs_count = Column(Integer, nullable=False, default=0)
    last_pool_count = Column(Integer, nullable=False, default=0)
    last_scan_error = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    virtual_servers = relationship("F5VirtualServer", back_populates="device", cascade="all, delete-orphan")
    pool_members = relationship("F5PoolMember", back_populates="device", cascade="all, delete-orphan")
    rules = relationship("F5Rule", back_populates="device", cascade="all, delete-orphan")
    application_maps = relationship("F5ApplicationMap", back_populates="device", cascade="all, delete-orphan")


class F5VirtualServer(Base):
    __tablename__ = "f5_virtual_servers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    f5_device_id = Column(Integer, ForeignKey("f5_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    destination = Column(String(255), default="")
    vs_ip = Column(String(45), default="")
    vs_port = Column(Integer, nullable=True)
    pool_name = Column(String(255), nullable=True, default="")
    rules = Column(Text, default="[]")
    raw_config = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    device = relationship("F5Device", back_populates="virtual_servers")


class F5PoolMember(Base):
    __tablename__ = "f5_pool_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    f5_device_id = Column(Integer, ForeignKey("f5_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    pool_name = Column(String(255), default="")
    member_name = Column(String(255), default="")
    member_ip = Column(String(45), default="")
    member_port = Column(Integer, nullable=True)
    member_state = Column(String(32), default="")
    raw_config = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    device = relationship("F5Device", back_populates="pool_members")


class F5Rule(Base):
    __tablename__ = "f5_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    f5_device_id = Column(Integer, ForeignKey("f5_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_name = Column(String(255), default="")
    rule_content = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    device = relationship("F5Device", back_populates="rules")


class F5ApplicationMap(Base):
    """最终映射清单：域名 → VS IP:端口 → Pool 成员 IP:端口"""
    __tablename__ = "f5_application_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    f5_device_id = Column(Integer, ForeignKey("f5_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    domain_name = Column(String(255), default="")
    vs_name = Column(String(255), default="")
    vs_ip = Column(String(45), default="")
    vs_port = Column(Integer, nullable=True)
    pool_name = Column(String(255), default="")
    rule_name = Column(String(255), default="")
    member_ip = Column(String(45), default="")
    member_port = Column(Integer, nullable=True)
    member_state = Column(String(32), default="")
    source = Column(String(64), default="")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    device = relationship("F5Device", back_populates="application_maps")
