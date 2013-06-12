#!/bin/bash

set -e

PROJECT_ROOT=$(cd $(dirname "$0")/../..; pwd)

cd "$PROJECT_ROOT"
. bin/activate

for file in {,trex/}requirements.txt; do [ -f $file ] && pip install -r $file; done
if [ "$1" == "-d" ]; then
    pip install -r trex/dev-requirements.txt
fi

mkdir -p node_modules
for file in {,trex/}node-requirements.txt; do
    if [ -f $file ]; then
        xargs npm install <$file
    fi
done

for script in node_modules/.bin/*; do
    script=$(basename $script)
    ln -f -s ../node_modules/.bin/lessc bin/
done

exit 0
