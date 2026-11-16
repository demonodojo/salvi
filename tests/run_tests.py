#!/usr/bin/env python3
"""Pruebas de extremo a extremo de salvi en Linux.

Cada caso arranca el binario en una pseudo-terminal con un fichero de
partida, teclea una secuencia y comprueba el fichero que queda al salir.

    python3 tests/run_tests.py [ruta/al/binario] [-k filtro]
"""
import os
import pty
import select
import sys
import tempfile
import time

ESC = "\x1b"

# (nombre, texto inicial, teclas, texto esperado)
CASES = [
    ("insertar", "", "ihola mundo" + ESC + ":wq\r", "hola mundo\n"),
    ("append", "abc\n", "Axyz" + ESC + ":wq\r", "abcxyz\n"),
    ("a tras cursor", "ac\n", "ab" + ESC + ":wq\r", "abc\n"),
    ("I primer no blanco", "   x\n", "AZ" + ESC + "I-" + ESC + ":wq\r", "   -xZ\n"),
    ("o y O", "b\n", "oc" + ESC + "kOa" + ESC + ":wq\r", "a\nb\nc\n"),
    ("intro parte linea", "abcd\n", "llia\rb" + ESC + ":wq\r", "aba\nbcd\n"),
    ("autoindent", "    x\n", "A\ry" + ESC + ":wq\r", "    x\n    y\n"),
    ("backspace une", "ab\ncd\n", "jI\x7f" + ESC + ":wq\r", "abcd\n"),
    ("x y X", "abcdef\n", "xx$X:wq\r", "cdf\n"),
    ("3x", "abcdef\n", "l3x:wq\r", "aef\n"),
    ("dd", "1\n2\n3\n", "jdd:wq\r", "1\n3\n"),
    ("2dd p", "1\n2\n3\n4\n", "2ddp:wq\r", "3\n1\n2\n4\n"),
    ("dw", "uno dos tres\n", "dw:wq\r", "dos tres\n"),
    ("d2w", "uno dos tres\n", "d2w:wq\r", "tres\n"),
    ("dw final de linea", "uno dos\ntres\n", "wdw:wq\r", "uno \ntres\n"),
    ("cw", "uno dos\n", "cwUNO" + ESC + ":wq\r", "UNO dos\n"),
    ("cc", "  uno\ndos\n", "ccX" + ESC + ":wq\r", "  X\ndos\n"),
    ("C y D", "abc def\nxyz\n", "wDjlCq" + ESC + ":wq\r", "abc \nxyq\n"),
    ("de", "foo.bar baz\n", "de:wq\r", ".bar baz\n"),
    ("dW", "foo.bar baz\n", "dW:wq\r", "baz\n"),
    ("db", "uno dos\n", "$db:wq\r", "uno s\n"),
    ("d$", "uno dos\n", "wd$:wq\r", "uno \n"),
    ("d0", "uno dos\n", "wd0:wq\r", "dos\n"),
    ("dG", "1\n2\n3\n", "jdG:wq\r", "1\n"),
    ("dgg", "1\n2\n3\n", "jdgg:wq\r", "3\n"),
    ("dj", "1\n2\n3\n", "dj:wq\r", "3\n"),
    ("df", "a,b,c\n", "df,:wq\r", "b,c\n"),
    ("dt", "a,b,c\n", "dt,:wq\r", ",b,c\n"),
    ("d2f", "a,b,c\n", "d2f,:wq\r", "c\n"),
    ("f ;", "a,b,c,d\n", "f,;x:wq\r", "a,bc,d\n"),
    ("yy P", "1\n2\n", "yyjP:wq\r", "1\n1\n2\n"),
    ("yw p", "uno dos\n", "ywP:wq\r", "uno uno dos\n"),
    ("p caracteres", "ab\n", "xp:wq\r", "ba\n"),
    ("J", "uno\n   dos\ntres\n", "J:wq\r", "uno dos\ntres\n"),
    ("3J", "a\nb\nc\nd\n", "3J:wq\r", "a b c\nd\n"),
    ("r", "abc\n", "rX:wq\r", "Xbc\n"),
    ("3r", "abcd\n", "3rz:wq\r", "zzzd\n"),
    ("~", "abC\n", "~~~:wq\r", "ABc\n"),
    ("R", "abcd\n", "lRXY" + ESC + ":wq\r", "aXYd\n"),
    (">> <<", "x\ny\n", ">>j>><<:wq\r", "\tx\ny\n"),
    ("set sw et", "x\n", ":set sw=4 et\r>>:wq\r", "    x\n"),
    ("u", "abc\n", "xxu:wq\r", "bc\n"),
    ("u ctrl-r", "abc\n", "xxuu\x12:wq\r", "bc\n"),
    ("u insercion", "abc\n", "Axyz" + ESC + "u:wq\r", "abc\n"),
    ("punto", "a b c d\n", "dw..:wq\r", "d\n"),
    ("punto insercion", "x\ny\n", "A!" + ESC + "j.:wq\r", "x!\ny!\n"),
    ("busqueda", "uno\ndos\ntres dos\n", "/dos\rnx:wq\r", "uno\ndos\ntres os\n"),
    ("busqueda atras", "dos\nuno\ndos\n", "G?dos\rx:wq\r", "os\nuno\ndos\n"),
    ("busqueda vacia repite", "a\nb a\na\n", "/a\r/\rx:wq\r", "a\nb a\n\n"),
    (":s delimitador escapado", "a/b\n", ":s/\\//-/\r:wq\r", "a-b\n"),
    ("tabulador en pantalla", "\tx\n", "$x:wq\r", "\t\n"),
    ("asterisco", "foo foobar foo\n", "*x:wq\r", "foo foobar oo\n"),
    (":s", "a a a\n", ":s/a/b/\r:wq\r", "b a a\n"),
    (":s g", "a a a\n", ":s/a/b/g\r:wq\r", "b b b\n"),
    (":%s", "a\nxa\n", ":%s/a/bb/g\r:wq\r", "bb\nxbb\n"),
    (":2,3d", "1\n2\n3\n4\n", ":2,3d\r:wq\r", "1\n4\n"),
    (":N", "1\n2\n3\n", ":3\rdd:wq\r", "1\n2\n"),
    ("G y gg", "1\n2\n3\n", "Gx" + "ggx:wq\r", "\n2\n\n"),
    ("visual d", "abcdef\n", "lvlld:wq\r", "aef\n"),
    ("visual linea y p", "1\n2\n", "Vyp:wq\r", "1\n1\n2\n"),
    ("visual multilinea", "abc\ndef\n", "lvjd:wq\r", "af\n"),
    ("visual >", "a\nb\n", "Vj>:wq\r", "\ta\n\tb\n"),
    ("visual U", "abc\n", "vlU:wq\r", "ABc\n"),
    ("%", "f(a(b)c)\n", "f(%x:wq\r", "f(a(b)c\n"),
    ("d%", "x(a)y\n", "f(d%:wq\r", "xy\n"),
    ("d}", "a\nb\n\nc\n", "d}:wq\r", "\nc\n"),
    ("utf8 x", "añb\n", "lx:wq\r", "ab\n"),
    ("utf8 insertar", "", "iñandú" + ESC + "x:wq\r", "ñand\n"),
    ("flechas", "ab\ncd\n", "\x1b[B\x1b[Cx:wq\r", "ab\nc\n"),
    ("tab", "", "i\tx" + ESC + ":wq\r", "\tx\n"),
    ("cuenta insert sin cuenta", "", "3ia" + ESC + ":wq\r", "a\n"),
    (":q sin guardar falla", "a\n", "x:q\r:q!\r", "a\n"),
    ("ZZ", "a\n", "xZZ", "\n"),
    ("ctrl-w", "", "iuno dos\x17X" + ESC + ":wq\r", "uno X\n"),
    (":r", "1\n", ":r {other}\r:wq\r", "1\nleido\n"),
    ("s", "abc\n", "sX" + ESC + ":wq\r", "Xbc\n"),
    ("S", "  abc\n", "SX" + ESC + ":wq\r", "  X\n"),
    ("Y", "a\nb\n", "Yjp:wq\r", "a\nb\na\n"),
    ("p multilinea", "abc\ndef\n", "lvjy$p:wq\r", "abcbc\nde\ndef\n"),
    ("e fin de palabra", "uno dos\n", "ex:wq\r", "un dos\n"),
    ("cuenta j", "1\n2\n3\n4\n", "2jx:wq\r", "1\n2\n\n4\n"),
    ("H M L", "1\n2\n3\n", "Lx:wq\r", "1\n2\n\n"),
    ("ctrl-d en soso no rompe", "1\n2\n", "\x04x:wq\r", "1\n\n"),
]


def run_case(binary, text, keys, rows=24, cols=80, timeout=5.0):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "f.txt")
        other = os.path.join(tmp, "otro.txt")
        with open(other, "w") as f:
            f.write("leido\n")
        with open(path, "w") as f:
            f.write(text)
        keys = keys.replace("{other}", other)
        env = dict(os.environ, LINES=str(rows), COLUMNS=str(cols), TERM="xterm")
        pid, fd = pty.fork()
        if pid == 0:
            os.execve(binary, [binary, path], env)
        out = b""
        deadline = time.time() + timeout

        def drain(wait):
            nonlocal out
            end = time.time() + wait
            while True:
                left = end - time.time()
                if left <= 0:
                    return True
                r, _, _ = select.select([fd], [], [], left)
                if not r:
                    return True
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    return False
                if not chunk:
                    return False
                out += chunk

        alive = drain(0.4)
        # Un ESC suelto tiene que llegar en su propia lectura para no
        # confundirse con una secuencia: se envía cada tecla por separado.
        i = 0
        while i < len(keys) and alive:
            ch = keys[i]
            if ch == ESC and keys[i + 1:i + 2] == "[":
                ch = keys[i:i + 3]
            os.write(fd, ch.encode())
            i += len(ch)
            alive = drain(0.03 if ch == ESC else 0.005)
        status = None
        while time.time() < deadline:
            done, st = os.waitpid(pid, os.WNOHANG)
            if done:
                status = st
                break
            drain(0.05)
        if status is None:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
            return None, out
        with open(path) as f:
            return f.read(), out


def main():
    args = sys.argv[1:]
    filt = None
    if "-k" in args:
        i = args.index("-k")
        filt = args[i + 1]
        del args[i:i + 2]
    binary = os.path.abspath(args[0] if args else "salvi")
    fails = 0
    total = 0
    for name, text, keys, want in CASES:
        if filt and filt not in name:
            continue
        total += 1
        got, out = run_case(binary, text, keys)
        if got == want:
            print(f"ok    {name}")
        else:
            fails += 1
            print(f"FALLO {name}: esperado {want!r}, obtenido {got!r}")
            if os.environ.get("SALVI_DEBUG"):
                print(out.decode(errors="replace")[-800:])
    print(f"\n{total - fails}/{total} correctos")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
