#!/bin/bash

# Create credentials directory inside staging
mkdir -p /var/app/current/credentials

# Write JSON from environment variable into a file
echo "$GOOGLE_APPLICATION_JSON" > /var/app/current/credentials/google_service_account.json

# Set secure permissions
chmod 600 /var/app/current/credentials/google_service_account.json

chown webapp:webapp /var/app/current/credentials/google_service_account.json