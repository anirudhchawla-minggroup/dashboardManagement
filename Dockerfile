# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables for Django admin creation
ENV DJANGO_SUPERUSER_USERNAME=ming_group_123 \
    DJANGO_SUPERUSER_PASSWORD=1234

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app/

# Upgrade pip
RUN pip install --upgrade pip

# Install dependencies from requirements.txt
RUN pip install -r requirements.txt

# Install gunicorn (we'll use it to run the Django app in production)
RUN pip install gunicorn

# Copy the SSL certificates for Nginx (assuming they are in the 'nginx' folder)
COPY ./nginx/dashboardManagement.crt /etc/nginx/cert/dashboardManagement.crt
COPY ./nginx/dashboardManagement.key /etc/nginx/cert/dashboardManagement.key
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "dashboardManagement.wsgi:application"]
