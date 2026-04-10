# dev_all.sh
#!/bin/bash

echo "Starting web..."
python run.py &

echo "Starting dispatcher..."
python redis_dispatcher.py &

echo "Starting IO worker..."
python redis_worker_io.py &

echo "Starting default worker..."
python redis_worker_default.py &

echo "Starting event clean up manager..."
python event_cleanup_manager.py &

wait