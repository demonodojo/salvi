# Fallos de sal encontrados al escribir salvi

## Doble liberación al mover un `String` a un argumento en una sola rama

Compilador: `../sal/target/release/sal` del 16-11-2026.

Si un `String` local se mueve como argumento de un método en una rama de un
`if` y en la otra no (o se mueve a otro sitio), la bandera `__live` de la rama
que llama al método queda a 1 y el llamador lo vuelve a liberar al salir.
El llamado ya lo había liberado: uso tras liberar / doble `free`.

```sal
struct E
    n: Int
    msg: String
    cmd: String

method E.take(&mut self, s: String) -> Unit
    self.n = s.len()

method E.go(&mut self, k: Int, c: Int) -> Unit ! alloc
    if k == 13
        line = self.cmd.clone()
        self.cmd = d""
        if c == 1
            self.take(line)
        else
            if line.len() > 0
                self.msg = line
            self.n = 7
        return
    self.n = 9

fn main() -> Int ! io, alloc
    e = E(0, d"", d"hola")
    e.go(13, 1)
    print_str("n=" + e.n.to_str() + "\n")
    0
```

`sal build --sanitize` + ejecutar: `heap-use-after-free ... in sal_str_cap`.
En el IR de `E__go` el `IfCarry` de la bandera vale la constante 1 en la rama
de `self.take(line)`.

Rodeo en salvi: `Editor.ex` y `Editor.search_cmd` reciben `&String`.

## `standard fix` (`Style/Elsif`) cambia la semántica

Convierte `else` + `if` en `elsif` aunque el bloque `else` tenga más
sentencias detrás del `if`; esas sentencias pasan a ejecutarse solo dentro
del `elsif`. En salvi dejó un bucle sin avance (`j = j + 1` dentro del nuevo
`elsif`). Hay que revisar el diff de `standard fix` a mano.
