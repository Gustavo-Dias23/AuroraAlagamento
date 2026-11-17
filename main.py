"""
main.py
Ponto de entrada da estação de alagamento.

    python main.py               # com o Arduino ligado
    python main.py --simulado    # sem Arduino: simula um alagamento
    python main.py --simulado --rapido --silenciosa   # teste em segundos
"""

import argparse

from aurora.estacao import EstacaoAlagamento
from aurora.hardware import ControladorArduino, SimuladorArduino
from aurora.ia import GeradorAlertas
from aurora.relatos import ClienteMVP
from aurora.voz import Voz


class RelogioVirtual:
    """No modo --rapido o tempo avança sem esperar de verdade."""

    def __init__(self):
        self.agora = 0.0

    def __call__(self) -> float:
        return self.agora

    def dormir(self, segundos: float) -> None:
        self.agora += segundos


def main() -> None:
    parser = argparse.ArgumentParser(description="Aurora - estação de alagamento")
    parser.add_argument("--simulado", action="store_true", help="roda sem Arduino")
    parser.add_argument("--rapido", action="store_true", help="não espera entre leituras")
    parser.add_argument("--silenciosa", action="store_true", help="não fala, só imprime")
    parser.add_argument("--porta", help="porta do Arduino (ex.: COM3 ou /dev/cu.usbmodem101)")
    parser.add_argument("--ciclos", type=int, help="número de leituras antes de parar")
    args = parser.parse_args()

    if args.simulado:
        hardware = SimuladorArduino()
    else:
        hardware = ControladorArduino(args.porta)
        if not hardware.conectado or not hardware.testar():
            print("Arduino não encontrado. Confira o cabo e a porta, ou use --simulado.")
            return

    extras = {}
    if args.rapido:
        relogio = RelogioVirtual()
        extras = {"relogio": relogio, "dormir": relogio.dormir}

    estacao = EstacaoAlagamento(
        hardware=hardware,
        voz=Voz(silenciosa=args.silenciosa),
        ia=GeradorAlertas(),
        mvp=ClienteMVP(),
        **extras,
    )
    print("Estação iniciada. Ctrl+C para encerrar.\n")
    estacao.executar(max_ciclos=args.ciclos)


if __name__ == "__main__":
    main()
