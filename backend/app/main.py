from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .config import settings
from .db import Base, engine, get_db
from .models import Doctor, Hospital, Specialty
from .schemas import ChatRequest, ChatResponse
from .agent import run_agent

app = FastAPI(title="HealTrip AI Patient Decision Assistant", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[settings.cors_origin], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        if not db.query(Specialty).first():
            cardiology = Specialty(name_en="Cardiology", name_ar="أمراض القلب")
            neurology = Specialty(name_en="Neurology", name_ar="طب الأعصاب")
            db.add_all([cardiology, neurology]); db.flush()
            h1 = Hospital(name_en="HealTrip Medical Center", name_ar="مركز هيل تريب الطبي", city="Jeddah", emergency_available=True)
            h2 = Hospital(name_en="Seaside Specialist Hospital", name_ar="مستشفى سي سايد التخصصي", city="Riyadh", emergency_available=False)
            db.add_all([h1, h2]); db.flush()
            db.add_all([
                Doctor(name_en="Dr. Ahmed Al-Harbi", name_ar="د. أحمد الحربي", specialty_id=cardiology.id, hospital_id=h1.id, languages="Arabic, English", years_experience=12),
                Doctor(name_en="Dr. Sara Al-Qahtani", name_ar="د. سارة القحطاني", specialty_id=cardiology.id, hospital_id=h2.id, languages="Arabic, English", years_experience=9),
                Doctor(name_en="Dr. Omar Saleh", name_ar="د. عمر صالح", specialty_id=neurology.id, hospital_id=h1.id, languages="Arabic, English", years_experience=10),
            ])
            db.commit()
    finally:
        db.close()

@app.get("/health")
def health(): return {"status":"ok"}

@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    try:
        return run_agent(db, req.message, req.history)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service temporarily unavailable") from exc
