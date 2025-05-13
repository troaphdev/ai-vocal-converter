# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install git - needed for dependencies from git AND for git-lfs
RUN apt-get update && apt-get install -y git git-lfs && rm -rf /var/lib/apt/lists/*

# Initialize Git LFS (system-wide, so it's available for any git operations)
# --skip-repo is important here as we\'re not in the .git dir of the final repo yet
RUN git lfs install --system --skip-repo

# Copy only the files necessary to resolve LFS and install Python dependencies first
COPY .lfsconfig .gitattributes requirements.txt ./

# If LFS URL is provided as a secret, configure Git to use it globally
# This ARG needs to be passed during the `docker build` command by Hugging Face Spaces, e.g., --build-arg RVC_LFS_URL=${RVC_LFS_URL_SECRET}
ARG RVC_LFS_URL
RUN if [ -n "$RVC_LFS_URL" ]; then \
        echo "Configuring Git LFS to use provided RVC_LFS_URL" && \
        git config --global lfs.url "$RVC_LFS_URL"; \
    else \
        echo "No RVC_LFS_URL provided, will use .lfsconfig or fail if credentials required by proxy for download."; \
    fi

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu118

# Copy the rest of the application code into the container
# This will include the .git directory if the build context sends it,
# or it will be a fresh copy. The LFS pull should happen after this.
COPY . .

# Pull LFS files
# This command will use the lfs.url (either from global config set via RVC_LFS_URL or from .lfsconfig)
# It should download the large files from your R2 proxy into the model directories etc.
RUN echo "Attempting to pull LFS files..." && git lfs pull && echo "LFS pull attempt finished."

# Verify LFS files (optional check - can be removed if causing issues)
# This checks if the pointer files are now actual files.
# Example: check one of your known LFS files.
# RUN if [ -f "hubert_base.pt" ] && [ $(head -n 1 "hubert_base.pt" | grep -c "version https://git-lfs.github.com/spec/v1") -eq 0 ]; then \
#         echo "hubert_base.pt appears to be a real file, not a pointer."; \
#     else \
#         echo "Warning: hubert_base.pt still appears to be an LFS pointer or is missing."; \
#     fi

# Make port 7860 available to the world outside this container
# Hugging Face Spaces typically uses port 7860
EXPOSE 7860

# Define environment variable for the port
ENV PORT=7860

# Run app.py when the container launches
# We use the app:app from your root app.py, which imports the FastAPI app from app.main
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"] 