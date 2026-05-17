# Leak: Die Abstraktion "RAM" verspricht: Jede Speicheradresse ist gleich schnell erreichbar (Random Access Memory!). Die Realität: Die CPU hat Caches (L1, L2, L3). Sequentieller Zugriff ist massiv schneller, weil die CPU vorhersagt, was du als nächstes brauchst, und es vorab lädt. Zufälliger Zugriff erzeugt ständig Cache Misses.

import time
a = list(range(1000000))   # Zusammenhängend im Speicher
b = [x for x in range(1000000)]  # Auch, aber...

# Sequentiell vs. zufällig zugreifen
import random
indices = list(range(1000000))
random.shuffle(indices)

start = time.time()
s = sum(a[i] for i in range(1000000))       # Sequentiell
t1 = time.time() - start

start = time.time()
s = sum(a[i] for i in indices)              # Zufällig
t2 = time.time() - start

print(f"Sequentiell: {t1:.3f}s")
print(f"Zufällig:    {t2:.3f}s")  # Deutlich langsamer!
