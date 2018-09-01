#!/usr/bin/env bash
prompt() {
    color=33
    echo -e '>>> \033[01;'$color'm'$1'\033[00m <<<'
}

prompt "Starting webserver"
nginx
prompt "Starting Django"
uwsgi --ini /home/balloon/uwsgi.ini
