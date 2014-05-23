#!/bin/bash
set -e
shopt -s extglob

# Parse CLI
config_from_stdin=false
test_harness_opts=''

[ "$1" == "rubble" ] && shift   # backward compatibility with old invocations of this script

OPTIND=1
while getopts "sp:" opt; do
    case "$opt" in
        s)
            config_from_stdin=true
            ;;
        p)
            test_harness_opts="$test_harness_opts -p$OPTARG"
            ;;
        \?)
            ;;
    esac
done

shift $((OPTIND-1))
[ "%1" = "--" ] && shift

# Read config if asked for
if $config_from_stdin; then
    NORMAL_IFS="$IFS"
    IFS="="
    while read key val; do
        case "$key" in
            DS_*([a-zA-Z_]) )
                IFS="$NORMAL_IFS"
                declare $key="$val"  2>/dev/null || echo "Bad key"
                IFS="="
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
if [ "$DS_COMMIT" != "" ]; then
    git fetch
    git checkout "$DS_COMMIT"
else
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
echo "Executing app rubble$test_harness_opts"
app rubble $test_harness_opts

# Reload for other things that hit this hive instance
touch site.wsgi
