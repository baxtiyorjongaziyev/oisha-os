#!/bin/sh
export PATH=/home/hermes/.hermes/installs/019d0d114d22b7e6/environments/f1005c748ab046329d2857df237db84d/venv/bin:/home/hermes/.hermes/tools/python-3.14.9+20261021-linux-x64/bin:/usr/bin:/bin
export PYTHONPATH=/home/hermes/.hermes/hermes-agent
exec /home/hermes/.hermes/installs/019d0d114d22b7e6/environments/f1005c748ab046329d2857df237db84d/venv/bin/python /home/hermes/.hermes/skills/productivity/google-workspace/scripts/setup.py --auth-url
