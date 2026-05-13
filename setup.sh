#!/usr/bin/env bash
# Bootstrap developer toolchains for french-rain-radar.
# Idempotent — safe to re-run.
set -euo pipefail

cd "$(dirname "$0")"

# ----- uv (Python package manager) -----
if ! command -v uv >/dev/null 2>&1; then
    echo "[setup] installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # shellcheck disable=SC1090
    [ -f "$HOME/.local/bin/env" ] && source "$HOME/.local/bin/env" || export PATH="$HOME/.local/bin:$PATH"
fi
echo "[setup] uv: $(uv --version)"

# ----- Backend Python deps -----
echo "[setup] syncing backend Python deps..."
(cd backend && uv sync)

# ----- Gradle wrapper -----
WRAPPER_JAR="client/gradle/wrapper/gradle-wrapper.jar"
WRAPPER_VERSION="8.11.1"
if [ ! -f "$WRAPPER_JAR" ]; then
    echo "[setup] downloading Gradle wrapper jar v$WRAPPER_VERSION..."
    curl -fsSL -o "$WRAPPER_JAR" \
        "https://raw.githubusercontent.com/gradle/gradle/v${WRAPPER_VERSION}/gradle/wrapper/gradle-wrapper.jar"
fi
chmod +x client/gradlew 2>/dev/null || true

# ----- JDK check -----
if ! command -v java >/dev/null 2>&1; then
    cat <<'EOF'

[setup] WARNING: no `java` on PATH. The client build needs JDK 21.
        Install via SDKMAN (recommended) or apt:
            curl -s https://get.sdkman.io | bash
            sdk install java 21.0.5-tem
          — or —
            sudo apt install openjdk-21-jdk

EOF
fi

# ----- Android SDK note -----
if [ -z "${ANDROID_HOME:-}" ] && [ -z "${ANDROID_SDK_ROOT:-}" ]; then
    echo "[setup] note: ANDROID_HOME/ANDROID_SDK_ROOT not set — Android build will fail until you install Android Studio or sdkmanager."
fi

echo "[setup] done."
echo "        Next:  make fake-data && make dev-caddy"
