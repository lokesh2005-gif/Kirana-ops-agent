from sqlalchemy.orm import Session
from app.db.models import OwnerPreference
from typing import Optional

def set_preference(db: Session, key: str, value: str):
    pref = db.query(OwnerPreference).filter(OwnerPreference.key == key).first()
    if pref:
        pref.value = value
    else:
        pref = OwnerPreference(key=key, value=value)
        db.add(pref)
    db.commit()

def get_preference(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    pref = db.query(OwnerPreference).filter(OwnerPreference.key == key).first()
    return pref.value if pref else default
