from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./predimaint.db"
    jwt_secret: str = "development-only-change-me"
    jwt_expire_minutes: int = 480
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_enabled: bool = True
    demo_tech_password: str = "change-tech-password"
    demo_manager_password: str = "change-manager-password"
    demo_director_password: str = "change-director-password"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


settings = Settings()
