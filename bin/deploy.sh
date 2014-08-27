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

[ -f deploy.hook.pregit ] && source deploy.hook.pregit

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

[ -f deploy.hook.predeps ] && source deploy.hook.predeps

# Sort out dependencies
trex/bin/install-deps.sh

[ -f deploy.hook.precron ] && source deploy.hook.precron

# Install crontab
[ -f crontab ] && crontab crontab

[ -f deploy.hook.prestatic ] && source deploy.hook.prestatic

# Compile static stuff
app compile_static

[ -f deploy.hook.presupervisor ] && source deploy.hook.presupervisor

[ -f supervisord.conf ] && [[ -x bin/supervisorctl ]] && supervisorctl update

[ -f deploy.hook.prereload ] && source deploy.hook.prereload

# Reload!
app wsgi_reload
