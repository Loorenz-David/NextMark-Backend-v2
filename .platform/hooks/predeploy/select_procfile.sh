#!/bin/bash
set -e

echo "Selecting Procfile based on APP_ROLE=$APP_ROLE"

case "$APP_ROLE" in
  worker)
    echo "Using Procfile.worker"
    cp Procfile.worker Procfile
    ;;

  scheduler)
    echo "Using Procfile.scheduler"
    cp Procfile.scheduler Procfile
    ;;
  dispatcher)
    echo "Using Procfile.dispatcher"
    cp Procfile.dispatcher Procfile   
    ;;
  web|"")
    echo "Using default Procfile (web)"
    ;;

  *)
    echo "Unknown APP_ROLE: $APP_ROLE"
    exit 1
    ;;
esac