import json
import re
import subprocess
import sys
from pathlib import Path

def safe(s):
    return str(s or "").replace("\\", "\\\\").replace('"', '\\"')

def method_name(sig):
    m = re.search(r"\s([A-Za-z0-9_$]+)\s*\(", sig or "")
    return m.group(1) if m else ""

def run(cmd):
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout, p.stderr

def script(cpg, cls, method, file_path):
    short = cls.split(".")[-1]
    filename = Path(file_path or "").name
    package_path = cls.replace(".", "/")
    return f'''
importCpg("{safe(cpg)}")

val cls = "{safe(cls)}"
val shortCls = "{safe(short)}"
val methodName = "{safe(method)}"
val filename = "{safe(filename)}"
val packagePath = "{safe(package_path)}"

println("CLASS=" + cls)
println("METHOD=" + methodName)
println("FILENAME=" + filename)

println("METHOD_NAME_COUNT=" + cpg.method.name(methodName).size)

println("TYPE_FULLNAME_COUNT=" + cpg.typeDecl.filter(_.fullName.contains(cls)).size)
println("TYPE_SHORT_COUNT=" + cpg.typeDecl.filter(t => t.name == shortCls || t.fullName.endsWith("." + shortCls)).size)
println("FILE_COUNT=" + cpg.file.filter(_.name.contains(filename)).size)
println("METHOD_FILENAME_COUNT=" + cpg.method.filter(m => filename.nonEmpty && m.filename.contains(filename)).size)
println("METHOD_CLASS_SUBSTR_COUNT=" + cpg.method.filter(_.fullName.contains(shortCls)).size)

println("MATCHING_METHODS_BEGIN")
cpg.method
 .filter(m =>
   m.name == methodName ||
   m.fullName.contains(cls) ||
   m.fullName.contains(shortCls) ||
   (filename.nonEmpty && m.filename.contains(filename))
 )
 .map(m => m.name + "|" + m.fullName + "|" + m.filename + "|" + m.lineNumber.getOrElse(-1))
 .take(30)
 .l
 .foreach(println)
println("MATCHING_METHODS_END")
'''

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m joern_engine.diagnose_method_resolution <cpg.bin> <candidates.json> <out.txt>")
        sys.exit(1)

    cpg = sys.argv[1]
    candidates = json.loads(Path(sys.argv[2]).read_text())
    out = Path(sys.argv[3])

    chunks = []
    tmp = out.parent / "joern_resolution_diagnostics"
    tmp.mkdir(parents=True, exist_ok=True)

    for i, c in enumerate(candidates, 1):
        cls = c.get("class", "")
        sig = c.get("signature", "")
        m = c.get("rn_enrichment", {}).get("method_name") or method_name(sig)
        fp = c.get("file", "")
        sp = tmp / f"{i:03d}_{m}.sc"
        sp.write_text(script(cpg, cls, m, fp))
        stdout, stderr = run(["joern", "--script", str(sp)])
        chunks.append(f"===== CANDIDATE {i} =====\n{stdout}\n")

    out.write_text("\n".join(chunks))
    print(f"[+] written {out}")

if __name__ == "__main__":
    main()
