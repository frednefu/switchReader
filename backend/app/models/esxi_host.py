from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class EsxiHost(Base):
    __tablename__ = "esxi_hosts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vcenter_id = Column(Integer, ForeignKey("vcenters.id", ondelete="CASCADE"), nullable=False)

    host_name = Column(String(255), default="")
    ip_address = Column(String(255), default="")
    processor_type = Column(String(255), default="")
    logical_processors = Column(Integer, default=0)
    memory_gb = Column(Float, default=0.0)
    hypervisor_type = Column(String(128), default="")
    nic_count = Column(Integer, default=0)
    status = Column(String(32), default="")

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    vcenter = relationship("VCenter", back_populates="esxi_hosts")
