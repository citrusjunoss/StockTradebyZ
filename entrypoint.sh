#!/bin/bash

if [ "$1" = "scheduler" ]; then
    echo "Starting scheduler mode..."
    python scheduler.py
elif [ "$1" = "once" ]; then
    echo "Running stock selection once..."
    python select_stock.py
elif [ "$1" = "web" ]; then
    echo "Starting web server..."
    python web_server.py --host 0.0.0.0 --port 8080
elif [ "$1" = "web-debug" ]; then
    echo "Starting web server in debug mode..."
    python web_server.py --host 0.0.0.0 --port 8080 --debug
else
    echo "Running with custom arguments: $@"
    exec "$@"
fi