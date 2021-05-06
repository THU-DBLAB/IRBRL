#!/bin/bash

FILE=$1
#GREP_COLOR
#https://askubuntu.com/questions/1042234/modifying-the-color-of-grep
shopt -s expand_aliases
alias grey-grep="GREP_COLOR='1;30' grep -E --color=always --line-buffered"
alias red-grep="GREP_COLOR='1;31' grep -E --color=always --line-buffered"
alias red-white-grep="GREP_COLOR='1;31;107' grep -E --color=always --line-buffered"

alias green-grep="GREP_COLOR='1;32' grep -E --color=always --line-buffered"
alias yellow-grep="GREP_COLOR='1;33' grep -E --color=always --line-buffered"
alias cyan-grep="GREP_COLOR='1;36' grep -E --color=always --line-buffered"

tail -1000f utils/log_file/$FILE |green-grep "DEBUG|" | cyan-grep "INFO|" | yellow-grep "WARNING|" | red-grep "ERROR|"|red-white-grep "CRITICAL|"