from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from .models import Doctor, Hospital, Specialty

# Tools are application-owned. The model can request them, but it cannot execute SQL.
def search_doctors(db: Session, specialty: str | None = None, city: str | None = None, limit: int = 5):
    stmt = select(Doctor).options(joinedload(Doctor.specialty), joinedload(Doctor.hospital)).where(Doctor.available.is_(True))
    if specialty:
        specialty = specialty.strip()
        specialty_key = specialty.casefold()
        for stored_specialty in db.scalars(select(Specialty.name_en)).all():
            stored_name = stored_specialty.strip()
            person_form = stored_name[:-1] + "ist" if stored_name.casefold().endswith("y") else None
            if specialty_key in {stored_name.casefold(), person_form.casefold() if person_form else ""}:
                specialty = stored_name
                break
        stmt = stmt.join(Doctor.specialty).where(Specialty.name_en.ilike(f"%{specialty}%"))
    if city:
        stmt = stmt.join(Doctor.hospital).where(Hospital.city.ilike(f"%{city}%"))
    rows = db.scalars(stmt.limit(min(limit, 10))).unique().all()
    return [{"id": d.id, "name_en": d.name_en, "name_ar": d.name_ar, "specialty": d.specialty.name_en, "hospital": d.hospital.name_en, "city": d.hospital.city} for d in rows]

def search_hospitals(db: Session, city: str | None = None, emergency_available: bool | None = None, limit: int = 5):
    stmt = select(Hospital)
    if city:
        stmt = stmt.where(Hospital.city.ilike(f"%{city}%"))
    if emergency_available is not None:
        stmt = stmt.where(Hospital.emergency_available == emergency_available)
    rows = db.scalars(stmt.limit(min(limit, 10))).all()
    return [{"id": h.id, "name_en": h.name_en, "name_ar": h.name_ar, "city": h.city, "country": h.country, "emergency_available": h.emergency_available} for h in rows]
