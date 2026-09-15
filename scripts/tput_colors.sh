#!/bin/bash
for i in {0..255}; do
    tput setaf $i
    printf "%4d" $i
    if [ $((($i + 1) % 16)) -eq 0 ]; then
        tput sgr0
        echo
    fi
done
tput sgr0

