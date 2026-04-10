# Firestore エミュレータ用: Homebrew/cask なしで入れた Temurin JDK 21 のパスを通す。
# 使い方: source scripts/local_jdk.sh
# shellcheck disable=SC3046
_JDK_ROOT="${LOCAL_JDK_HOME:-$HOME/.local/share/temurin-jdk-21/Contents/Home}"
if [ -x "$_JDK_ROOT/bin/java" ]; then
  export JAVA_HOME="$_JDK_ROOT"
  export PATH="$JAVA_HOME/bin:$PATH"
else
  echo "local_jdk.sh: JDK not found at $_JDK_ROOT (expected Temurin tarball layout)." >&2
  return 1 2>/dev/null || exit 1
fi
unset _JDK_ROOT
