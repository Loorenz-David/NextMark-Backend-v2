#!/bin/bash

set -e 

WEB_ENV="nextmarkapp-prod"
WORKER_ENV="nextmark-workers"
SCHEDULER_ENV="nextmark-scheduler"
DISPATCHER_ENV="nextmarkapp-dispatcher"

echo "Deploying to web environment..."
eb use $WEB_ENV
eb deploy 

echo "Fetching latest version label..."
VERSION=$(eb status $WEB_ENV | grep "Deployed Version" | awk '{print $3}')

echo "Latest version: $VERSION"

echo "Deploying same version to workers and schedulers..."
eb deploy $WORKER_ENV --version $VERSION & 
WORKER_PID=$!

eb deploy $SCHEDULER_ENV --version $VERSION &
SCHED_PID=$!

eb deploy $DISPATCHER_ENV --version $VERSION &
DISPATCH_PID=$!

wait $WORKER_PID
wait $SCHED_PID
wait $DISPATCH_PID

echo "Deployment completed for all environments."