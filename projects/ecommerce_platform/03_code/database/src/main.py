from fastapi import FastAPI
from database import database, models
from database.database import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.on_event("startup")
async def startup():
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


@app.get("/")
async def root():
    return {"message": "Hello World"}
