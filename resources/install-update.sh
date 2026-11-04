#!/bin/bash
set -euo pipefail
old_pid="$1"; target="$2"; staged="$3"; previous="$4"; health="$5"; expected="$6"; data="$7"; exports="$8"
parent="$(dirname "$target")"
[[ "$(basename "$target")" == 'StarPower Content Studio.app' ]] || exit 1
[[ "$(dirname "$staged")" == "$parent" && "$(basename "$staged")" == .starpower-incoming-* ]] || exit 1
[[ "$(dirname "$previous")" == "$parent" && "$(basename "$previous")" == .starpower-previous-* ]] || exit 1
deadline=$((SECONDS+180))
while kill -0 "$old_pid" 2>/dev/null; do
  (( SECONDS < deadline )) || exit 1
  sleep 0.3
done
export STUDIO_DATA_DIR="$data" STUDIO_EXPORT_DIR="$exports" PYINSTALLER_RESET_ENVIRONMENT=1
new_pid=''
rollback() {
  trap - ERR
  if [[ -n "$new_pid" ]] && kill -0 "$new_pid" 2>/dev/null; then kill "$new_pid"; wait "$new_pid" 2>/dev/null || true; fi
  if [[ -d "$previous" ]]; then
    if [[ -d "$target" ]]; then mv "$target" "$parent/.starpower-failed-$(/usr/bin/uuidgen)"; fi
    mv "$previous" "$target"
    nohup "$target/Contents/MacOS/StarPower Content Studio" >/dev/null 2>&1 &
  fi
  echo 'Rolled back app only; current history preserved.' > "$(dirname "$health")/result.txt"
}
trap rollback ERR
mv "$target" "$previous"
mv "$staged" "$target"
nohup "$target/Contents/MacOS/StarPower Content Studio" --update-health "$health" >/dev/null 2>&1 &
new_pid=$!
deadline=$((SECONDS+90))
healthy=0
while (( SECONDS < deadline )) && kill -0 "$new_pid" 2>/dev/null; do
  if [[ -f "$health" ]]; then
    actual=$(/usr/bin/plutil -extract version raw -o - "$health" 2>/dev/null || true)
    passed=$(/usr/bin/plutil -extract passed raw -o - "$health" 2>/dev/null || true)
    app_path=$(/usr/bin/plutil -extract appPath raw -o - "$health" 2>/dev/null || true)
    if [[ "$actual" == "$expected" && "$passed" == true && "$app_path" == "$target" ]]; then healthy=1; break; fi
  fi
  sleep 0.5
done
[[ "$healthy" == 1 ]] || false
trap - ERR
echo "Update installed; previous app retained at $previous" > "$(dirname "$health")/result.txt"
