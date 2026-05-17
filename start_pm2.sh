#!/bin/bash
set -e

echo "Building the workspace..."
pnpm install
pnpm build

echo "Starting applications with PM2..."
# Install pm2 globally if not installed
if ! command -v pm2 &> /dev/null
then
    echo "PM2 could not be found. Installing via npm..."
    npm install -g pm2
fi

pm2 start ecosystem.config.js
pm2 save
pm2 startup

echo "SalesCoach applications are now running 24/7 in the background!"
