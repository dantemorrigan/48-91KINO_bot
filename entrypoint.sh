#!/bin/sh
set -e

if [ -n "$DATA_DIR" ] && [ -d "$DATA_DIR" ]; then
    chown -R app:app "$DATA_DIR" 2>/dev/null || true
fi

exec python3 -c "
import os, pwd
u = pwd.getpwnam('app')
os.setgid(u.pw_gid)
os.setuid(u.pw_uid)
os.execvp('python', ['python', 'main.py'])
"
