color_prompt=yes
uh_color=33
wd_color=34
if [ "$color_prompt" = yes ]; then
    PS1='\[\033[01;'$uh_color'm\]\u@docker:\h\[\033[00m\] - \[\033[01;'$wd_color'm\]\w\[\033[00m\]\n\$ '
else
    PS1='\u@docker:\h - \w\n\$ '
fi

export PATH=/home/amdar/bin:/home/amdar/frontend/node_modules/.bin:$PATH
export PYTHONPATH=/home/amdar/backend
export TERM=xterm

# If this is an xterm set the title to user@host:dir
case "$TERM" in
xterm*|rxvt*)
    PS1="\[\e]0;docker:\u@\h: \w\a\]$PS1"
    ;;
*)
    ;;
esac
