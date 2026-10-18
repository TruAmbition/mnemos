#!/bin/zsh
# The runtime key is entered through Python's hidden terminal prompt, never here.
cd -- "$(dirname -- "$0")" || exit 1

mnemos_python=""
for mnemos_candidate in "${MNEMOS_PYTHON:-${KEYSTONE_PYTHON:-python3}}" /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if "$mnemos_candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    mnemos_python="$mnemos_candidate"
    break
  fi
done

if [[ -z "$mnemos_python" ]]; then
  print 'Mnemos needs Python 3.11 or newer. Install Python, then open this launcher again.'
  read -r 'mnemos_reply?Press Return to close this window. '
  exit 1
fi

print 'Mnemos · ChatGPT connection'
print 'Your runtime key will be hidden and kept only in memory.'
"$mnemos_python" scripts/connect_chatgpt.py connect
mnemos_exit=$?
if (( mnemos_exit != 0 && mnemos_exit != 130 )); then
  print 'The connection did not start. Review the message above, then try again.'
  read -r 'mnemos_reply?Press Return to close this window. '
fi
exit "$mnemos_exit"
