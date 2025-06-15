import os

from typing import List

from dotenv import load_dotenv

load_dotenv()

PROJECT_NAME = os.getenv("PROJECT_NAME", "Ecommerce Platform")

API_V1_STR = "/api/v1"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/dbname")

BACKEND_CORS_ORIGINS = os.getenv(
    "BACKEND_CORS_ORIGINS",
    "http://localhost,http://localhost:4200,http://localhost:3000",
)

BACKEND_CORS_ORIGINS = BACKEND_CORS_ORIGINS.split(",")

USERS_OPEN_REGISTRATION = os.getenv("USERS_OPEN_REGISTRATION", "True") == "True"

SECRET_KEY = os.getenv("SECRET_KEY", "YOUR_SECRET_KEY")

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 30
