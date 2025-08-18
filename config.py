from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    LOCAL_URL: str = os.getenv("LOCAL_URL", "http://localhost:11434")
    LOCAL_LLM_MODEL_NAME: str = os.getenv("LOCAL_LLM_MODEL_NAME")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()