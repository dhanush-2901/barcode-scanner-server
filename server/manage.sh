#!/bin/bash
# Quick management commands for the license server on GCE
# Usage: bash manage.sh [status|restart|logs|show-key|stop]

SERVICE="barcode-scanner"
ENV_FILE="/opt/barcode-scanner/.env"

case "$1" in
  status)
    sudo systemctl status $SERVICE --no-pager
    ;;
  restart)
    sudo systemctl restart $SERVICE
    echo "Restarted."
    ;;
  logs)
    sudo journalctl -u $SERVICE -n 100 --no-pager
    ;;
  show-key)
    echo "API Key    : $(grep '^API_KEY=' $ENV_FILE | cut -d= -f2)"
    echo "Admin pass : $(grep '^ADMIN_PASSWORD=' $ENV_FILE | cut -d= -f2)"
    ;;
  stop)
    sudo systemctl stop $SERVICE
    echo "Stopped."
    ;;
  *)
    echo "Usage: bash manage.sh [status|restart|logs|show-key|stop]"
    ;;
esac
