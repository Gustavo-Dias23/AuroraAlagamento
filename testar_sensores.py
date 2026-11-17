"""
testar_sensores.py
Diagnóstico da estação com o Arduino ligado. Use para:
  - conferir se o ultrassônico, o LED e o servo estão ligados certo;
  - ver a distância medida ao vivo (coloque e tire água da bacia).

    python testar_sensores.py
"""

import time

from aurora.hardware import NOMES_NIVEIS, ControladorArduino


def main() -> None:
    arduino = ControladorArduino()
    if not arduino.conectado or not arduino.testar():
        print("Arduino não respondeu. Feche o Monitor Serial da IDE e confira o cabo.")
        return
    print(f"Arduino em {arduino.porta}\n")

    print("Testando os padrões do LED:")
    for nivel in (1, 2, 3, 0):
        print(f"  nível {nivel}: {NOMES_NIVEIS[nivel]}")
        arduino.definir_nivel(nivel)
        time.sleep(3)

    print("\nTestando o servo (a cabeça deve balançar)...")
    arduino.gesto()

    print(f"\nPiso seco a {arduino.calibrar()} cm do sensor")
    print("\nDistância ao vivo (Ctrl+C para sair):")
    try:
        while True:
            print(f"  {arduino.ler().distancia} cm")
            time.sleep(0.5)
    except KeyboardInterrupt:
        arduino.fechar()


if __name__ == "__main__":
    main()
