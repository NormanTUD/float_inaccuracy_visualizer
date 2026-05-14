# Floating-Point Problem: 0.1 ist der Klassiker!

x = 0.0
step = 0.1
target = 1.0

print(f"Step (volle Präzision): {step:.20f}")
print(f"10 * 0.1 (volle Präzision): {10 * 0.1:.20f}")
print(f"0.1 + 0.1 + ... (10x) = {0.1+0.1+0.1+0.1+0.1+0.1+0.1+0.1+0.1+0.1:.20f}")
print(f"Ist das == 1.0? {0.1+0.1+0.1+0.1+0.1+0.1+0.1+0.1+0.1+0.1 == 1.0}")
print()

# Die Endlosschleife (mit Sicherheitsabbruch)
iterations = 0
max_iterations = 200

while x != target:
    x += step
    iterations += 1
    
    # Zeige was passiert wenn wir uns 1.0 nähern
    if 0.9 <= x <= 1.1:
        print(f"  Iteration {iterations}: x = {x:.20f} | x == 1.0? {x == 1.0}")
    
    if iterations >= max_iterations:
        print(f"\n  ABBRUCH nach {max_iterations} Iterationen!")
        print(f"  x ist jetzt: {x:.20f}")
        print(f"  x springt über 1.0 hinweg, ohne es je exakt zu treffen!")
        break

print()
print("--- Das Problem ---")
print(f"0.1 als float ist eigentlich: {0.1:.25f}")
print(f"10x addiert ergibt NICHT 1.0, sondern: {sum([0.1]*10):.25f}")
