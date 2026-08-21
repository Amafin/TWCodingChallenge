from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional
import bcrypt
import jwt
from datetime import datetime, timedelta

from backend import models, schemas
from backend.database import engine, get_db

SECRET_KEY = "prompt-library-secret-key-local"
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

# Création bases de données
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Prompt Library")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


# Utilisateur
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalide")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")
    return user



# API Routes
@app.post("/api/auth/register", response_model=schemas.TokenResponse)
def register(data: schemas.UserAuth, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    user = models.User(email=data.email, password=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_token(user.id)}



@app.post("/api/auth/login", response_model=schemas.TokenResponse)
def login(data: schemas.UserAuth, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=400, detail="Identifiants incorrects")
    return {"access_token": create_token(user.id)}



# Prompts
# --- Récupérer les infos de l'utilisateur connecté ---
@app.get("/api/auth/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}

# --- Tags globaux de tous les prompts ---
@app.get("/api/tags", response_model=List[str])
def get_all_tags(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    prompts = db.query(models.Prompt.tag).all()
    all_tags = set()
    for (tag_str,) in prompts:
        if tag_str:
            parts = [t.strip() for t in tag_str.split(",") if t.strip()]
            all_tags.update(parts)
    
    tag_list = sorted(list(all_tags))
    if not tag_list:
        tag_list = ["Général"]
    return tag_list

# --- Lister TOUS les prompts de la communauté ---
@app.get("/api/prompts", response_model=List[schemas.PromptResponse])
def get_prompts(
    search: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Prompt)  # <-- Plus de filtre par user_id
    if search:
        query = query.filter(
            (models.Prompt.title.ilike(f"%{search}%")) |
            (models.Prompt.content.ilike(f"%{search}%")) |
            (models.Prompt.tag.ilike(f"%{search}%"))
        )
    return query.order_by(models.Prompt.id.desc()).all()

# --- Modification (autorisée uniquement pour le créateur) ---
@app.put("/api/prompts/{prompt_id}", response_model=schemas.PromptResponse)
def update_prompt(
    prompt_id: int,
    prompt_data: schemas.PromptUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    prompt = db.query(models.Prompt).filter(models.Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt non trouvé")
    if prompt.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Non autorisé à modifier ce prompt")

    if prompt_data.title is not None:
        prompt.title = prompt_data.title
    if prompt_data.tag is not None:
        clean_tags = ", ".join([t.strip() for t in prompt_data.tag.split(",") if t.strip()])
        prompt.tag = clean_tags or "Général"
    if prompt_data.content is not None:
        prompt.content = prompt_data.content

    db.commit()
    db.refresh(prompt)
    return prompt

# --- Suppression (autorisée uniquement pour le créateur) ---
@app.delete("/api/prompts/{prompt_id}")
def delete_prompt(
    prompt_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    prompt = db.query(models.Prompt).filter(models.Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt non trouvé")
    if prompt.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Non autorisé à supprimer ce prompt")

    db.delete(prompt)
    db.commit()
    return {"ok": True}

import os

# Calcule le chemin absolu vers le dossier frontend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Servir les fichiers Frontend statiques avec le chemin exact
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")