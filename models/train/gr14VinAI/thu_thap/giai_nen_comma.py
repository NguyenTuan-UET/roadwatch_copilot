# Giai nen 1 chunk comma2k19 tren Windows, doi ky tu '|' thanh '_'
# Cach dung: python giai_nen_comma.py <file zip> [thu muc dich, mac dinh la thu muc archive]
import zipfile, os, shutil, sys
src = sys.argv[1]
dst = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
z = zipfile.ZipFile(src)
infos = z.infolist(); n = len(infos)
for i, info in enumerate(infos, 1):
    name = info.filename.replace('|', '_')
    out = os.path.join(dst, *name.rstrip('/').split('/'))
    if info.is_dir():
        os.makedirs(out, exist_ok=True); continue
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out) and os.path.getsize(out) == info.file_size:
        continue
    with z.open(info) as s, open(out, 'wb') as d:
        shutil.copyfileobj(s, d, 1 << 22)
    if i % 100 == 0 or i == n:
        print(f"\r{i}/{n} file", end='', flush=True)
print("\nXong! Du lieu nam trong", os.path.abspath(dst))
