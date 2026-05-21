from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    db_server: str = "localhost"
    db_name: str = "ReestrDb"
    db_driver: str = "{ODBC Driver 17 for SQL Server}"
    db_trusted_connection: str = "yes"
    db_user: Optional[str] = None
    db_password: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def connection_string(self) -> str:
        base_str = f"Driver={self.db_driver};Server={self.db_server};Database={self.db_name};"
        if self.db_user and self.db_password:
            # Подключение по логину и паролю
            return base_str + f"UID={self.db_user};PWD={self.db_password};"
        # Подключение через Windows Authentication
        return base_str + f"Trusted_Connection={self.db_trusted_connection};"

settings = Settings()
