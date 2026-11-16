#!/bin/sh
# Prepara un árbol de sal con el compilador descargado dentro, en
# <árbol>/target/release/sal. Hace falta porque `sal install` busca las
# bibliotecas estándar junto a las fuentes del compilador (<árbol>/sal/std), no
# junto al binario suelto.
#
#   scripts/preparar-sal.sh [directorio]    (por defecto ../sal)
#
# Variables: SAL_REPO, SAL_VERSION (ver obtener-sal.sh).
# Imprime por stdout la ruta absoluta del ejecutable.
set -eu

dir=${1:-../sal}
dir=$(cd "$(dirname "$dir")" && pwd)/$(basename "$dir")
case "$dir" in
/*) ;;
*)
    echo "preparar-sal: no se pudo resolver $dir" >&2
    exit 1
    ;;
esac

if [ -e "$dir" ]; then
    # Un árbol local ya preparado (el del desarrollador): no se toca.
    if [ -x "$dir/target/release/sal" ]; then
        echo "$dir/target/release/sal"
        exit 0
    fi
    echo "preparar-sal: $dir ya existe pero no tiene target/release/sal" >&2
    echo "preparar-sal: compílalo allí o pásame otro directorio" >&2
    exit 1
fi

repo=${SAL_REPO:?preparar-sal: define SAL_REPO (owner/repo) del compilador}
tag=$(SAL_REPO="$repo" ./scripts/obtener-sal.sh --etiqueta)

mkdir -p "$(dirname "$dir")"
git clone --quiet --depth 1 "https://github.com/$repo.git" "$dir"
if git -C "$dir" fetch --quiet --depth 1 origin "refs/tags/$tag"; then
    git -C "$dir" checkout --quiet --detach FETCH_HEAD
else
    echo "preparar-sal: no existe el tag $tag en $repo; uso la rama por defecto" >&2
fi

bin=$(SAL_REPO="$repo" SAL_VERSION="$tag" ./scripts/obtener-sal.sh target/toolchain)
mkdir -p "$dir/target/release"
install -m 755 "$bin" "$dir/target/release/sal"
echo "$dir/target/release/sal"
