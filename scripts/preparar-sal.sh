#!/bin/sh
# Prepara un árbol de sal con el compilador descargado dentro y su biblioteca
# estándar localizable.
#
# El binario de la release lleva grabadas en compilación las rutas de std/ y
# runtime/ de la máquina donde se construyó (`CARGO_MANIFEST_DIR`), que no
# existen aquí; por eso hay que clonar las fuentes, exportar `SAL_STD` y dejar
# `runtime/` al alcance del proyecto que se compila.
#
#   scripts/preparar-sal.sh [directorio]    (por defecto ../sal)
#
# Variables: SAL_REPO, SAL_VERSION (ver obtener-sal.sh).
# Imprime líneas KEY=valor listas para $GITHUB_ENV:
#
#   SAL=<árbol>/target/release/sal
#   SAL_STD=<árbol>/std
set -eu

dir=${1:-../sal}
dir=$(cd "$(dirname "$dir")" && pwd)/$(basename "$dir")

if [ -e "$dir" ]; then
    # Un árbol local ya preparado (el del desarrollador): no se toca.
    if [ ! -x "$dir/target/release/sal" ]; then
        echo "preparar-sal: $dir ya existe pero no tiene target/release/sal" >&2
        echo "preparar-sal: compílalo allí o pásame otro directorio" >&2
        exit 1
    fi
else
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

    # El compilador busca runtime/ en la raíz del proyecto que compila y, si no
    # está, usa la ruta grabada en compilación (la de su propia máquina).
    if [ ! -e runtime/sal_runtime.c ]; then
        ln -s "$dir/runtime" runtime
    fi
fi

if [ ! -d "$dir/std/io" ]; then
    echo "preparar-sal: $dir/std/io no existe; sal no podrá resolver { std = \"io\" }" >&2
    exit 1
fi

echo "SAL=$dir/target/release/sal"
echo "SAL_STD=$dir/std"
