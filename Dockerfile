# Use a lightweight Python image
FROM python:3.12-slim

# Update
RUN apt-get update && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy source code
COPY streamlit_sender.py . 
COPY pyproject.toml .

# Install dependencies using uv
RUN uv sync

# Expose the streamlit port
EXPOSE 8501

# Run the server
CMD ["uv", "run", "streamlit", "run", "streamlit_sender.py", "--server.port=8501", "--server.address=0.0.0.0"]
