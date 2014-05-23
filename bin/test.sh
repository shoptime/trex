#!/bin/bash
set -e
shopt -s extglob

# Parse CLI
config_from_deployswitch=false
parallel=''

[ "$1" == "rubble" ] && shift   # backward compatibility with old invocations of this script

OPTIND=1
while getopts "dp:" opt; do
    case "$opt" in
        d)
            config_from_deployswitch=true
            ;;
        p)
            parallel="$OPTARG"
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

# Get the latest code
if [ "$DS_DEPLOY_HASH" != "" ]; then
    echo "Fetching and checking out $DS_DEPLOY_HASH"
    git fetch
    git checkout "$DS_DEPLOY_HASH"
else
    echo "Pulling latest head"
    git pull
fi

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
test_harness_opts=''
if [ $parallel ]; then
    test_harness_opts="$test_harness_opts -p3"
fi
app rubble $test_harness_opts

# Reload for other things that hit this hive instance
touch site.wsgi
