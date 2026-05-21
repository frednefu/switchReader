"""
华为 SDN 交换机 MIB 探测工具

用法：
  /c/Users/Administrator/.conda/envs/fred/python.exe switchReader/huawei_mib_test.py <IP> [community] [context]

示例：
  # 不带 VPN context
  python switchReader/huawei_mib_test.py 10.110.112.11 fred7531

  # 带 VPN context (如 Router_5004)
  python switchReader/huawei_mib_test.py 10.110.112.11 fred7531 Router_5004
"""
import asyncio
import sys
from pysnmp.hlapi.v1arch import Slim, ObjectType, ObjectIdentity

# ============================================================
# 探测目标 OID 列表
# ============================================================

# 华为企业前缀
HW = '1.3.6.1.4.1.2011'

PROBE_OIDS = {
    # -- 标准 MIB --
    'sysDescr':                     '1.3.6.1.2.1.1.1.0',
    'sysServices':                  '1.3.6.1.2.1.1.7.0',

    # -- 标准 ARP (IP-MIB) --
    'ipNetToMediaPhysAddress':      '1.3.6.1.2.1.4.22.1.2',

    # -- 标准 MAC 转发表 --
    'dot1qTpFdbPort':               '1.3.6.1.2.1.17.7.1.2.2.1.2',
    'dot1dTpFdbPort':               '1.3.6.1.2.1.17.4.3.1.2',

    # -- 华为私有: MAC 转发表 (HUAWEI-L2MAM-MIB), 多种可能路径 --
    'hwL2MacDynamicEntry (.42.2.1.1)':   f'{HW}.5.25.42.2.1.1',
    'hwL2MacIfIndex (.42.2.1.1.3)':      f'{HW}.5.25.42.2.1.1.3',
    'hwL2MacVlanType (.42.2.1.1.5)':     f'{HW}.5.25.42.2.1.1.5',
    # 尝试 .42.1.x 路径
    'hwL2Mac at .42.1.1':                f'{HW}.5.25.42.1.1',
    'hwL2Mac at .42.1.2':                f'{HW}.5.25.42.1.2',
    'hwL2Mac at .42.1.3':                f'{HW}.5.25.42.1.3',
    # 尝试 .42.3.x 路径
    'hwL2Mac at .42.3.2':                f'{HW}.5.25.42.3.2',
    'hwL2Mac at .42.3.3':                f'{HW}.5.25.42.3.3',
    # 尝试 .42.4.x
    'hwL2Mac at .42.4.1':                f'{HW}.5.25.42.4.1',
    # 尝试 .25.41 (另一个MIB区域)
    'MAC at .25.41.1.1':                 f'{HW}.5.25.41.1.1',
    'MAC at .25.41.1.2':                 f'{HW}.5.25.41.1.2',

    # -- 华为私有: ARP 表候选 (多种可能路径) --
    'hwARPDynamicEntry (123.1)':    f'{HW}.5.25.123.1',     # HUAWEI-ARP-MIB 常见路径
    'hwARPDynamicEntry (123.2)':    f'{HW}.5.25.123.2',
    'hwIpNetToMediaEntry (25.1)':   f'{HW}.5.25.25.1',      # 另一可能路径
    'hwARPDynTable (38.1)':         f'{HW}.5.25.38.1',      # 老文档常见
    'hwARPDynTable (38.2)':         f'{HW}.5.25.38.2',
    'hwARPDynTable (38.3)':         f'{HW}.5.25.38.3',

    # -- 华为私有: IP-MIB 候选 --
    'hwIPEntry (120.1)':            f'{HW}.5.25.120.1',
    'hwIPNetToMedia (37.1)':        f'{HW}.5.25.37.1',

    # -- 华为私有: 设备信息 --
    'hwEntitySystemNode':           f'{HW}.2.6.7.1.1',
    'hwL2DevVlanExist':             f'{HW}.5.25.42.1.1.1',

    # -- 华为私有: BD 相关 --
    'hwBdTable':                    f'{HW}.5.25.40.1.1',
    'hwVlanMappingEntry':           f'{HW}.5.25.42.3.1',
}


async def probe_all(slim, ip, community, port=161, timeout=3, retries=2):
    """依次探测所有目标 OID，统计每个 OID 的返回条目数。"""
    results = {}

    for name, oid in PROBE_OIDS.items():
        count = 0
        first_value = None
        next_vb = ObjectType(ObjectIdentity(oid))

        try:
            for _ in range(500):  # 限制每个 OID 最多走 500 步
                err, err_status, err_idx, varBinds = await slim.next(
                    community, ip, port, next_vb,
                    timeout=timeout, retries=retries,
                )
                if err:
                    count = -1  # 表示有错误
                    first_value = str(err)[:80]
                    break
                if err_status:
                    count = -2  # SNMP 错误状态
                    first_value = str(err_status)[:80]
                    break
                if not varBinds:
                    break
                for vb in varBinds:
                    oid_str = str(vb[0])
                    if not oid_str.startswith(oid + '.') and oid_str != oid:
                        break  # 走出子树
                    count += 1
                    if first_value is None:
                        first_value = str(vb[1])[:60]
                        # 对 ARP 类型尝试解析 MAC
                        try:
                            first_value = ':'.join(f'{b:02x}' for b in vb[1].asOctets())
                        except Exception:
                            pass
                    next_vb = ObjectType(ObjectIdentity(oid_str))
                else:
                    continue
                break
        except Exception as e:
            count = -3
            first_value = str(e)[:80]

        results[name] = (count, first_value)

    return results


def print_results(ip, community, context, results):
    """格式化输出探测结果。"""
    ctx_str = f'@{context}' if context else ''
    print(f"\n{'='*70}")
    print(f"华为 MIB 探测结果: {ip}  (community={community}{ctx_str})")
    print(f"{'='*70}")
    print(f"{'OID 名称':35s} {'条目数':>6s}  第一项值")
    print(f"{'-'*35} {'-'*6}  {'-'*36}")

    for name, (count, first_val) in results.items():
        if count > 0:
            print(f"{name:35s} {count:6d}  {first_val or '-'}")
        elif count == 0:
            print(f"{name:35s} {'(空)':>6s}  -")
        elif count == -1:
            print(f"{name:35s} {'(错误)':>6s}  {first_val or '-'}")
        elif count == -2:
            print(f"{name:35s} {'(SNMP错)':>6s}  {first_val or '-'}")
        elif count == -3:
            print(f"{name:35s} {'(异常)':>6s}  {first_val or '-'}")

    print()

    # 汇总
    available = [n for n, (c, _) in results.items() if c > 0]
    empty = [n for n, (c, _) in results.items() if c == 0]
    errors = [n for n, (c, _) in results.items() if c < 0]

    print(f"Available: {len(available)}  |  Empty: {len(empty)}  |  Errors: {len(errors)}")
    if available:
        print(f"\nUsable MIB nodes:")
        for n in available:
            c, v = results[n]
            print(f"  [OK] {n}  ->  {c} entries, first={v}")
    if errors:
        print(f"\nFailed MIB nodes:")
        for n in errors:
            c, v = results[n]
            print(f"  [ERR] {n}  ->  {v}")


async def _walk_oid(slim, ip, community, oid, max_steps=500):
    """Walk an OID and return {oid_str: value} dict."""
    data = {}
    next_vb = ObjectType(ObjectIdentity(oid))
    for _ in range(max_steps):
        err, err_status, err_idx, varBinds = await slim.next(
            community, ip, 161, next_vb, timeout=3, retries=1,
        )
        if err or err_status or not varBinds:
            break
        for vb in varBinds:
            oid_str = str(vb[0])
            if not oid_str.startswith(oid + '.') and oid_str != oid:
                return data
            data[oid_str] = vb[1]
            next_vb = ObjectType(ObjectIdentity(oid_str))
    return data


def _format_mac_from_bytes(val):
    try:
        return ':'.join(f'{b:02x}' for b in val.asOctets())
    except Exception:
        return str(val)[:40]


async def deep_probe_arp(slim, ip, community):
    """深入探测华为 ARP 相关 MIB 列，提取实际 IP/MAC 数据。"""
    HW_BASE = '1.3.6.1.4.1.2011.5.25.38'

    # 探测 .38 下的所有列 (1-10)
    print(f"\n{'='*60}")
    print(f"Deep probe: hwARPDynTable columns under {HW_BASE}")
    print(f"{'='*60}")

    for col in range(1, 11):
        oid = f'{HW_BASE}.{col}'
        data = await _walk_oid(slim, ip, community, oid)
        if data:
            print(f"\n  Column .38.{col}: {len(data)} entries")
            # Show first 5 entries
            for oid_str, val in list(data.items())[:5]:
                val_str = _format_mac_from_bytes(val)
                print(f"    {oid_str}  =  {val_str}")
            if len(data) > 5:
                print(f"    ... and {len(data)-5} more")

    # 尝试解析: 如果 .38.1 是 ifIndex, .38.2 是 MAC, 尝试配对
    col1 = await _walk_oid(slim, ip, community, f'{HW_BASE}.1')
    col2 = await _walk_oid(slim, ip, community, f'{HW_BASE}.2')

    if col1 and col2:
        # 按索引匹配
        print(f"\n  Attempting to match ARP entries (col.1=ifIndex, col.2=MAC):")
        col2_by_suffix = {}
        for oid_str, val in col2.items():
            suffix = oid_str[len(f'{HW_BASE}.2') + 1:]
            col2_by_suffix[suffix] = val

        count = 0
        for oid_str, ifindex in col1.items():
            suffix = oid_str[len(f'{HW_BASE}.1') + 1:]
            mac_val = col2_by_suffix.get(suffix)
            if mac_val:
                mac_str = _format_mac_from_bytes(mac_val)
                # 解析 suffix 可能含 IP
                parts = suffix.split('.')
                if len(parts) >= 4:
                    maybe_ip = '.'.join(parts[-4:])
                    print(f"    ifIndex={ifindex}  MAC={mac_str}  suffix_ip={maybe_ip}")
                else:
                    print(f"    ifIndex={ifindex}  MAC={mac_str}  suffix={suffix}")
                count += 1
                if count >= 8:
                    break


async def main_async(ip, community, context=None):
    """主异步入口。"""
    slim = Slim()

    # 如果有 context，尝试 community@context 语法（华为 SNMPv2c 扩展）
    if context:
        comm_with_ctx = f'{community}@{context}'
        print(f"SNMP Context: {comm_with_ctx}")
    else:
        comm_with_ctx = community

    # 1. 基础连通性检查
    print(f"Connectivity check: {ip} ...")
    err, err_status, _, varBinds = await slim.get(
        comm_with_ctx, ip, 161,
        ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0')),
        timeout=3, retries=1,
    )
    if err or err_status:
        print(f"  Failed: {err or err_status}")
        if context:
            print(f"  Retry without context...")
            err, err_status, _, varBinds = await slim.get(
                community, ip, 161,
                ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0')),
                timeout=3, retries=1,
            )
            if err or err_status:
                print(f"  Still failed: {err or err_status}")
                slim.close()
                return
            else:
                print(f"  Connected without context (context syntax may not be supported)")
                comm_with_ctx = community
        else:
            slim.close()
            return
    else:
        sys_descr = str(varBinds[0][1]) if varBinds else 'N/A'
        print(f"  Connected! Device: {sys_descr[:80]}")

    # 2. 探测所有 OID
    results = await probe_all(slim, ip, comm_with_ctx)
    print_results(ip, community, context, results)

    # 3. 深入探测华为 ARP MIB
    await deep_probe_arp(slim, ip, comm_with_ctx)

    # 4. 广泛扫描 Huawei L2MAM 子树，定位 FDB 表
    await deep_probe_l2mac_find(slim, ip, comm_with_ctx)

    slim.close()


async def deep_probe_l2mac_find(slim, ip, community):
    """Scan the Huawei 5.25.42 subtree to locate the L2 MAC forwarding table."""
    HW_L2 = '1.3.6.1.4.1.2011.5.25.42'

    print(f"\n{'='*60}")
    print(f"Broad scan: locating L2 FDB table under {HW_L2}")
    print(f"{'='*60}")

    # Walk the entire .42 subtree to see what's there (limit scope)
    for sub in [1, 2, 3, 4, 5, 99]:
        oid = f'{HW_L2}.{sub}'
        data = await _walk_oid(slim, ip, community, oid, max_steps=50)
        if data:
            first_oid = list(data.keys())[0]
            first_val = _format_mac_from_bytes(data[first_oid])
            print(f"  .42.{sub}: {len(data)} entries, first OID={first_oid}, val={first_val}")
        else:
            print(f"  .42.{sub}: empty")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ip = sys.argv[1]
    community = sys.argv[2] if len(sys.argv) > 2 else 'fred7531'
    context = sys.argv[3] if len(sys.argv) > 3 else None

    asyncio.run(main_async(ip, community, context))


if __name__ == '__main__':
    main()
