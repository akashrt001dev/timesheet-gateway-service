#!/bin/bash

################################################################################
# Gateway Service Startup Script
# Manages start, stop, restart, and status operations
################################################################################

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"  # Script is in project root
PID_FILE="$PROJECT_DIR/.gateway.pid"
LOG_FILE="$PROJECT_DIR/gateway.log"
MODULE="app.main:app"

# Python detection - use PYTHON_PATH if set, otherwise auto-detect
if [ -z "$PYTHON_PATH" ]; then
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "Error: Python is not installed or not in PATH"
        echo "Please install Python 3.8+ or set PYTHON_PATH environment variable"
        exit 1
    fi
else
    PYTHON_CMD="$PYTHON_PATH"
fi

################################################################################
# Functions
################################################################################

print_usage() {
    cat << EOF
Usage: $0 {start|stop|restart|status|logs|build|health}

Commands:
    build               - Build server
    start               - Start the gateway service
    stop                - Stop the gateway service
    restart             - Restart the gateway service
    status              - Check service status
    logs                - Show last 30 lines of logs
    logs follow         - Follow logs in real-time
    health              - Health check

Environment Variables:
    SERVER_PORT          - Server port (default: 8000)
    SERVER_HOST          - Server host (default: 0.0.0.0)
    ENVIRONMENT          - Environment (local, dev, qa, uat, prod)
    PYTHON_PATH          - Python interpreter path (default: python)

Examples:
    sudo $0 build
    sudo $0 start
    SERVER_PORT=9000 sudo $0 start
    sudo $0 stop
    sudo $0 restart
    sudo $0 status
    sudo $0 logs
    sudo $0 logs follow
    sudo $0 health

EOF
    exit 1
}

ensure_venv() {
    # Verify Python is available and working
    if ! command -v "$PYTHON_CMD" &> /dev/null; then
        echo "Error: Python command '$PYTHON_CMD' not found"
        echo "Please install Python 3.8+ or set PYTHON_PATH environment variable"
        exit 1
    fi

    # Check Python version
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
    echo "Using $PYTHON_VERSION"

    if [ ! -d "$PROJECT_DIR/venv" ]; then
        echo "Creating Python virtual environment..."
        if ! $PYTHON_CMD -m venv "$PROJECT_DIR/venv"; then
            echo "Error: Failed to create virtual environment"
            exit 1
        fi
    fi

    if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
        source "$PROJECT_DIR/venv/bin/activate"
    elif [ -f "$PROJECT_DIR/venv/Scripts/activate" ]; then
        source "$PROJECT_DIR/venv/Scripts/activate"
    fi
}

install_dependencies() {
    echo "Installing Python dependencies..."
    pip install -q -r "$PROJECT_DIR/requirements.txt"
}

start_service() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Service is already running (PID: $PID)"
            return 0
        else
            rm -f "$PID_FILE"
        fi
    fi

    echo "Starting gateway service..."
    ensure_venv
    install_dependencies

    # Start service in background
    nohup $PYTHON_CMD -m uvicorn $MODULE \
        --host "${SERVER_HOST:-0.0.0.0}" \
        --port "${SERVER_PORT:-8000}" \
        --log-level "${LOG_LEVEL:-info}" \
        > "$LOG_FILE" 2>&1 &

    PID=$!
    echo $PID > "$PID_FILE"

    # Wait for service to start
    sleep 2

    if kill -0 "$PID" 2>/dev/null; then
        echo "Service started successfully (PID: $PID)"
        echo "Port: ${SERVER_PORT:-8000}"
        echo "Logs: $LOG_FILE"
        return 0
    else
        echo "Failed to start service"
        cat "$LOG_FILE"
        return 1
    fi
}

stop_service() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Service is not running"
        return 0
    fi

    PID=$(cat "$PID_FILE")

    if ! kill -0 "$PID" 2>/dev/null; then
        echo "Service is not running (stale PID file)"
        rm -f "$PID_FILE"
        return 0
    fi

    echo "Stopping service (PID: $PID)..."
    kill -TERM "$PID" 2>/dev/null || true

    # Wait for graceful shutdown
    for i in {1..30}; do
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "Service stopped successfully"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 1
    done

    # Force kill if graceful shutdown fails
    echo "Force killing service..."
    kill -9 "$PID" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "Service stopped"
    return 0
}

status_service() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Service is not running"
        return 1
    fi

    PID=$(cat "$PID_FILE")

    if kill -0 "$PID" 2>/dev/null; then
        echo "Service is running (PID: $PID)"
        return 0
    else
        echo "Service is not running (stale PID file)"
        rm -f "$PID_FILE"
        return 1
    fi
}

show_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo "Log file not found: $LOG_FILE"
        return 1
    fi

    # Check if "follow" argument is provided
    if [ "$2" = "follow" ]; then
        tail -f "$LOG_FILE"
    else
        # Show last 30 lines by default
        tail -n 30 "$LOG_FILE"
    fi
}

build_service() {
    echo "Building server..."
    ensure_venv
    install_dependencies
    echo "Server build completed successfully"
}

health_check() {
    PORT="${SERVER_PORT:-8000}"
    HOST="${SERVER_HOST:-0.0.0.0}"
    
    echo "Performing health check on http://$HOST:$PORT/health"
    
    if ! kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
        echo "Service is not running"
        return 1
    fi

    # Try to reach the health endpoint
    if command -v curl &> /dev/null; then
        RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:$PORT/health 2>/dev/null || echo -e "\n000")
        HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
        BODY=$(echo "$RESPONSE" | sed '$d')
        
        if [ "$HTTP_CODE" = "200" ]; then
            echo "Health check passed (HTTP $HTTP_CODE)"
            echo "Response: $BODY"
            return 0
        else
            echo "Health check failed (HTTP $HTTP_CODE)"
            echo "Response: $BODY"
            return 1
        fi
    else
        echo "curl not found. Checking if service is running..."
        status_service
        return $?
    fi
}

restart_service() {
    echo "Restarting service..."
    stop_service
    sleep 1
    start_service
}

################################################################################
# Main
################################################################################

if [ $# -eq 0 ]; then
    print_usage
fi

case "$1" in
    build)
        build_service
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        status_service
        ;;
    logs)
        show_logs "$@"
        ;;
    health)
        health_check
        ;;
    *)
        echo "Unknown command: $1"
        print_usage
        ;;
esac
