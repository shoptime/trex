#!/bin/bash

set -e

ROOT=$(dirname $(dirname $(dirname $0)))

(
    cd "$ROOT/trex"
    git pull
)

(
    cd "$ROOT"
    . bin/activate
    python -c 'from trex.self_tests import tests; tests.main()' "$@"
)

