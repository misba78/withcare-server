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
# 1. 데이터베이스 설정 (절대 경로 사용!)
# ==========================================
# 박사님 아이디(misba78) 경로에 맞춘 절대 경로입니다. (슬래시 4개 주의)
# 점(.) 하나가 '현재 위치'라는 뜻입니다. 슬래시 3개입니다.
SQLALCHEMY_DATABASE_URL = "sqlite:///./withcare_v2.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ==========================================
# 2. 데이터베이스 모델 정의 (설계도)
# ==========================================
class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer)  # 예: 1=뽀삐, 2=화초
    user_name = Column(String)  # 예: 아빠, 엄마
    action_type = Column(String)  # 예: MEAL(밥주기)
    performed_at = Column(DateTime, default=datetime.now)  # 언제?
    image_url = Column(String)  # 사진 주소 (추가된 부분!)


# DB 테이블 자동 생성 (없으면 만듦)
Base.metadata.create_all(bind=engine)

# ==========================================
# 3. FastAPI 앱 설정 & CORS (보안 해제)
# ==========================================
app = FastAPI()

# 크롬 브라우저나 외부 접속 허용 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 곳에서 접속 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 사진 저장할 폴더 만들기 (없으면 자동 생성)
if not os.path.exists("uploads"):
    os.makedirs("uploads")

# 'uploads' 폴더를 '/images' 주소로 연결 (외부에서 사진 보기 위함)
app.mount("/images", StaticFiles(directory="uploads"), name="images")


# DB 세션 가져오기 (도우미 함수)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==========================================
# 4. 기능(API) 구현
# ==========================================

# (1) 기본 접속 테스트
@app.get("/")
def read_root():
    return {"message": "WithCare Server is Running on Cloud!"}


# (2) 중복 체크 (방금 밥 줬는데 또 주는거 방지)
@app.post("/check-duplication")
def check_duplication(
        target_id: int,
        action_type: str,
        db: Session = Depends(get_db)
):
    # 최근 30분 이내 기록 찾기
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


# (3) 행동 기록 & 사진 업로드 (핵심 기능!)
@app.post("/actions")
async def log_action(
        target_id: int,
        user_name: str,
        action_type: str,
        file: UploadFile = File(...),  # 사진 파일 받기
        db: Session = Depends(get_db)
):
    # 1. 서버에 사진 파일 저장
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)

    # 2. 사진의 인터넷 주소 만들기 (클라우드 주소 적용!)
    # 주의: 주석은 '#'을 써야 합니다.
    # saved_file_url = f"https://misba78.pythonanywhere.com/images/{file.filename}"
    saved_file_url = f"/images/{file.filename}"
    # 3. DB에 기록 저장
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


# (4) 전체 기록 조회 (히스토리)
@app.get("/history")
def get_history(db: Session = Depends(get_db)):
    # 최신순으로 정렬해서 가져오기
    logs = db.query(ActionLog).order_by(ActionLog.performed_at.desc()).all()

    return logs
