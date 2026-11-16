#!/bin/sh
# Descarga el compilador `sal` desde una release de GitHub y deja el
# ejecutable en <destino>/sal. Así el CI compila salvi sin construir antes el
# compilador.
#
#   scripts/obtener-sal.sh [destino]        (por defecto target/toolchain)
#
# Variables:
#   SAL_REPO       repositorio del compilador, owner/repo. Por defecto, el
#                  mismo dueño que este repositorio y repo "sal".
#   SAL_VERSION    etiqueta de la release; "latest" (por defecto) usa la
#                  última publicada.
#   SAL_ASSET_URL  URL directa del artefacto: se salta el descubrimiento (útil
#                  si la release usa nombres de fichero poco habituales).
#
# Imprime por stdout la ruta absoluta del ejecutable.
set -eu

destino=${1:-target/toolchain}
version=${SAL_VERSION:-latest}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM

url=${SAL_ASSET_URL:-}
if [ -z "$url" ]; then
    repo=${SAL_REPO:-}
    if [ -z "$repo" ]; then
        owner=${GITHUB_REPOSITORY_OWNER:-}
        if [ -z "$owner" ] && [ -n "${GITHUB_REPOSITORY:-}" ]; then
            owner=${GITHUB_REPOSITORY%%/*}
        fi
        if [ -z "$owner" ]; then
            echo "obtener-sal: define SAL_REPO (owner/repo) del compilador" >&2
            exit 1
        fi
        repo="$owner/sal"
    fi
    command -v jq >/dev/null 2>&1 || {
        echo "obtener-sal: hace falta jq para leer la release de $repo" >&2
        exit 1
    }
    if [ "$version" = latest ]; then
        api="https://api.github.com/repos/$repo/releases/latest"
    else
        api="https://api.github.com/repos/$repo/releases/tags/$version"
    fi
    json=$(curl -fsSL "$api") || {
        echo "obtener-sal: no se pudo leer $api (¿existe la release?)" >&2
        exit 1
    }
    # Preferimos el artefacto de Linux x86_64; si no lo hay, cualquiera cuyo
    # nombre mencione sal.
    url=$(printf '%s' "$json" | jq -r '
        [.assets[].browser_download_url
         | select(test("linux") and test("x86_64|amd64"))]
        | first // empty')
    if [ -z "$url" ]; then
        url=$(printf '%s' "$json" | jq -r '
            [.assets[].browser_download_url | select(test("sal"))]
            | first // empty')
    fi
    if [ -z "$url" ]; then
        echo "obtener-sal: la release de $repo no trae ningún artefacto usable" >&2
        echo "obtener-sal: define SAL_ASSET_URL con la URL del binario" >&2
        exit 1
    fi
fi

nombre=$(basename "${url%%\?*}")
curl -fsSL "$url" -o "$tmp/$nombre" || {
    echo "obtener-sal: falló la descarga de $url" >&2
    exit 1
}

bin=
case "$nombre" in
*.tar.gz | *.tgz | *.tar.xz | *.tar.bz2 | *.zip)
    mkdir "$tmp/x"
    case "$nombre" in
    *.tar.gz | *.tgz) tar xzf "$tmp/$nombre" -C "$tmp/x" ;;
    *.tar.xz) tar xJf "$tmp/$nombre" -C "$tmp/x" ;;
    *.tar.bz2) tar xjf "$tmp/$nombre" -C "$tmp/x" ;;
    *.zip) unzip -q "$tmp/$nombre" -d "$tmp/x" ;;
    esac
    bin=$(find "$tmp/x" -type f \( -name sal -o -name 'sal-*' \) | head -n 1)
    ;;
*)
    bin="$tmp/$nombre"
    ;;
esac
if [ -z "$bin" ] || [ ! -f "$bin" ]; then
    echo "obtener-sal: no hay un ejecutable sal en $nombre" >&2
    exit 1
fi

mkdir -p "$destino"
install -m 755 "$bin" "$destino/sal"
echo "$(cd "$destino" && pwd)/sal"
