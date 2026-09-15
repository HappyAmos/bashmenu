msg=" "; for i in {0..255}; do printf "\x1b[38;5;${i}m%4d" $i; if [ $((($i + 1) % 16)) -eq 0 ]; then echo; fi; done
