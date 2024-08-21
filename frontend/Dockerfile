FROM zauberzeug/nicegui:latest
WORKDIR /app

# Copy the requirements.txt file to the container
COPY requirements.txt .

# Install the app's dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app to the container
COPY . .

# Expose the port that Streamlit listens on
EXPOSE 8080

CMD ["python","main.py"]
