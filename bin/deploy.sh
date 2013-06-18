#!/bin/bash
set -e

# Basic prep
source bin/activate
mkdir -p logs

# Get the latest code (should be git checkout when we can)
OLD_COMMIT=$(git rev-parse HEAD)
git pull
NEW_COMMIT=$(git rev-parse HEAD)
git submodule update --init

find . -name '*.pyc' -delete

# Sort out dependencies
trex/bin/install-deps.sh

# Install crontab
crontab crontab

# Compile static stuff
app compile_static

supervisorctl update

# Reload!
touch site.wsgi
