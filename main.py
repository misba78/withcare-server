from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
import os
import shutil

# ==========================================
# 1. 데이터베이스 설정 (Render용)
# ==========================================
SQLALCHEMY_DATABASE_URL = "sqlite:///./withcare_v2.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# 2. 데이터베이스 모델 정의
# ==========================================
class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer)
    user_name = Column(String)
    action_type = Column(String)
    performed_at = Column(DateTime, default=datetime.now)
    image_url = Column(String)

Base.metadata.create_all(bind=engine)

# ==========================================
# 3. FastAPI 앱 설정
# ==========================================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not os.path.exists("uploads"):
    os.makedirs("uploads")

app.mount("/images", StaticFiles(directory="uploads"), name="images")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 4. 기능 구현
# ==========================================
@app.get("/")
def read_root():
    return {"message": "WithCare Server is Running on Cloud!"}

@app.post("/check-duplication")
def check_duplication(target_id: int, action_type: str, db: Session = Depends(get_db)):
    time_limit = datetime.now() - timedelta(minutes=30)
    recent_log = db.query(ActionLog).filter(
        ActionLog.target_id == target_id,
        ActionLog.action_type == action_type,
        ActionLog.performed_at >= time_limit
    ).order_by(ActionLog.performed_at.desc()).first()

    if recent_log:
        return {
            "status": "DUPLICATE",
            "message": f"이미 {recent_log.user_name}님이 밥을 줬어요!",
            "last_performed_at": recent_log.performed_at
        }
    else:
        return {"status": "OK", "message": "밥을 줘도 좋습니다."}

@app.post("/actions")
async def log_action(
    target_id: int,
    user_name: str,
    action_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)

    # ▼▼▼ [여기!] 박사님의 Render 주소를 넣어주세요 ▼▼▼
    # 예: https://withcare-app-abcd.onrender.com (끝에 슬래시 뺌)
    my_server_url = "https://withcare-app.onrender.com" 
    
    saved_file_url = f"{my_server_url}/images/{file.filename}"

    new_log = ActionLog(
        target_id=target_id,
        user_name=user_name,
        action_type=action_type,
        image_url=saved_file_url,
        performed_at=datetime.now()
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    return {"status": "SUCCESS", "data": new_log}

@app.get("/history")
def get_history(db: Session = Depends(get_db)):
    logs = db.query(ActionLog).order_by(ActionLog.performed_at.desc()).all()
    return logs

