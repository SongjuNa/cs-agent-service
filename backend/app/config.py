from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# 저장소 루트 (backend/app/config.py에서 두 단계 위)
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """환경 변수(.env)에서 읽는 설정 (기술 명세서 §1-5)."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str
    gemini_api_key: str = ""
    llm_model_small: str = "gemini-3.8-flash"
    llm_model_transcribe: str = ""  # L9 통화 받아쓰기 모델. 비우면 llm_model_small (기술 명세서 §12-7 T46)
    embedding_model: str = "gemini-embedding-2"
    data_dir: str = "data/CS_AI_Agent_Training_Data_v1"
    log_full_llm_io: bool = False  # 실행 로그에 지시문·응답 전문(가린 글)을 남긴다(FR-036 처리 4, §1-5)
    scheduler_enabled: bool = True  # 5분 주기 점검(§6-4). 끄면 periodic_check를 직접 부른다
    auto_send_default: bool = True  # 자동 처리 설정을 아직 저장하지 않았을 때의 켜짐 여부(변경 add-auto-send). 실제 메일을 연동하면 먼저 false로
    # 이관 메일 실제 발송·수신(변경 add-escalation-mail-live). 끄면 예전처럼 via_mail 표시만 남긴다
    mail_enabled: bool = False
    smtp_host: str = "localhost"
    smtp_port: int = 1025                         # Mailpit SMTP
    mailpit_api_url: str = "http://localhost:8025"  # 서버가 받은 메일함을 읽는 주소
    mailpit_public_url: str = "http://localhost:8025"  # 화면에서 여는 메일함 주소(브라우저 기준)
    mail_cs_address: str = "cs-center@cs.example.com"  # 이관 메일을 보내고 부서 답장을 받는 C/S 메일함
    mail_dept_domain: str = "dept.example.com"    # 부서 메일함 = 부서 코드 소문자 @ 이 도메인
    mail_poll_seconds: int = 30                   # 받은 메일함 확인 주기
    app_base_url: str = "http://localhost:5173"   # 메일 본문의 문의 화면 링크

    @property
    def data_path(self) -> Path:
        """운영진 데이터 폴더. 상대 경로는 저장소 루트 기준이다."""
        path = Path(self.data_dir)
        return path if path.is_absolute() else REPO_ROOT / path


def get_settings() -> Settings:
    return Settings()
