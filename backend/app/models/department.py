from sqlalchemy import Column, Integer, String, DateTime, func
from app.database import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dwbm = Column(String(32), unique=True, nullable=False, index=True, comment="单位编码")
    dwmc = Column(String(256), nullable=False, comment="单位名称")
    dwywmc = Column(String(256), nullable=True, comment="单位英文名称")
    dwjc = Column(String(128), nullable=True, comment="单位简称")
    dwdz = Column(String(512), nullable=True, comment="单位地址")
    dwcc = Column(String(64), nullable=True, comment="单位层次")
    lsdwh = Column(String(32), nullable=True, index=True, comment="隶属单位号（父级编码）")
    dwlbm = Column(String(32), nullable=True, comment="单位类别码")
    dwlbmc = Column(String(128), nullable=True, comment="单位类别名称")
    dwjbm = Column(String(32), nullable=True, comment="单位级别码")
    dwjbmc = Column(String(128), nullable=True, comment="单位级别名称")
    dwxzm = Column(String(32), nullable=True, comment="单位性质码")
    dwxzmc = Column(String(128), nullable=True, comment="单位性质名称")
    dwfzrgh = Column(String(32), nullable=True, comment="单位负责人工号")
    jlny = Column(String(16), nullable=True, comment="建立年月")
    sfst = Column(String(8), nullable=True, comment="是否实体")
    pxh = Column(String(16), nullable=True, comment="排序号")
    sfyx = Column(String(8), nullable=True, comment="是否有效")
    tstamp = Column(String(32), nullable=True, comment="时间戳")
    synced_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="同步时间")
