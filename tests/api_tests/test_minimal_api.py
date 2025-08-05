#!/usr/bin/env python
"""Test minimal FastAPI app."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

# Store something in app state
app.state.test_value = "Hello from state"

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/state-test")
async def state_test(request: Request):
    """Test accessing app state."""
    value = request.app.state.test_value
    return {"state_value": value}

@app.get("/health")
async def health():
    """Simple health check."""
    return {"status": "healthy", "message": "API is running"}

if __name__ == "__main__":
    print("Starting minimal API on http://localhost:49495")
    uvicorn.run(app, host="127.0.0.1", port=49495)