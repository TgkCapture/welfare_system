#!/bin/sh
# Describe this server for planning the 3.0.0 deployment. Read-only: it
# changes nothing and prints no passwords or keys.
#
#   sh survey.sh > survey.txt 2>&1      (sudo gives fuller nginx and port details)
#
# Then send survey.txt back.

section() { printf '\n===== %s =====\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

section 'System'
. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"
uname -srm
echo "CPUs: $(nproc 2>/dev/null)"
free -h 2>/dev/null
df -h / /home /opt /srv /var 2>/dev/null | sort -u
swapon --show 2>/dev/null

section 'Containers'
for tool in docker podman; do
    have "$tool" && "$tool" --version
done
have docker && { docker compose version 2>/dev/null; docker ps --format '{{.Names}}  {{.Image}}  {{.Ports}}' 2>/dev/null; }

section 'Listening ports'
(ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null) | sed 's/users:.*pid=\([0-9]*\).*/pid=\1/'

section 'nginx'
if have nginx; then
    nginx -v 2>&1
    # Only the lines that say what is served where
    nginx -T 2>/dev/null | grep -E '^# configuration file|^\s*(listen|server_name|proxy_pass|root|ssl_certificate |include .*sites|return)\b'
else
    echo 'nginx not found'
fi

section 'Certificates'
have certbot && certbot --version 2>&1
ls /etc/letsencrypt/live 2>/dev/null

section 'Firewall'
have firewall-cmd && { firewall-cmd --state 2>&1; firewall-cmd --list-all 2>/dev/null; }
have ufw && ufw status 2>/dev/null
have iptables && iptables -S INPUT 2>/dev/null | head -30

section 'SELinux'
have getenforce && { getenforce; getsebool httpd_can_network_connect 2>/dev/null; } || echo 'SELinux tools not found'

section 'The old app'
ps -eo pid,user,args | grep -E 'gunicorn|run\.py|flask|waitress|uwsgi' | grep -v grep
systemctl list-units --type=service --no-pager 2>/dev/null | grep -i -E 'welfare|mzugoss|gunicorn|flask'
for dir in $(find /home /opt /srv /var/www /root -maxdepth 4 -name run.py -path '*welfare*' 2>/dev/null | xargs -r -n1 dirname); do
    echo "--- $dir"
    (cd "$dir" && git log -1 --format='commit %h %cd %s' 2>/dev/null && git branch --show-current 2>/dev/null)
    grep -h '__version__' "$dir/app/__init__.py" 2>/dev/null
    ls -la "$dir/instance" 2>/dev/null | grep -E '\.db|\.sqlite'
    ls -d "$dir"/venv "$dir"/.venv 2>/dev/null
done
find /home /opt /srv /var/www /root -maxdepth 5 \( -name '*.sqlite3' -o -name 'welfare*.db' \) 2>/dev/null

section 'Done'
