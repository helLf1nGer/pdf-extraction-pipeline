"""Simple test server to verify networking"""
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello World", "status": "ok"}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "test-server"}

if __name__ == "__main__":
    print("Starting simple test server on http://127.0.0.1:8888")
    uvicorn.run(app, host="127.0.0.1", port=8888)