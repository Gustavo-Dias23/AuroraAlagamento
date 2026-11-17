"""
voz.py
Classe Voz — fala os alertas no alto-falante do computador.

- macOS: comando nativo 'say' com a voz Luciana (pt-BR). Evita o bug do
  pyttsx3 2.90 no Mac ("name 'objc' is not defined").
- Windows e Linux: pyttsx3.
- Sem nenhum motor disponível: o texto só aparece no terminal.
"""

import platform
import subprocess

from .config import VELOCIDADE_FALA, VOLUME_FALA

try:
    import pyttsx3
except Exception:
    pyttsx3 = None


class Voz:
    def __init__(self, velocidade: int = VELOCIDADE_FALA, volume: float = VOLUME_FALA,
                 silenciosa: bool = False):
        self.velocidade = velocidade
        self.volume = max(0.0, min(1.0, volume))
        self.silenciosa = silenciosa
        self.usar_say = False
        self.motor = None
        if not silenciosa:
            self._iniciar_motor()

    def _iniciar_motor(self) -> None:
        if platform.system() == "Darwin":
            self.usar_say = True
            return
        if pyttsx3 is None:
            return
        try:
            self.motor = pyttsx3.init()
            self.motor.setProperty("rate", self.velocidade)
            self.motor.setProperty("volume", self.volume)
            for voz in self.motor.getProperty("voices"):
                nome = f"{voz.id} {getattr(voz, 'name', '')}".lower()
                if any(t in nome for t in ("brazil", "portug", "pt_br", "pt-br")):
                    self.motor.setProperty("voice", voz.id)
                    break
        except Exception as erro:
            print(f"[Voz] pyttsx3 indisponível ({erro}); só texto no terminal.")
            self.motor = None

    def falar(self, texto: str) -> None:
        print(f"[Aurora] {texto}")
        if self.silenciosa:
            return
        if self.usar_say:
            comando = ["say", "-r", str(self.velocidade), f"[[volm {self.volume:.2f}]] {texto}"]
            for voz_ptbr in ("Luciana", "Felipe"):
                try:
                    subprocess.run([comando[0], "-v", voz_ptbr, *comando[1:]], check=True)
                    return
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            subprocess.run(comando, check=False)
        elif self.motor is not None:
            try:
                self.motor.say(texto)
                self.motor.runAndWait()
            except Exception as erro:
                print(f"[Voz] Falha ao falar: {erro}")
