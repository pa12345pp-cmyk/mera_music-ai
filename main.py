from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, EmailStr, Field
from .db import Base, engine, get_db
from .models import User, WalletLedger, CreditLedger, GenerationJob
from .config import settings
from .security import hash_password, verify_password, make_token, current_user, admin_user

app = FastAPI(title="Mera Music AI API", version="0.1.0")
Base.metadata.create_all(bind=engine)

@app.on_event("startup")
def create_owner():
    db = next(get_db())
    try:
        owner = db.query(User).filter(
            User.email == settings.admin_email.lower()
        ).first()

        if not owner:
            owner = User(
                email=settings.admin_email.lower(),
                password_hash=hash_password(settings.admin_password),
                is_admin=True
            )
            db.add(owner)
        else:
            owner.password_hash = hash_password(settings.admin_password)
            owner.is_admin = True

        db.commit()
    finally:
        db.close()

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

class JobIn(BaseModel):
    job_type: str = Field(pattern="^(song|video)$")
    prompt: str = Field(min_length=3, max_length=5000)

@app.get("/health")
def health():
    return {"status": "ok", "service": "Mera Music AI API"}

@app.post("/auth/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = str(data.email).lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Email already registered")
    user = User(email=email, password_hash=hash_password(data.password), is_admin=False)
    db.add(user); db.commit(); db.refresh(user)
    return {"id": user.id, "email": user.email, "message": "Account created"}

@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username.lower()).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": make_token(user), "token_type": "bearer"}

@app.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    wallet = db.query(func.coalesce(func.sum(WalletLedger.amount_paise), 0)).filter(WalletLedger.user_id == user.id).scalar()
    credits = db.query(func.coalesce(func.sum(CreditLedger.credits), 0)).filter(CreditLedger.user_id == user.id).scalar()
    return {"email": user.email, "wallet_balance_paise": wallet, "credits": credits}

@app.post("/jobs")
def create_job(data: JobIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # No credits are deducted until a verified pricing rule and generation worker are configured.
    job = GenerationJob(user_id=user.id, job_type=data.job_type, prompt=data.prompt, status="needs_worker")
    db.add(job); db.commit(); db.refresh(job)
    return {"job_id": job.id, "status": job.status,
            "message": "Request saved. Connect the verified ACE-Step/video worker before generation."}

@app.get("/jobs")
def my_jobs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    jobs = db.query(GenerationJob).filter(GenerationJob.user_id == user.id).order_by(GenerationJob.id.desc()).limit(100).all()
    return [{"id": j.id, "type": j.job_type, "status": j.status, "output_url": j.output_url} for j in jobs]

@app.get("/admin/overview")
def admin_overview(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    # This route is server-side admin-protected; no customer can read these totals.
    return {
        "customers": db.query(User).filter(User.is_admin == False).count(),
        "jobs_total": db.query(GenerationJob).count(),
        "songs": db.query(GenerationJob).filter(GenerationJob.job_type == "song").count(),
        "videos": db.query(GenerationJob).filter(GenerationJob.job_type == "video").count(),
        "wallet_ledger_entries": db.query(WalletLedger).count()
    }

@app.post("/payments/webhook")
def payment_webhook():
    # Intentionally disabled: implement provider signature verification + idempotency
    # for the chosen gateway before accepting/crediting real payments.
    raise HTTPException(501, "Payment gateway not configured; no wallet credit was applied")

@app.get("/admin/secret-check")
def admin_secret_check(_: User = Depends(admin_user)):
    return {"admin_access": True}
