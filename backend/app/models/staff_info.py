from sqlalchemy import Column, Integer, String, DateTime, func
from app.database import Base


class StaffInfo(Base):
    __tablename__ = "staff_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gh = Column(String(32), unique=True, nullable=False, index=True, comment="工号")
    xm = Column(String(128), nullable=False, comment="姓名")
    szdwbm = Column(String(32), nullable=True, index=True, comment="所在单位编码")
    szks = Column(String(256), nullable=True, comment="所在科室")
    xbm = Column(String(8), nullable=True, comment="性别码")
    bgdh = Column(String(32), nullable=True, comment="办公电话")
    yddh = Column(String(32), nullable=True, comment="移动电话")
    dzyx = Column(String(128), nullable=True, comment="电子邮箱")
    synced_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="同步时间")
