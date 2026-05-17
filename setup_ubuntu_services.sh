#!/bin/bash
set -e

echo "========================================="
echo " Installing Postgres, Redis, and Minio   "
echo " Directly on Ubuntu (Without Docker)     "
echo "========================================="

# Update package lists
sudo apt-get update -y

# 1. Install PostgreSQL
echo "--> Installing PostgreSQL..."
sudo apt-get install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Configure PostgreSQL Database and User
echo "--> Configuring PostgreSQL for SalesCoach..."
sudo -u postgres psql -c "CREATE USER salescoach WITH PASSWORD 'salescoach_dev';" || true
sudo -u postgres psql -c "CREATE DATABASE salescoach OWNER salescoach;" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE salescoach TO salescoach;" || true

# 2. Install Redis
echo "--> Installing Redis..."
sudo apt-get install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

# 3. Install Minio
echo "--> Installing Minio Server..."
cd /tmp
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio
sudo mv minio /usr/local/bin/

# Create Minio data directory and user
sudo mkdir -p /var/lib/minio/data
sudo useradd -r -s /bin/false minio-user || true
sudo chown -R minio-user:minio-user /var/lib/minio

# Create Minio Systemd Service
echo "--> Configuring Minio Service..."
cat << 'SERVICE' | sudo tee /etc/systemd/system/minio.service
[Unit]
Description=MinIO
Documentation=https://docs.min.io
Wants=network-online.target
After=network-online.target

[Service]
User=minio-user
Group=minio-user
Environment="MINIO_ROOT_USER=salescoach"
Environment="MINIO_ROOT_PASSWORD=salescoach_dev_password"
ExecStart=/usr/local/bin/minio server /var/lib/minio/data --console-address ":9001"
Restart=always
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
SERVICE

# Start Minio
sudo systemctl daemon-reload
sudo systemctl enable minio
sudo systemctl start minio

echo "========================================="
echo " Setup Complete!                         "
echo " Postgres is running on port 5432        "
echo " Redis is running on port 6379           "
echo " Minio is running on ports 9000 & 9001   "
echo " All services will auto-restart 24/7.    "
echo "========================================="
