#!/bin/bash
set -e
shopt -s extglob

# Parse CLI
config_from_deployswitch=false
test_harness_opts=''

OPTIND=1
while getopts "d" opt; do
    case "$opt" in
        d)
            config_from_deployswitch=true
            ;;
        \?)
            ;;
    esac
done

shift $((OPTIND-1))
[ "%1" = "--" ] && shift

# Read config from deployswitch if asked for
if $config_from_deployswitch; then
    NORMAL_IFS="$IFS"
    IFS="="
    while read key val; do
        case "$key" in
            DS_*([a-zA-Z_]) )
                IFS="$NORMAL_IFS"
                declare $key="$val"  2>/dev/null || echo "Bad key"
                IFS="="
                ;;
            .)
                # A single '.' is the EOF marker
                break
                ;;
            *)
                echo "Bad key"
                ;;
        esac
    done
fi

# Basic prep
source bin/activate
mkdir -p logs

# Get the latest code (should be git checkout when we can)
OLD_COMMIT=$(git rev-parse HEAD)
if [ "$DS_DEPLOY_HASH" != "" ]; then
    git fetch
    git checkout "$DS_DEPLOY_HASH"
else
    git pull
fi
NEW_COMMIT=$(git rev-parse HEAD)
git submodule update --init

find . -name '*.pyc' -delete

# Sort out dependencies
trex/bin/install-deps.sh

# Install crontab
[ -f crontab ] && crontab crontab

# Compile static stuff
app compile_static

[ -f supervisord.conf ] && [[ -x bin/supervisorctl ]] && supervisorctl update

# Reload!
app wsgi_reload
