from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class Specialty(Base):
    __tablename__ = "specialties"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_en: Mapped[str] = mapped_column(String(100), unique=True)
    name_ar: Mapped[str] = mapped_column(String(100))
    doctors: Mapped[list["Doctor"]] = relationship(back_populates="specialty")

class Hospital(Base):
    __tablename__ = "hospitals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_en: Mapped[str] = mapped_column(String(160), unique=True)
    name_ar: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(100), index=True)
    country: Mapped[str] = mapped_column(String(100), default="Saudi Arabia")
    emergency_available: Mapped[bool] = mapped_column(Boolean, default=False)
    doctors: Mapped[list["Doctor"]] = relationship(back_populates="hospital")

class Doctor(Base):
    __tablename__ = "doctors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_en: Mapped[str] = mapped_column(String(160))
    name_ar: Mapped[str] = mapped_column(String(160))
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"))
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    languages: Mapped[str] = mapped_column(String(160), default="English, Arabic")
    years_experience: Mapped[int] = mapped_column(Integer, default=5)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    specialty: Mapped[Specialty] = relationship(back_populates="doctors")
    hospital: Mapped[Hospital] = relationship(back_populates="doctors")
