#!/usr/bin/env python3
"""Prueba de salvi dentro de soso, en QEMU, por la consola serie.

Monta un rootfs propio en target/soso-test (no toca el árbol de soso) con
las utilidades mínimas de soso, `soso-pkg` y un repositorio local de paquetes
con salvi. Dentro de soso instala salvi con `soso-pkg instalar salvi --origen`
(no va en /bin: sosh lo encuentra por /var/paquetes/comandos) y edita
ficheros tecleando por la consola serie.

    python3 tests/soso_qemu.py [directorio-del-paquete]

El paquete por defecto es ../soso/rootfs/share/paquetes/salvi/<versión más
reciente> (`cargo xtask pkg-pack salvi`). Necesita en ../soso:
target/soso-uefi.img, target/release/mkfs-soso y rootfs/bin con init, sosh,
cat y soso-pkg; y OVMF en /usr/share/OVMF.
"""
import os
import pathlib
import re
import selectors
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parents[1]
SOSO = pathlib.Path(os.environ.get("SOSO_DIR", HERE.parent / "soso"))
OUT = HERE / "target/soso-test"
ROOT = OUT / "rootfs"
ESC = "\x1b"

# (nombre, texto inicial, teclas, texto esperado)
CASES = [
    ("insertar y guardar", "", "ihola soso" + ESC + ":wq\r", "hola soso\n"),
    ("borrar palabra y deshacer", "uno dos tres\n", "dwdwu:wq\r", "dos tres\n"),
    ("líneas y pegar", "1\n2\n3\n", "ddp:wq\r", "2\n1\n3\n"),
    ("sustituir", "a a a\n", ":%s/a/bé/g\r:wq\r", "bé bé bé\n"),
    ("buscar y utf8", "año\nniño\n", "/ñ\rnx:wq\r", "año\nnio\n"),
    ("ctrl-d (VEOF de soso)", "1\n2\n", "\x04x:wq\r", "1\n\n"),
    ("visual multilínea", "abc\ndef\n", "vjd:wq\r", "ef\n"),
    ("fichero nuevo", None, "inuevo" + ESC + ":wq\r", "nuevo\n"),
]


def paquete_por_defecto():
    base = SOSO / "rootfs/share/paquetes/salvi"
    versiones = sorted((d for d in base.iterdir() if d.is_dir()),
                       key=lambda d: [int(x) for x in d.name.split(".")])
    return versiones[-1]


def preparar(paquete):
    if ROOT.exists():
        shutil.rmtree(ROOT)
    for d in ["bin", "etc", "tmp", "var/paquetes", "pruebas"]:
        (ROOT / d).mkdir(parents=True, exist_ok=True)
    (ROOT / "etc/soso-release").write_text("salvi-test\n")
    for name in ["init", "sosh", "echo", "cat", "rm", "halt", "soso-pkg"]:
        src = SOSO / "rootfs/bin" / name
        if src.exists():
            shutil.copy2(src, ROOT / "bin" / name)
    # Repositorio local con solo salvi, en el formato del índice publicado.
    repo = ROOT / "share/paquetes"
    destino = repo / "salvi" / paquete.name
    destino.mkdir(parents=True)
    for f in ["paquete.txt", "paquete.pack"]:
        shutil.copy2(paquete / f, destino / f)
    filas = [l for l in (paquete.parents[1] / "indice.txt").read_text().splitlines()
             if l.startswith(f"p salvi {paquete.name} ")]
    if not filas:
        raise SystemExit(f"indice.txt no lista salvi {paquete.name}; ejecuta cargo xtask pkg-pack salvi")
    (repo / "indice.txt").write_text("SOSOPKG indice v1\n" + filas[0] + "\n")
    for i, (_, text, _, _) in enumerate(CASES):
        if text is not None:
            (ROOT / "pruebas" / f"c{i}.txt").write_bytes(text.encode())
    subprocess.run([str(SOSO / "target/release/mkfs-soso"), str(ROOT), str(OUT / "data.img"), "256"],
                   check=True, stdout=subprocess.DEVNULL)


def main():
    paquete = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else paquete_por_defecto()
    OUT.mkdir(parents=True, exist_ok=True)
    preparar(paquete)
    shutil.copy2(SOSO / "target/soso-uefi.img", OUT / "boot.img")
    shutil.copy2("/usr/share/OVMF/OVMF_VARS_4M.fd", OUT / "vars.fd")
    kvm = os.access("/dev/kvm", os.R_OK | os.W_OK)
    cmd = ["qemu-system-x86_64", "-machine", "q35", "-cpu", "max", "-m", "1024", "-smp", "2",
           "-accel", "kvm" if kvm else "tcg",
           "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
           "-drive", f"if=pflash,format=raw,file={OUT}/vars.fd",
           "-drive", f"format=raw,file={OUT}/boot.img",
           "-drive", f"if=none,id=root,format=raw,file={OUT}/data.img",
           "-device", "virtio-blk-pci,drive=root", "-nic", "none", "-display", "none",
           "-serial", "stdio", "-monitor", "none", "-no-reboot"]
    log = open(OUT / "serial.log", "wb")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    total = bytearray()

    def leer(segundos):
        end = time.monotonic() + segundos
        while time.monotonic() < end:
            for key, _ in sel.select(0.05):
                data = os.read(key.fd, 65536)
                if not data:
                    raise RuntimeError(f"QEMU terminó: {proc.poll()}")
                log.write(data)
                log.flush()
                total.extend(data)

    def esperar(pattern, timeout=120):
        start = len(total)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            m = re.search(pattern, total[start:])
            if m:
                return bytes(total[start:]).decode("utf8", "replace")
            leer(0.2)
        raise RuntimeError(f"timeout esperando {pattern!r}; ver {OUT}/serial.log")

    def escribir(s):
        proc.stdin.write(s.encode())
        proc.stdin.flush()

    fallos = 0
    try:
        esperar(rb"\$ ", 180)
        escribir("soso-pkg instalar salvi --origen /share/paquetes\n")
        escribir("echo FIN_INSTALAR\n")
        out = esperar(rb"\nFIN_INSTALAR\r?\n", 60)
        print(re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", out).replace("\r", "").strip(), flush=True)
        if (ROOT / "bin/salvi").exists():
            raise SystemExit("salvi no debería estar en /bin del rootfs de prueba")
        for i, (name, text, keys, want) in enumerate(CASES):
            path = f"/pruebas/c{i}.txt"
            escribir(f"salvi {path}\n")
            esperar(rb"\x1b\[\?25h", 30)  # primer pintado
            leer(0.3)
            # Un ESC suelto va solo: en soso no hay plazo para separarlo.
            for ch in keys:
                escribir(ch)
                leer(0.08 if ch == ESC else 0.02)
            marca = f"FIN_{i}"
            escribir(f"cat {path}\n")
            escribir(f"echo {marca}\n")
            out = esperar(rf"\n{marca}\r?\n".encode(), 30)
            out = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", out).replace("\r", "")
            # Lo que hay entre el eco de `cat …` y el siguiente indicador `$ `.
            got = out.split(f"cat {path}\n", 1)[-1].split("$ echo", 1)[0]
            ok = got == want
            fallos += 0 if ok else 1
            print(f"{'ok   ' if ok else 'FALLO'} {name}" + ("" if ok else f": esperado {want!r}, obtenido {got!r}"),
                  flush=True)
        print(f"\n{len(CASES) - fallos}/{len(CASES)} correctos en soso")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        sel.close()
        log.close()
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
