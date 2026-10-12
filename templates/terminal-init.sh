# Device-local profile paths and the chosen Python are prepended by setup_device.py.
# Homebrew on Apple Silicon or Intel; Linux keeps its normal system tool paths.
if [ -d /opt/homebrew/bin ]; then
    export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"
elif [ -d /usr/local/Homebrew ]; then
    export PATH="/usr/local/bin:/usr/local/sbin:$PATH"
fi
# Select an actually installed UTF-8 locale rather than assuming macOS names.
_hermes_utf8=$(locale -a 2>/dev/null | awk 'tolower($0) ~ /^(c|en_us)\.(utf-?8)$/ { print; exit }')
if [ -n "$_hermes_utf8" ]; then
    export LANG="$_hermes_utf8"
    export LC_ALL="$_hermes_utf8"
fi
unset _hermes_utf8
