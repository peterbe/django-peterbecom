#!/usr/bin/env bash
set -eo pipefail

# This is used to make sure that before you start huey, there isn't already
# one running the background.
# It has happened that huey gets lingering stuck as a ghost and it's hard
# to notice it sitting there lurking and being weird.

bad() {
    echo "Huey is already running!"
    exit 1
}

good() {
    echo "Huey is NOT already running"
    exit 0
}

ps aux | rg huey | rg -v 'rg huey' | rg -v 'huey-isnt-running.sh' && bad || good
