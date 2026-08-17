import sys
path, line = sys.argv[1], sys.argv[2]
src = open(path).read().splitlines(keepends=True)
out = []
for l in src:
    out.append(l)
    if '"add":' in l:
        indent = l[:len(l) - len(l.lstrip())]
        out.append(f'{indent}{line}\n')
open(path, "w").writelines(out)
