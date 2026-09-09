from discovery import discover_matches

matches = discover_matches("2026/27")
print("total discovered:", len(matches))
ids = sorted(m.nbl_id for m in matches)
print("ids:", ids)
print("544546 in result:", 544546 in ids)
print("544552 in result:", 544552 in ids)

for m in matches:
    if m.nbl_id in (544546, 544552, 544558):
        print(m)
