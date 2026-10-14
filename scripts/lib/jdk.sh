# shellcheck shell=bash
# jdk.sh -- JAVA_HOME for the Ghidra tools. Sourced. Homebrew's openjdk is keg-only, so there is no
# `java` on the PATH even when it is installed: $JAVA_HOME, then brew's prefix, then the known brew
# paths of both Mac architectures, then the system JDK.

java_home_path() {
    if [ -n "${JAVA_HOME:-}" ]; then
        printf "%s\n" "$JAVA_HOME"
        return 0
    fi
    if command -v brew >/dev/null 2>&1; then
        p=$(brew --prefix openjdk 2>/dev/null)
        if [ -n "$p" ] && [ -d "$p" ]; then
            printf "%s\n" "$p"
            return 0
        fi
    fi
    for j in /opt/homebrew/opt/openjdk /usr/local/opt/openjdk; do
        if [ -d "$j" ]; then
            printf "%s\n" "$j"
            return 0
        fi
    done
    /usr/libexec/java_home 2>/dev/null
}

# require_jdk: exports JAVA_HOME, or says there is no JDK and returns 1.
require_jdk() {
    JAVA_HOME=$(java_home_path) || JAVA_HOME=""
    if [ -z "$JAVA_HOME" ]; then
        echo "ERROR: no JDK found. Install one: brew install openjdk" >&2
        return 1
    fi
    export JAVA_HOME
}
