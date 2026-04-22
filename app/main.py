from fastapi import FastAPI

from app.api.routes.leads import router as leads_router

app = FastAPI(title='Expired Listing AI API')
app.include_router(leads_router)


@app.get('/health')
def health():
    return {'ok': True}
