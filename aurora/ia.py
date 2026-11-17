"""
ia.py
Classe GeradorAlertas — usa o Google Gemini para interpretar as leituras
dos sensores e criar o aviso falado para os ciclistas.

A IA recebe o contexto completo (nível, lâmina d'água, tendência de subida,
horário) e devolve uma resposta contextualizada. Se a internet ou a API
falharem, a estação usa frases prontas: o alerta nunca deixa de sair.

A chave vai no cabeçalho 'x-goog-api-key' (formato exigido pelas chaves
novas do Google, com prefixo 'AQ.').
"""

from datetime import datetime

import requests

from .config import GEMINI_API_KEY, GEMINI_MODELO, GEMINI_URL, PROMPT_SISTEMA
from .hardware import ALAGADO, FALHA, NOMES_NIVEIS, POCA, SECO

# Frases usadas quando a IA não está disponível
FRASES_LOCAIS = {
    SECO: "Ciclovia liberada. A água baixou neste trecho.",
    POCA: "Atenção, ciclista: água acumulada na ciclovia logo à frente. Reduza a velocidade.",
    ALAGADO: ("Perigo: ciclovia alagada neste trecho. Desça da bicicleta "
              "ou use uma rota alternativa."),
    FALHA: "Aviso: o sensor de nível da estação está com problema. Redobre a atenção.",
}


class GeradorAlertas:
    """Gera o texto do alerta com o Gemini, com frases prontas como reserva."""

    def __init__(self, chave: str = GEMINI_API_KEY, modelo: str = GEMINI_MODELO):
        self.chave = chave
        self.modelo = modelo

    @property
    def configurada(self) -> bool:
        return bool(self.chave)

    # ------------------------------------------------------------------ #
    @staticmethod
    def descrever_contexto(contexto: dict) -> str:
        """Transforma as leituras em texto para o modelo."""
        tendencia = contexto.get("tendencia_cm_min")
        if tendencia is None:
            texto_tendencia = "indefinida"
        elif tendencia > 0.2:
            texto_tendencia = f"subindo {tendencia} cm por minuto"
        elif tendencia < -0.2:
            texto_tendencia = f"baixando {abs(tendencia)} cm por minuto"
        else:
            texto_tendencia = "estável"

        return (
            f"Nível de risco: {NOMES_NIVEIS[contexto['nivel']]} "
            f"(antes: {NOMES_NIVEIS[contexto['nivel_anterior']]}). "
            f"Lâmina d'água: {contexto['lamina_cm']:.1f} cm. "
            f"Água {texto_tendencia}. "
            f"Modo atenção (água subindo rápido): {'sim' if contexto['modo_atencao'] else 'não'}. "
            f"Horário: {datetime.now():%H:%M}."
        )

    # ------------------------------------------------------------------ #
    def gerar(self, contexto: dict) -> tuple[str, str]:
        """Devolve (texto do alerta, origem), em que origem é 'gemini' ou 'local'."""
        texto = self._perguntar_gemini(self.descrever_contexto(contexto))
        if texto:
            return texto, "gemini"
        return FRASES_LOCAIS[contexto["nivel"]], "local"

    def _perguntar_gemini(self, dados: str) -> str | None:
        if not self.configurada:
            return None

        url = GEMINI_URL.format(modelo=self.modelo)
        cabecalhos = {"x-goog-api-key": self.chave}
        corpo = {
            "system_instruction": {"parts": [{"text": PROMPT_SISTEMA}]},
            "contents": [{"role": "user", "parts": [{"text": dados}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 200,
                # Os modelos 2.5+ "pensam" antes de responder e isso consome
                # o orçamento de tokens, truncando o aviso. Zeramos o thinking.
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        try:
            resposta = requests.post(url, json=corpo, headers=cabecalhos, timeout=8)
            resposta.raise_for_status()
            texto = resposta.json()["candidates"][0]["content"]["parts"][0]["text"]
            return texto.strip() or None
        except Exception as erro:
            print(f"[IA] Gemini indisponível ({type(erro).__name__}); usando frase local.")
            return None
