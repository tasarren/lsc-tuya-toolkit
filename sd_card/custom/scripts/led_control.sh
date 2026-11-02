#!/bin/sh
# This script tries to unify the three main led control scripts located in /usr/sbin
# This may not work in your camera but who knows

# USAGE:
# ./led.sh red on
# ./led.sh red on 1
# ./led.sh blue off
# ./led.sh state blink
# ./led.sh state blink 200 300

led_name=$1
action=$2
arg1=$3
arg2=$4

default_brightness=1
default_delay=100

usage() {
    echo "Usage:"
    echo "  $0 {red|blue|state} on [brightness]"
    echo "  $0 {red|blue|state} off"
    echo "  $0 {red|blue|state} blink [delay_off] [delay_on]"
    exit 1
}

get_led_path() {
    case "$led_name" in
        red)   led_path="/sys/class/leds/red_led" ;;
        blue)  led_path="/sys/class/leds/blue_led" ;;
        state) led_path="/sys/class/leds/state_led" ;;
        *) usage ;;
    esac
}

set_trigger_none() {
    echo none > "$led_path/trigger"
}

led_on() {
    brightness=${1:-$default_brightness}
    set_trigger_none
    echo "$brightness" > "$led_path/brightness"
}

led_off() {
    set_trigger_none
    echo 0 > "$led_path/brightness"
}

led_blink() {
    delay_off=${1:-$default_delay}
    delay_on=${2:-$default_delay}

    current=$(cat "$led_path/brightness" 2>/dev/null)
    [ "$current" = "0" ] && led_on "$default_brightness"

    echo timer > "$led_path/trigger"
    echo "$delay_off" > "$led_path/delay_off"
    echo "$delay_on" > "$led_path/delay_on"
}

[ $# -ge 2 ] || usage

get_led_path

case "$action" in
    on)
        led_on "$arg1"
        ;;
    off)
        led_off
        ;;
    blink)
        led_blink "$arg1" "$arg2"
        ;;
    *)
        usage
        ;;
esac

exit 0