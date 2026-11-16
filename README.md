# salvi

Un vi escrito en [sal](../sal) que corre en Linux y en [soso](../soso).

```sh
./build.sh                    # ./salvi (Linux) y ./salvi-soso (soso)
./salvi [+N] [fichero]
```

En soso se distribuye como paquete de aplicación: no va en la imagen, lo
instala el usuario.

```sh
soso-pkg instalar salvi      # dentro de soso; queda en /var/paquetes/salvi
salvi nota.txt
```

Para publicar una versión nueva, sube `SALVI_VERSION` en
`../soso/xtask/src/pkg_pack.rs` y ejecuta en soso `cargo xtask pkg-pack salvi`:
compila con `./build.sh soso`, deja el paquete en
`rootfs/share/paquetes/salvi/<versión>/` y añade su fila a `indice.txt`.

## Qué hay

| | |
|---|---|
| Modos | normal, inserción (`i a I A o O`), reemplazo (`R`), visual (`v`, `V`), órdenes (`:`), búsqueda (`/ ?`) |
| Movimientos | `h j k l` y flechas, `w b e W B E`, `0 ^ $ \|`, `gg G` con cuenta, `f F t T ; ,`, `%`, `{ }`, `H M L`, `+ - Intro` |
| Operadores | `d c y > <` con cualquier movimiento, dobles (`dd cc yy >> <<`), cuentas (`2d3w`) |
| Órdenes | `x X D C s S Y p P J gJ r ~ u Ctrl-R .` |
| Visual | `d x y c s > < ~ u U J p :` y `o` para cambiar de extremo |
| Desplazamiento | `Ctrl-F Ctrl-B Ctrl-D Ctrl-U Ctrl-E Ctrl-Y`, RePág/AvPág |
| Búsqueda | `/` `?` `n` `N` `*` `#` (texto literal; `*` y `#` por palabra entera) |
| `:` | `w [f]`, `q[!]`, `wq`, `x`, `ZZ`, `ZQ`, `e[!] [f]`, `r f`, `N`, `$`, rangos `N,M` `%` `.`, `s/pat/rep/[g]`, `d`, `y`, `j`, `set`, `help` |
| `:set` | `nu`/`nonu`, `ts=N`, `sw=N`, `et`/`noet`, `ai`/`noai`, `lines=N`, `columns=N` |
| Texto | UTF-8 (el cursor salta caracteres completos), tabuladores, deshacer ilimitado |

## Cómo funciona en cada sistema

- **Linux**: la tty se pasa a modo crudo con `stty raw -echo` y se restaura
  con lo que guardó `stty -g`; el tamaño sale de `stty size`. Usa la pantalla
  alternativa del terminal.
- **soso**: la tty ya entrega los bytes sin eco ni línea, así que no hace
  falta `stty` (si no se puede lanzar, se asume consola cruda). No hay forma
  de preguntar el tamaño: se usa `LINES`/`COLUMNS` o 80×24, y se puede cambiar
  con `:set lines=N columns=N`. La tty de soso convierte Ctrl-D en un `read`
  de 0 bytes: salvi lo vuelve a tratar como Ctrl-D. Ctrl-C manda SIGINT y
  soso no tiene manejadores: mata el editor.
- Una tecla Esc se distingue de una secuencia (flechas…) porque la secuencia
  llega en la misma lectura; en Linux además se espera 25 ms.

## Límites conocidos

- Búsqueda y `:s` sin expresiones regulares (soso no tiene `regcomp`).
- Sin ajuste de línea: las líneas largas se desplazan en horizontal.
- Un solo buffer y un solo registro sin nombre; sin marcas, macros ni `:!`.
- La cuenta no repite inserciones (`3ia<Esc>` inserta una `a`).
- Caracteres anchos (CJK, emoji) cuentan como una columna.
- Fichero con bytes NUL: se corta en el primero (las cadenas de sal son C).

## Pruebas

```sh
python3 tests/run_tests.py ./salvi        # 83 casos en una pty de Linux
python3 tests/soso_qemu.py               # instala el paquete en soso (QEMU) y prueba 8 casos
```

`soso_qemu.py` monta su propio rootfs en `target/soso-test` con utilidades de
`../soso/rootfs/bin` (incluido `soso-pkg`) y un repositorio local con el
paquete de `../soso/rootfs/share/paquetes/salvi/`; dentro de soso ejecuta
`soso-pkg instalar salvi --origen /share/paquetes` y luego `salvi`. No
modifica el árbol de soso.

## Código

| Ruta | Contenido |
|---|---|
| `src/salvi.sal` | argumentos y arranque |
| `src/term/` | terminal (modo crudo, tamaño, escritura) y lectura de teclas |
| `src/text/` | buffer de líneas, UTF-8 y movimientos de vi |
| `src/editor/editor.sal` | estado del editor y todos los modos |
| `src/editor/render.sal`, `ex.sal` | pintado de líneas y ayudas de `:` |

Fallos de sal encontrados por el camino: [docs/bugs-sal.md](docs/bugs-sal.md).
