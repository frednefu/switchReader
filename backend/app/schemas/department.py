from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── Department ──

class DepartmentBase(BaseModel):
    dwbm: str
    dwmc: str
    dwywmc: Optional[str] = None
    dwjc: Optional[str] = None
    dwdz: Optional[str] = None
    dwcc: Optional[str] = None
    lsdwh: Optional[str] = None
    dwlbm: Optional[str] = None
    dwlbmc: Optional[str] = None
    dwjbm: Optional[str] = None
    dwjbmc: Optional[str] = None
    dwxzm: Optional[str] = None
    dwxzmc: Optional[str] = None
    dwfzrgh: Optional[str] = None
    jlny: Optional[str] = None
    sfst: Optional[str] = None
    pxh: Optional[str] = None
    sfyx: Optional[str] = None
    tstamp: Optional[str] = None


class DepartmentOut(DepartmentBase):
    id: int
    synced_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DepartmentTreeNode(BaseModel):
    """组织树节点"""
    id: int
    dwbm: str
    dwmc: str
    dwjc: Optional[str] = None
    lsdwh: Optional[str] = None
    pxh: Optional[str] = None
    user_count: int = 0
    children: List["DepartmentTreeNode"] = []

    class Config:
        from_attributes = True


class DepartmentSyncResult(BaseModel):
    total: int
    created: int
    updated: int


# ── StaffInfo ──

class StaffInfoBase(BaseModel):
    gh: str
    xm: str
    szdwbm: Optional[str] = None
    szks: Optional[str] = None
    xbm: Optional[str] = None
    bgdh: Optional[str] = None
    yddh: Optional[str] = None
    dzyx: Optional[str] = None


class StaffInfoOut(StaffInfoBase):
    id: int
    department_name: Optional[str] = None
    department_id: Optional[int] = None
    synced_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StaffLookupRequest(BaseModel):
    gh: Optional[str] = None
    xm: Optional[str] = None


class StaffLookupResponse(BaseModel):
    found: bool
    staff_list: list[StaffInfoOut] = []
    message: str = ""
