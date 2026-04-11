echo "# relaunch.sh"

echo "Restarting services..."
sudo systemctl restart nextmark-*
echo "Done ✅"