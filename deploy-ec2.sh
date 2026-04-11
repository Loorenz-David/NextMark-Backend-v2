# deploy.sh

set -e

echo "Pulling latest code..."
git pull origin main

echo "Activating venv..."
source .venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

echo "loading envs..."
set -a
source .env
set +a

echo "Running migrations..."
export FLASK_APP=application.py
flask db upgrade

echo "Reloading services..."
sudo systemctl daemon-reload
sudo systemctl restart nextmark-*

echo "Deployment complete ✅"