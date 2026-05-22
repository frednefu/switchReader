"""一次性迁移脚本：为 history_records 表添加新列和索引。"""
from app.database import engine
from sqlalchemy import text

conn = engine.connect()
conn.execute(text("ALTER TABLE history_records ADD COLUMN source_type VARCHAR(16) DEFAULT 'switch'"))
conn.execute(text("ALTER TABLE history_records ADD COLUMN source_id INTEGER"))
conn.execute(text("ALTER TABLE history_records ADD COLUMN source_name VARCHAR(255) DEFAULT ''"))
conn.execute(text("ALTER TABLE history_records ADD COLUMN dedup_key VARCHAR(512) DEFAULT ''"))
conn.execute(text("ALTER TABLE history_records ADD COLUMN change_detail TEXT"))
try:
    conn.execute(text("CREATE INDEX idx_hr_source ON history_records(source_type)"))
except Exception:
    pass  # 索引可能已存在
try:
    conn.execute(text("CREATE INDEX idx_hr_dedup ON history_records(dedup_key)"))
except Exception:
    pass
conn.commit()
conn.close()
print("迁移完成：history_records 表已添加 5 个新列和 2 个索引")
