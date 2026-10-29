#!/usr/bin/env bash
set -u

# Avoid concurrent runs
exec 200>/tmp/instagram_plus_campaign.lock
if ! flock -n 200; then
    exit 0
fi

cd /home/ubuntu/oisha-os || exit 1
mkdir -p data

echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] Starting Instagram Plus Campaign check ===" >> data/instagram_plus_campaign.log
./venv/bin/python3 -u -m scripts.instagram_plus_campaign --days 7 --live --confirm YUBORISH >> data/instagram_plus_campaign.log 2>&1 || true
echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] Finished ===" >> data/instagram_plus_campaign.log

# Keep last 5000 lines to prevent log bloat
if [ -f data/instagram_plus_campaign.log ]; then
    tail -n 5000 data/instagram_plus_campaign.log > data/instagram_plus_campaign.log.tmp 2>/dev/null && mv data/instagram_plus_campaign.log.tmp data/instagram_plus_campaign.log
fi
