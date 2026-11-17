"""
hardware.py
Camada de hardware da estação.

- ControladorArduino: conversa com o Arduino pela porta USB (serial).
- SimuladorArduino: mesma interface, mas gera leituras de um cenário
  de alagamento. Serve para desenvolver e testar sem o Arduino:
      python main.py --simulado

As duas classes têm os mesmos métodos, então a estação não precisa
saber com qual delas está falando (polimorfismo).
"""

import random
import time
from dataclasses import dataclass

try:
    import serial
    from serial.tools import list_ports
except ImportError:          # pyserial ausente: só o simulador funciona
    serial = None
    list_ports = None

from .config import ARDUINO_BAUDRATE, ARDUINO_PORTA, ARDUINO_TIMEOUT

# Níveis compartilhados com o firmware
SECO, POCA, ALAGADO, FALHA = 0, 1, 2, 3
NOMES_NIVEIS = {SECO: "seco", POCA: "poça", ALAGADO: "alagado", FALHA: "falha"}


@dataclass
class Leitura:
    """Uma medição do ultrassônico. distancia=None indica falha do sensor."""
    distancia: float | None


# ====================================================================== #
# Arduino real
# ====================================================================== #
class ControladorArduino:
    """Envia comandos de texto ao firmware e interpreta as respostas."""

    IDENTIFICADORES = ("arduino", "ch340", "usb-serial", "wch",
                       "ttyusb", "ttyacm", "usbmodem")

    def __init__(self, porta: str | None = ARDUINO_PORTA):
        self.conexao = None
        self.porta = porta or self._detectar_porta()
        if self.porta:
            self._abrir()

    # ------------------------------------------------------------------ #
    def _detectar_porta(self) -> str | None:
        if list_ports is None:
            return None
        for p in list_ports.comports():
            descricao = f"{p.device} {p.description} {p.manufacturer}".lower()
            if any(chave in descricao for chave in self.IDENTIFICADORES):
                return p.device
        return None

    def _abrir(self) -> None:
        try:
            self.conexao = serial.Serial(self.porta, ARDUINO_BAUDRATE,
                                         timeout=ARDUINO_TIMEOUT)
            time.sleep(2.5)      # o Uno reinicia ao abrir a porta e se calibra
            self.conexao.reset_input_buffer()
        except Exception as erro:
            print(f"[Hardware] Não consegui abrir {self.porta}: {erro}")
            self.conexao = None

    @property
    def conectado(self) -> bool:
        return self.conexao is not None and self.conexao.is_open

    # ------------------------------------------------------------------ #
    def enviar(self, comando: str) -> str:
        """Envia um comando e devolve a linha de resposta ('' em caso de erro)."""
        if not self.conectado:
            return ""
        try:
            self.conexao.reset_input_buffer()
            self.conexao.write((comando + "\n").encode("ascii"))
            return self.conexao.readline().decode("ascii", errors="ignore").strip()
        except Exception as erro:
            # Cabo puxado no meio da operação, por exemplo
            print(f"[Hardware] Conexão perdida: {erro}")
            self.conexao = None
            return ""

    def testar(self) -> bool:
        return any(self.enviar("PING") == "PONG" for _ in range(3))

    def ler(self) -> Leitura:
        """Pede uma medição: resposta 'D:23.4' (ou 'D:-1.0' se o sensor falhar)."""
        resposta = self.enviar("LER")
        try:
            distancia = float(resposta.split("D:", 1)[1])
        except (IndexError, ValueError):
            return Leitura(None)
        return Leitura(distancia if distancia > 0 else None)

    def calibrar(self) -> float | None:
        """Mede o piso seco e devolve a distância base."""
        resposta = self.enviar("CALIBRAR")
        if resposta.startswith("BASE:"):
            return float(resposta.split(":", 1)[1])
        return None

    def definir_nivel(self, nivel: int) -> None:
        """Aplica o padrão do LED do nível."""
        self.enviar(f"NIVEL:{nivel}")

    def gesto(self) -> None:
        """Balança a cabeça para chamar atenção."""
        self.enviar("GESTO")

    def fechar(self) -> None:
        if self.conectado:
            self.definir_nivel(SECO)
            self.conexao.close()


# ====================================================================== #
# Simulador
# ====================================================================== #
class SimuladorArduino:
    """
    Reproduz um alagamento, uma leitura por chamada de ler():
      piso seco -> a água começa a subir rápido -> alaga ->
      fica parada -> escoa devagar -> o sensor falha por alguns segundos.
    """

    BASE_CM = 25.0

    def __init__(self, ruido: float = 0.15):
        self.passo = 0
        self.ruido = ruido
        self.nivel = SECO
        self.gestos = 0
        self.conectado = True
        print("[Hardware] Modo SIMULADO: nenhum Arduino necessário.")

    def _lamina(self) -> float:
        p = self.passo
        if p < 15:
            return 0.0
        if p < 27:                       # água subindo 0,4 cm por leitura
            return (p - 15) * 0.4
        if p < 45:                       # alagado, nível parado
            return 4.6
        return max(0.0, 4.6 - (p - 45) * 0.15)   # escoando devagar

    def testar(self) -> bool:
        return True

    def ler(self) -> Leitura:
        self.passo += 1
        if 85 <= self.passo < 91:        # sensor desconectado por um tempo
            return Leitura(None)
        distancia = self.BASE_CM - self._lamina() + random.uniform(-self.ruido, self.ruido)
        return Leitura(round(distancia, 1))

    def calibrar(self) -> float:
        return self.BASE_CM

    def definir_nivel(self, nivel: int) -> None:
        self.nivel = nivel

    def gesto(self) -> None:
        self.gestos += 1

    def fechar(self) -> None:
        pass
