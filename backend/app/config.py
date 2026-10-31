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

    @property
    def data_path(self) -> Path:
        """운영진 데이터 폴더. 상대 경로는 저장소 루트 기준이다."""
        path = Path(self.data_dir)
        return path if path.is_absolute() else REPO_ROOT / path


def get_settings() -> Settings:
    return Settings()
