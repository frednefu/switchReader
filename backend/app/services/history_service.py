"""Change detection: compare old vs new scan results to produce history records."""
from app.models.history import History, ChangeType

TRACKED_FIELDS = ["vlan_bd", "vlan_type", "physical_port", "virtual_port", "switch_type"]


def _make_entry(change_type, switch_id, scan_log_id, old_r, new_r):
    """Build a History record from old/new scan result rows."""
    entry = History(
        change_type=change_type,
        switch_id=switch_id,
        scan_log_id=scan_log_id,
    )
    if new_r is not None:
        entry.ip_address = new_r.ip_address
        entry.mac_address = new_r.mac_address
        entry.new_vlan_bd = new_r.vlan_bd
        entry.new_vlan_type = new_r.vlan_type or ""
        entry.new_physical_port = new_r.physical_port or ""
        entry.new_virtual_port = new_r.virtual_port or ""
        entry.new_switch_type = new_r.switch_type or ""
    if old_r is not None:
        if new_r is None:
            entry.ip_address = old_r.ip_address
            entry.mac_address = old_r.mac_address
        entry.old_vlan_bd = old_r.vlan_bd
        entry.old_vlan_type = old_r.vlan_type or ""
        entry.old_physical_port = old_r.physical_port or ""
        entry.old_virtual_port = old_r.virtual_port or ""
        entry.old_switch_type = old_r.switch_type or ""
    return entry


def detect_changes(db, switch_id: int, scan_log_id: int, old_by_key: dict, new_by_key: dict):
    """Diff old and new scan results by (ip, mac) key, write History records."""
    old_keys = set(old_by_key.keys())
    new_keys = set(new_by_key.keys())

    added = new_keys - old_keys
    deleted = old_keys - new_keys
    common = old_keys & new_keys

    count = 0

    for key in added:
        db.add(_make_entry(ChangeType.added, switch_id, scan_log_id, None, new_by_key[key]))
        count += 1

    for key in deleted:
        db.add(_make_entry(ChangeType.deleted, switch_id, scan_log_id, old_by_key[key], None))
        count += 1

    for key in common:
        old_r = old_by_key[key]
        new_r = new_by_key[key]
        changed = False
        for field in TRACKED_FIELDS:
            if str(getattr(old_r, field, None) or "") != str(getattr(new_r, field, None) or ""):
                changed = True
                break
        if changed:
            db.add(_make_entry(ChangeType.modified, switch_id, scan_log_id, old_r, new_r))
            count += 1

    return count
