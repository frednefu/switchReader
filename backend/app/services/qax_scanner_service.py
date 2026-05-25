"""奇安信椒图（云锁）API 采集引擎"""
import hashlib
import time
import asyncio
import logging
from datetime import datetime

import urllib3
import requests

from app.database import SessionLocal
from app.models.qax import QianXinDevice, QianXinServer, QianXinPort, QianXinProcess, QianXinSoftware

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


class QianXinClient:
    """奇安信云锁 API 客户端"""

    def __init__(self, base_url: str, uuid: str, secret: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.uuid = uuid
        self.secret = secret
        self.timeout = timeout

    def _generate_token(self) -> str:
        timestamp = str(int(time.time()))
        raw = self.uuid + self.secret + timestamp
        secret_md5 = hashlib.md5(raw.encode()).hexdigest()
        return secret_md5 + self.uuid + timestamp

    def _headers(self) -> dict:
        return {
            "Api-Token": self._generate_token(),
            "Content-Type": "application/json",
        }

    def _post(self, path: str, body: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        resp = requests.post(
            url,
            json=body or {},
            headers=self._headers(),
            timeout=self.timeout,
            verify=False,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") in (1, "1", 200):
            return data
        raise RuntimeError(f"API 返回错误: code={data.get('code')}, msg={data.get('msg', data.get('message', ''))}")

    def get_server_list(self, page: int = 1, size: int = 10) -> dict:
        """获取服务器列表（单页），返回原始 API 响应用于分页判断。"""
        return self._post(
            "/api/assetSrv/machineController/searchMachineList",
            {"currentPage": page, "maxResults": size},
        )

    def get_all_servers(self, page_size: int = 100) -> list:
        """遍历所有分页，获取全部服务器列表。"""
        return self._get_all_pages(
            "/api/assetSrv/machineController/searchMachineList",
            {},
            page_size,
        )

    def _get_all_pages(self, path: str, base_body: dict, page_size: int = 100) -> list:
        """通用分页遍历，返回全部数据。"""
        all_items = []
        page = 1
        total = 0
        while True:
            body = {**base_body, "currentPage": page, "maxResults": page_size}
            result = self._post(path, body)
            items = _safe_list(result)
            if not items:
                break
            all_items.extend(items)
            inner = result.get("data")
            if isinstance(inner, dict):
                total = inner.get("total") or inner.get("totalCount") or total
            total = result.get("total") or result.get("totalCount") or total
            if total > 0 and len(all_items) >= total:
                break
            page += 1
            if page > 200:
                break
        return all_items

    def get_server_ports(self, machine_uuid: str) -> list:
        return self._get_all_pages(
            "/api/assetSrv/portController/searchMachineUuidPortList",
            {"machineUuid": machine_uuid},
        )

    def get_server_processes(self, machine_uuid: str) -> list:
        return self._get_all_pages(
            "/api/assetSrv/processController/searchMachineUuidProcessList",
            {"machineUuid": machine_uuid},
        )

    def get_server_software(self, machine_uuid: str) -> list:
        return self._get_all_pages(
            "/api/assetSrv/softwareAppController/searchMachineUuidUserList",
            {"machineUuid": machine_uuid},
        )


def _safe_list(data: dict, key: str = "list") -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in (key, "data", "rows", "items", "result", "records"):
            val = data.get(k)
            if isinstance(val, list):
                return val
        inner = data.get("data")
        if isinstance(inner, dict):
            for k in (key, "rows", "items", "list", "result"):
                val = inner.get(k)
                if isinstance(val, list):
                    return val
    return []


async def _run_qax_scan_async(device_id: int, scan_log_id: int | None = None):
    """异步扫描椒图设备，采集服务器清单及端口/进程/软件详情并写入数据库。"""
    from app.models.scan_log import ScanLog, ScanStatus

    start_time = datetime.now()

    db = SessionLocal()
    device = None
    server_count = 0
    try:
        device = db.query(QianXinDevice).get(device_id)
        if not device or not device.enabled:
            return

        device.last_scan_status = "running"
        device.last_scan_error = None
        db.commit()
        db.close()  # 释放 SQLite 连接，避免与后续 write_db 冲突

        client = QianXinClient(device.host, device.uuid, device.secret)

        loop = asyncio.get_running_loop()
        servers = await loop.run_in_executor(None, client.get_all_servers)

        write_db = SessionLocal()
        try:
            # 删除该设备所有旧数据
            old_server_ids = [
                r[0] for r in write_db.query(QianXinServer.id).filter(
                    QianXinServer.device_id == device_id
                ).all()
            ]
            if old_server_ids:
                write_db.query(QianXinPort).filter(
                    QianXinPort.server_id.in_(old_server_ids)
                ).delete(synchronize_session=False)
                write_db.query(QianXinProcess).filter(
                    QianXinProcess.server_id.in_(old_server_ids)
                ).delete(synchronize_session=False)
                write_db.query(QianXinSoftware).filter(
                    QianXinSoftware.server_id.in_(old_server_ids)
                ).delete(synchronize_session=False)
            write_db.query(QianXinServer).filter(
                QianXinServer.device_id == device_id
            ).delete()

            # 写入服务器基本信息
            for s in servers:
                server = QianXinServer(
                    device_id=device_id,
                    machine_uuid=s.get("machineUuid", ""),
                    machine_name=s.get("machineName", ""),
                    ipv4=s.get("ipv4") or s.get("intranetIp") or "",
                    intranet_ip=s.get("intranetIp") or "",
                    ipv6=s.get("ipv6") or "",
                    operation_system=s.get("operationSystem", ""),
                    kernel_version=s.get("kernelVersion", ""),
                    cpu=s.get("cpu") or s.get("cpuInfo", ""),
                    memory=s.get("memory") or s.get("memoryGb", ""),
                    disk_size_str=s.get("diskSizeStr") or s.get("diskSize", ""),
                    online_status=s.get("onlineStatus", 0),
                    run_status=s.get("runStatus", 0),
                    machine_group=s.get("machineGroup", ""),
                    port_count=s.get("portCount", 0),
                    process_count=s.get("processCount", 0),
                    software_count=s.get("softwareAppCount", 0),
                    web_count=s.get("webCount", 0),
                    web_server_count=s.get("webServerCount", 0),
                    database_count=s.get("databaseCount", 0),
                )
                write_db.add(server)
                write_db.flush()

                server_id = server.id
                machine_uuid = s.get("machineUuid", "")
                if not machine_uuid:
                    continue

                # 获取并写入端口
                try:
                    ports = await loop.run_in_executor(None, client.get_server_ports, machine_uuid)
                    for p in ports:
                        write_db.add(QianXinPort(
                            device_id=device_id,
                            server_id=server_id,
                            port=str(p.get("port", "")),
                            protocol=str(p.get("protocol", "")),
                            process_name=str(p.get("processName", "")),
                            start_user=str(p.get("startUser", "")),
                            process_version=str(p.get("processVersion", "")),
                        ))
                except Exception as e:
                    logger.warning("获取端口失败 server=%s: %s", s.get("machineName", ""), e)

                # 获取并写入进程
                try:
                    procs = await loop.run_in_executor(None, client.get_server_processes, machine_uuid)
                    for p in procs:
                        write_db.add(QianXinProcess(
                            device_id=device_id,
                            server_id=server_id,
                            process_name=str(p.get("processName", "")),
                            pid=str(p.get("pid", "")),
                            start_user=str(p.get("startUser", "")),
                            cpu_percent=str(p.get("cpuPercent", "")),
                            mem_percent=str(p.get("memPercent", "")),
                        ))
                except Exception as e:
                    logger.warning("获取进程失败 server=%s: %s", s.get("machineName", ""), e)

                # 获取并写入软件
                try:
                    sw_list = await loop.run_in_executor(None, client.get_server_software, machine_uuid)
                    for sw in sw_list:
                        write_db.add(QianXinSoftware(
                            device_id=device_id,
                            server_id=server_id,
                            software_name=str(sw.get("softwareName", "")),
                            version=str(sw.get("version", "")),
                            install_path=str(sw.get("installPath", "")),
                        ))
                except Exception as e:
                    logger.warning("获取软件失败 server=%s: %s", s.get("machineName", ""), e)

            write_db.commit()
            server_count = len(servers)
        except Exception:
            write_db.rollback()
            raise
        finally:
            write_db.close()

        duration = round((datetime.now() - start_time).total_seconds(), 1)
        # 重新打开 db 会话更新最终状态
        db = SessionLocal()
        db_device = db.query(QianXinDevice).get(device_id)
        if db_device:
            db_device.last_scan_status = "success"
            db_device.last_scan_time = datetime.now()
            db_device.last_scan_duration = duration
            db_device.last_server_count = server_count
            db_device.last_scan_error = None
            db.commit()
        db.close()
        logger.info("椒图 %s 扫描完成，服务器: %s，耗时 %ss", device.host, server_count, duration)
    except Exception as e:
        duration = round((datetime.now() - start_time).total_seconds(), 1)
        logger.exception("椒图 %s 扫描失败", device.host if device else device_id)
        try:
            db = SessionLocal()
            db_device = db.query(QianXinDevice).get(device_id)
            if db_device:
                db_device.last_scan_status = "failed"
                db_device.last_scan_error = str(e)
                db_device.last_scan_duration = duration
                db.commit()
            db.close()
        except Exception:
            pass

    # 更新扫描日志
    if scan_log_id:
        _db = SessionLocal()
        try:
            log = _db.query(ScanLog).get(scan_log_id)
            if log:
                log.status = ScanStatus.success
                log.hosts_found = server_count
                log.completed_at = datetime.now()
                if log.started_at:
                    log.duration_seconds = round((datetime.now() - log.started_at).total_seconds(), 1)
                _db.commit()
        except Exception:
            pass
        finally:
            _db.close()


async def trigger_qax_scan(device: QianXinDevice, triggered_by: str = "manual") -> int:
    """触发异步扫描，立即返回。返回 scan_log_id。"""
    from app.models.scan_log import ScanLog, ScanStatus, TriggerType

    db = SessionLocal()
    try:
        db_device = db.query(QianXinDevice).get(device.id)
        if db_device:
            db_device.last_scan_status = "running"
            db_device.last_scan_error = None

        trigger = TriggerType.manual if triggered_by == "manual" else TriggerType.scheduled
        scan_log = ScanLog(
            source_type="qax",
            source_id=device.id,
            source_name=device.name,
            status=ScanStatus.running,
            triggered_by=trigger,
            started_at=datetime.now(),
        )
        db.add(scan_log)
        db.commit()
        db.refresh(scan_log)
        scan_log_id = scan_log.id
    finally:
        db.close()
    asyncio.create_task(_run_qax_scan_async(device.id, scan_log_id))
    return scan_log_id


async def test_qax_connection(host: str, uuid: str, secret: str) -> dict:
    """测试椒图连接。"""
    loop = asyncio.get_running_loop()
    try:
        client = QianXinClient(host, uuid, secret)
        result = await loop.run_in_executor(None, client.get_server_list, 1, 10)
        servers = _safe_list(result)
        # 优先从 data.total 读取真实总数
        total = result.get("total") or result.get("totalCount")
        inner = result.get("data")
        if isinstance(inner, dict):
            total = inner.get("total") or inner.get("totalCount") or total
        if not total:
            total = len(servers)
        return {"ok": True, "message": f"连接成功，共 {total} 台服务器"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
