"""Seed script: create default admin user if not exists."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal, engine, Base
from app.models.user import User, UserRole
from app.utils.security import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@ipam.local",
            password_hash=hash_password("Admin123!"),
            role=UserRole.admin,
        )
        db.add(admin)
        db.commit()
        print("Default admin user created: admin / Admin123!")
    else:
        print("Admin user already exists, skipping.")

    viewer = db.query(User).filter(User.username == "viewer").first()
    if not viewer:
        viewer = User(
            username="viewer",
            email="viewer@ipam.local",
            password_hash=hash_password("Viewer123!"),
            role=UserRole.user,
        )
        db.add(viewer)
        db.commit()
        print("Default viewer user created: viewer / Viewer123!")
    else:
        print("Viewer user already exists, skipping.")
finally:
    db.close()
