"""
classificador.py
Classifica o risco do ponto monitorado (seco, poça ou alagado) a partir
da lâmina d'água medida pelo ultrassônico, e decide sozinho quando entrar
em MODO ATENÇÃO (água subindo rápido).

A classificação de segurança é feita por regras locais de propósito:
ela precisa funcionar sempre, mesmo sem internet. A IA generativa entra
depois, para interpretar o contexto e criar o aviso falado (ia.py).
"""

from collections import deque

from .config import (
    CONFIRMACOES_DESCER,
    CONFIRMACOES_SUBIR,
    FATOR_MODO_ATENCAO,
    JANELA_TENDENCIA,
    LAMINA_ALAGADO_CM,
    LAMINA_POCA_CM,
    TENDENCIA_ATENCAO_DESLIGA,
    TENDENCIA_ATENCAO_LIGA,
)
from .hardware import ALAGADO, POCA, SECO


class ClassificadorAlagamento:
    """Decide o nível de risco e o modo atenção a partir das leituras."""

    def __init__(
        self,
        lamina_poca: float = LAMINA_POCA_CM,
        lamina_alagado: float = LAMINA_ALAGADO_CM,
        fator_atencao: float = FATOR_MODO_ATENCAO,
        atencao_liga: float = TENDENCIA_ATENCAO_LIGA,
        atencao_desliga: float = TENDENCIA_ATENCAO_DESLIGA,
        confirmacoes_subir: int = CONFIRMACOES_SUBIR,
        confirmacoes_descer: int = CONFIRMACOES_DESCER,
        janela: int = JANELA_TENDENCIA,
    ):
        self.lamina_poca = lamina_poca
        self.lamina_alagado = lamina_alagado
        self.fator_atencao = fator_atencao
        self.atencao_liga = atencao_liga
        self.atencao_desliga = atencao_desliga
        self.confirmacoes_subir = confirmacoes_subir
        self.confirmacoes_descer = confirmacoes_descer

        self.nivel = SECO
        self.modo_atencao = False
        self.tendencia: float | None = None       # cm/min; positivo = subindo
        self._candidato = SECO
        self._contagem = 0
        self._subida_seguida = 0                  # leituras seguidas subindo rápido
        self._historico: deque[tuple[float, float]] = deque(maxlen=janela)

    # ------------------------------------------------------------------ #
    def atualizar(self, lamina: float, instante: float) -> int:
        """Registra uma leitura e devolve o nível confirmado."""
        self._historico.append((instante, lamina))
        self.tendencia = self._calcular_tendencia()
        self._atualizar_modo_atencao()
        return self._confirmar_nivel(self.nivel_bruto(lamina))

    # ------------------------------------------------------------------ #
    def limiares(self) -> tuple[float, float]:
        """Com a água subindo rápido, os limiares caem: alerta mais cedo."""
        fator = self.fator_atencao if self.modo_atencao else 1.0
        return self.lamina_poca * fator, self.lamina_alagado * fator

    def nivel_bruto(self, lamina: float) -> int:
        """Nível de uma única leitura, sem confirmação."""
        poca, alagado = self.limiares()
        if lamina >= alagado:
            return ALAGADO
        if lamina >= poca:
            return POCA
        return SECO

    # ------------------------------------------------------------------ #
    def _atualizar_modo_atencao(self) -> None:
        """
        Liga quando a água sobe mais rápido que 'atencao_liga' por 2 leituras
        seguidas (uma leitura com erro sozinha não basta) e só desliga
        quando a subida cai abaixo de 'atencao_desliga'. Os dois limites
        diferentes (histerese) evitam que o modo fique ligando e desligando.
        """
        if self.tendencia is None:
            return
        if self.tendencia >= self.atencao_liga:
            self._subida_seguida += 1
        else:
            self._subida_seguida = 0

        if not self.modo_atencao and self._subida_seguida >= 2:
            self.modo_atencao = True
        elif self.modo_atencao and self.tendencia < self.atencao_desliga:
            self.modo_atencao = False

    def _confirmar_nivel(self, bruto: int) -> int:
        """
        Para mudar de nível, a mesma leitura precisa se repetir algumas
        vezes seguidas: poucas vezes para SUBIR (segurança primeiro) e
        mais vezes para DESCER (evita alternar com ondas na água).
        """
        if bruto == self.nivel:
            self._candidato, self._contagem = bruto, 0
            return self.nivel

        if bruto == self._candidato:
            self._contagem += 1
        else:
            self._candidato, self._contagem = bruto, 1

        exigido = self.confirmacoes_subir if bruto > self.nivel else self.confirmacoes_descer
        if self._contagem >= exigido:
            self.nivel = bruto
            self._contagem = 0
        return self.nivel

    def _calcular_tendencia(self) -> float | None:
        """
        Velocidade da água em cm/min pelo estimador de Theil-Sen: a MEDIANA
        das inclinações entre todos os pares de leituras da janela.

        Diferente da regressão linear comum, ele ignora leituras isoladas
        com erro (uma onda na água, um eco falso do ultrassônico) e só
        acusa subida quando a maioria das leituras concorda.
        """
        if len(self._historico) < 3:
            return None
        pontos = list(self._historico)
        inclinacoes = sorted(
            (l2 - l1) / (t2 - t1)
            for i, (t1, l1) in enumerate(pontos)
            for t2, l2 in pontos[i + 1:]
            if t2 != t1
        )
        if not inclinacoes:
            return None
        meio = len(inclinacoes) // 2
        mediana = (inclinacoes[meio] if len(inclinacoes) % 2
                   else (inclinacoes[meio - 1] + inclinacoes[meio]) / 2)
        return round(mediana * 60, 2)   # cm/s -> cm/min
