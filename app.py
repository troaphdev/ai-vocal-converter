# This file is the entry point for Hugging Face Spaces.
# It imports the FastAPI app instance from your existing app/main.py file.

from app.main import app

# Hugging Face Spaces will typically run this using Uvicorn, e.g.:
# uvicorn app:app --host 0.0.0.0 --port 7860
# So, you usually don't need to add uvicorn.run() here explicitly.

# If you need to run this locally for testing, you can add:
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000) 