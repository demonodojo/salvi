#!/bin/sh
# Compila salvi para Linux (./salvi) y para soso (./salvi-soso).
#   ./build.sh            ambos
#   ./build.sh linux|soso uno solo
# SAL apunta al compilador (por defecto ../sal/target/release/sal) y SOSO al
# árbol de soso con el SDK de sal ya preparado (cargo xtask sal-build --cross-only).
set -e
cd "$(dirname "$0")"
SAL="${SAL:-../sal/target/release/sal}"
SOSO="${SOSO:-../soso}"
que="${1:-todo}"
[ -e sal_modules/io ] || "$SAL" install
if [ "$que" = todo ] || [ "$que" = linux ]; then
    "$SAL" build --release src/salvi.sal -o salvi >/dev/null
    echo "salvi (linux)"
fi
if [ "$que" = todo ] || [ "$que" = soso ]; then
    SAL_SDK="${SAL_SDK:-$SOSO/target/sal/sdk}" \
    SAL_LD="${SAL_LD:-$(cd "$SOSO" && rustc --print sysroot)/lib/rustlib/x86_64-unknown-linux-gnu/bin/rust-lld}" \
        "$SAL" build --target soso src/salvi.sal -o salvi-soso >/dev/null
    echo "salvi-soso (soso)"
fi
