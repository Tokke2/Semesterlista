# POSIX bootstrap payload. Launchers normalize CRLF before passing this to sh.
# No Python, pip, sudo or third-party shell module is required to show the offer.
ROOT=$1
SYSTEM=$(uname -s)
PYTHON=
SEEN=0
BREW=$(command -v brew 2>/dev/null) || BREW=
if [ -z "$BREW" ]; then
    for path in /opt/homebrew/bin/brew /usr/local/bin/brew; do
        if [ -x "$path" ]; then BREW=$path; break; fi
    done
fi

message() {
    text=$1
    if [ "$SYSTEM" = Darwin ]; then
        /usr/bin/osascript -e 'on run argv' -e 'display dialog (item 1 of argv) with title "Semesterlista" buttons {"OK"} default button "OK"' -e 'end run' "$text" >/dev/null 2>&1
    elif command -v zenity >/dev/null 2>&1; then
        zenity --error --no-markup --title=Semesterlista --text="$text" 2>/dev/null
    elif command -v kdialog >/dev/null 2>&1; then
        kdialog --title Semesterlista --error "$text" 2>/dev/null
    elif command -v xmessage >/dev/null 2>&1; then
        xmessage "$text" 2>/dev/null
    fi
    return 0
}

confirm() {
    text=$1
    if [ "$SYSTEM" = Darwin ]; then
        answer=$(/usr/bin/osascript -e 'on run argv' -e 'set answer to display dialog (item 1 of argv) with title "Semesterlista" buttons {"Nej", "Ja"} default button "Nej" cancel button "Nej"' -e 'return button returned of answer' -e 'end run' "$text" 2>/dev/null) || return 1
        [ "$answer" = Ja ]
    elif command -v zenity >/dev/null 2>&1; then
        zenity --question --default-cancel --no-markup --title=Semesterlista --text="$text" --ok-label=Ja --cancel-label=Nej 2>/dev/null
    elif command -v kdialog >/dev/null 2>&1; then
        kdialog --title Semesterlista --warningyesno "$text" --defaultno 2>/dev/null
    else
        # No graphical confirmation available: never infer installation consent.
        fail 'Python saknas och ingen dialogfunktion finns. Installera Python via operativsystemets pakethanterare och starta igen.'
        return 1
    fi
}

fail() {
    mkdir -p "$ROOT/data/loggar" 2>/dev/null
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$ROOT/data/loggar/fel.log"
    message "$1"
}

probe() {
    candidate=$1
    [ -e "$candidate" ] || [ -L "$candidate" ] || return 1
    # Apple's command-line-tools shim is not an installed Python interpreter.
    if [ "$SYSTEM" = Darwin ] && [ "$candidate" = /usr/bin/python3 ]; then
        /usr/bin/xcode-select -p >/dev/null 2>&1 || return 1
    fi
    SEEN=1
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) and sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then
        PYTHON=$candidate
        return 0
    fi
    return 1
}

find_python() {
    PYTHON=
    SEEN=0
    for name in python3.15 python3.14 python3 python python3.13 python3.12 python3.11 python3.10 python2; do
        found=$(command -v "$name" 2>/dev/null) || found=
        if [ -n "$found" ]; then probe "$found" && return 0; fi
        for folder in /opt/homebrew/bin /usr/local/bin /usr/bin; do
            probe "$folder/$name" && return 0
        done
    done
    for candidate in /Library/Frameworks/Python.framework/Versions/*/bin/python3 /opt/homebrew/opt/python*/bin/python3 /usr/local/opt/python*/bin/python3; do
        probe "$candidate" && return 0
    done
    # Do not offer a second copy if a package exists but its executable is broken.
    if command -v dpkg-query >/dev/null 2>&1; then
        state=$(dpkg-query -W -f='${Status}' python3 2>/dev/null) || state=
        [ "$state" = 'install ok installed' ] && SEEN=1
    fi
    if command -v rpm >/dev/null 2>&1; then rpm -q python3 >/dev/null 2>&1 && SEEN=1; fi
    if [ -n "$BREW" ]; then
        "$BREW" list --formula 2>/dev/null | grep -Eq '^python(@|$)' && SEEN=1
    fi
    return 1
}

install_missing_python() {
    if [ "$SYSTEM" = Darwin ]; then
        if [ -n "$BREW" ]; then
            confirm 'Python saknas helt. Installera senaste stabila Python via befintlig Homebrew? Befintlig Python uppdateras aldrig.' || return 2
            HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_UPGRADE=1 "$BREW" install python
        else
            confirm 'Python saknas helt. Öppna den officiella sidan för senaste stabila Python? Slutför installationen där och starta sedan Semesterlista igen.' || return 2
            /usr/bin/open https://www.python.org/downloads/macos/
            return 2
        fi
    elif command -v pkexec >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
        confirm 'Python saknas helt. Installera distributionens senaste tillgängliga Python 3 via apt? Administratörsgodkännande krävs. Systemets Python ersätts inte med en annan version.' || return 2
        pkexec apt-get install -y python3
    elif command -v pkexec >/dev/null 2>&1 && command -v dnf >/dev/null 2>&1; then
        confirm 'Python saknas helt. Installera distributionens senaste tillgängliga Python 3 via dnf? Administratörsgodkännande krävs.' || return 2
        pkexec dnf install -y python3
    else
        message 'Python saknas. Installera Python 3 med distributionens pakethanterare och starta sedan igen. Inget har installerats eller uppdaterats.'
        return 2
    fi
}

main() {
    if find_python; then
        exec "$PYTHON" "$ROOT/tools/runtime_check.py"
    fi
    if [ "$SEEN" -ne 0 ]; then
        fail 'Python finns men kunde inte startas eller stöds inte (kräver 3.10+). Reparera den befintliga installationen. Ingen extra Python installeras.'
        return 1
    fi
    log=$(mktemp) || return 1
    install_missing_python >"$log" 2>&1
    code=$?
    if [ "$code" -eq 2 ]; then rm -f "$log"; return 0; fi
    if [ "$code" -ne 0 ]; then
        mkdir -p "$ROOT/data/loggar"
        cat "$log" >> "$ROOT/data/loggar/fel.log"
        rm -f "$log"
        fail 'Python-installationen misslyckades. Se data/loggar/fel.log. Ingen uppdatering av befintlig Python görs.'
        return 1
    fi
    rm -f "$log"
    if find_python; then exec "$PYTHON" "$ROOT/tools/runtime_check.py"; fi
    fail 'Python hittades inte efter installationen. Starta om startfilen. Ingen ytterligare installation görs nu.'
    return 1
}

if [ "${SEMESTERLISTA_BOOTSTRAP_TEST:-}" != functions ]; then main; fi
