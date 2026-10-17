# Shared fail-closed cutout check. Caller supplies ADB and serial.
# Return success only when the display or its fallback overlay proves no cutout.
cutout_disabled() {
    local display line overlays state
    display="$("$ADB" -s "$serial" shell dumpsys display 2>/dev/null)" || return 1
    line="$(printf '%s\n' "$display" | grep -m1 'DisplayDeviceInfo{"Built-in Screen"' || true)"
    if [[ -n "$line" ]]; then
        if [[ "$line" != *cutout* ]]; then
            return 0
        fi
        [[ "$line" == *'cutout DisplayCutout{insets=Rect(0, 0 - 0, 0)'* ]]
        return
    fi
    overlays="$("$ADB" -s "$serial" shell cmd overlay list android 2>/dev/null)" || return 1
    state="$(printf '%s\n' "$overlays" | tr -d '\r' | grep -F 'com.android.internal.emulation.pixel_7' || true)"
    [[ "$state" == '[ ] com.android.internal.emulation.pixel_7' ]]
}
