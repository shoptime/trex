#!/bin/bash
set -e

if [ "$1" == "" ]; then
    test_harness='test'
else
    test_harness="$1"
fi

# Basic prep
source bin/activate
mkdir -p logs

# Get the latest code (should be git checkout when we can)
git pull

TREX_OLD_COMMIT=$(cd trex && git rev-parse HEAD)
git submodule update --init
TREX_NEW_COMMIT=$(cd trex && git rev-parse HEAD)

if [[ "$TREX_OLD_COMMIT" != "$TREX_NEW_COMMIT" ]] && [[ "$(cd trex && git merge-base $TREX_OLD_COMMIT $TREX_NEW_COMMIT)" == "$TREX_NEW_COMMIT" ]]; then
    echo "STOP: trex appears to have gone backward!";
    echo "Old commit $TREX_OLD_COMMIT, new commit $TREX_NEW_COMMIT"
    ( cd trex && git checkout $TREX_OLD_COMMIT )
    exit 1
fi

find . -name '*.pyc' -delete

# Sort out dependencies
bash trex/bin/install-deps.sh

# Compile static stuff
app compile_static

# Run tests
echo "Executing app $test_harness" "${*:2}"
if [ "$2" != "" ]; then
    app "$test_harness" "${*:2}"
else
    app "$test_harness"
fi

# Reload for other things that hit this hive instance
touch site.wsgi
