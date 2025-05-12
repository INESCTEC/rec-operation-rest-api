# use a Python 3.10 image
FROM python:3.10

# Install dependencies
RUN apt-get update && apt-get install -y build-essential python3-dev git nano

# set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Updgrade pip and install the dependencies
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Expose the port on which the application will run
EXPOSE 80

# run the command to start uWSGI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]