#!/bin/zsh
# The runtime key is entered through Python's hidden terminal prompt, never here.
cd -- "$(dirname -- "$0")" || exit 1

keystone_python=""
for keystone_candidate in "${KEYSTONE_PYTHON:-python3}" /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if "$keystone_candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    keystone_python="$keystone_candidate"
    break
  fi
done

if [[ -z "$keystone_python" ]]; then
  print 'Keystone needs Python 3.11 or newer. Install Python, then open this launcher again.'
  read -r 'keystone_reply?Press Return to close this window. '
  exit 1
fi

print 'Keystone · ChatGPT connection'
print 'Your runtime key will be hidden and kept only in memory.'
"$keystone_python" scripts/connect_chatgpt.py connect
keystone_exit=$?
if (( keystone_exit != 0 && keystone_exit != 130 )); then
  print 'The connection did not start. Review the message above, then try again.'
  read -r 'keystone_reply?Press Return to close this window. '
fi
exit "$keystone_exit"
