"""
estacao.py
Classe EstacaoAlagamento — o "cérebro" da Aurora na Global Solution.

A cada ciclo ela:
  1. lê o ultrassônico pelo Arduino;
  2. calcula a lâmina d'água em relação ao piso seco;
  3. classifica o risco (seco, poça, alagado) e decide se a água está
     subindo rápido (modo atenção);
  4. aciona o LED, balança a cabeça, gera o aviso com IA e fala;
  5. registra tudo em CSV e envia o relato ao MVP.

Ela não depende de comando nenhum: decide sozinha a partir das leituras.
"""

import csv
import time
from datetime import datetime

from .classificador import ClassificadorAlagamento
from .config import (
    ARQUIVO_EVENTOS,
    ARQUIVO_LEITURAS,
    FALHAS_PARA_ALERTA,
    INTERVALO_ATENCAO_S,
    INTERVALO_NORMAL_S,
    REPETIR_ALERTA_S,
)
from .hardware import ALAGADO, FALHA, NOMES_NIVEIS, POCA, SECO
from .ia import FRASES_LOCAIS


class EstacaoAlagamento:
    """Orquestra sensor, classificação, IA, voz e envio ao MVP (composição)."""

    def __init__(self, hardware, voz, ia, mvp, classificador=None,
                 relogio=time.monotonic, dormir=time.sleep):
        self.hardware = hardware
        self.voz = voz
        self.ia = ia
        self.mvp = mvp
        self.classificador = classificador or ClassificadorAlagamento()
        self.relogio = relogio
        self.dormir = dormir

        self.base_cm: float | None = None
        self.ativa = True
        self.em_falha = False
        self.falhas_seguidas = 0
        self.ultimo_alerta = float("-inf")
        self.ciclos = 0

    # ================================================================== #
    # Calibração
    # ================================================================== #
    def calibrar(self) -> bool:
        """Mede a distância até o piso SECO, que vira a referência (lâmina zero)."""
        base = self.hardware.calibrar()
        if base is None:
            self.voz.falar("Não consegui calibrar. Confira o sensor ultrassônico.")
            return False
        self.base_cm = base
        self.voz.falar(f"Estação calibrada. Piso seco a {base:.0f} centímetros do sensor.")
        return True

    # ================================================================== #
    # Ciclo principal
    # ================================================================== #
    def ciclo(self) -> float:
        """Executa uma leitura completa. Devolve quantos segundos esperar."""
        self.ciclos += 1
        leitura = self.hardware.ler()
        agora = self.relogio()

        # ---- Falha do sensor ultrassônico -------------------------------
        if leitura.distancia is None:
            self.falhas_seguidas += 1
            nivel_log = FALHA if self.em_falha else self.classificador.nivel
            self._registrar_leitura(leitura, None, nivel_log)
            if self.falhas_seguidas == FALHAS_PARA_ALERTA:
                self._entrar_em_falha()
            if self.em_falha:
                self.hardware.definir_nivel(FALHA)
            return INTERVALO_NORMAL_S

        if self.em_falha:
            self._sair_da_falha()
        self.falhas_seguidas = 0

        # ---- Classificação ----------------------------------------------
        lamina = max(0.0, self.base_cm - leitura.distancia)
        anterior = self.classificador.nivel
        atencao_antes = self.classificador.modo_atencao
        nivel = self.classificador.atualizar(lamina, agora)
        atencao = self.classificador.modo_atencao
        self._registrar_leitura(leitura, lamina, nivel)

        # Reenvia o nível a cada ciclo: se o Arduino tiver reiniciado ou
        # entrado em modo local, ele volta a obedecer o notebook.
        self.hardware.definir_nivel(nivel)

        if atencao != atencao_antes:
            self._mudar_modo(atencao, lamina)

        contexto = {
            "nivel": nivel,
            "nivel_anterior": anterior,
            "lamina_cm": lamina,
            "tendencia_cm_min": self.classificador.tendencia,
            "modo_atencao": atencao,
        }
        if nivel != anterior:
            self._alertar(contexto, mudou=True)
        elif nivel in (POCA, ALAGADO) and agora - self.ultimo_alerta >= REPETIR_ALERTA_S:
            self._alertar(contexto, mudou=False)     # reforço periódico do aviso

        self.mvp.reenviar_pendentes()
        return INTERVALO_ATENCAO_S if (atencao or nivel > SECO) else INTERVALO_NORMAL_S

    def executar(self, max_ciclos: int | None = None) -> None:
        """Laço contínuo até Ctrl+C (ou até max_ciclos, usado nos testes)."""
        if self.base_cm is None and not self.calibrar():
            return
        try:
            while self.ativa and (max_ciclos is None or self.ciclos < max_ciclos):
                self.dormir(self.ciclo())
        except KeyboardInterrupt:
            print("\n[Estação] Encerrada pelo usuário.")
        finally:
            self.hardware.fechar()

    # ================================================================== #
    # Reações
    # ================================================================== #
    def _alertar(self, contexto: dict, mudou: bool) -> None:
        # A cabeça balança quando há água (não ao voltar para seco)
        if contexto["nivel"] in (POCA, ALAGADO):
            self.hardware.gesto()
        texto, origem = self.ia.gerar(contexto)
        self.voz.falar(texto)
        self.ultimo_alerta = self.relogio()
        self._registrar_evento(contexto, texto, origem)
        if mudou:
            self.mvp.enviar(self.mvp.montar_relato(contexto, texto))

    def _mudar_modo(self, atencao: bool, lamina: float) -> None:
        if atencao:
            texto = "A água está subindo rápido. Entrando em modo atenção: vou alertar mais cedo."
        else:
            texto = "A água parou de subir rápido. Voltando ao modo padrão."
        self.voz.falar(texto)
        self._registrar_evento(
            {"nivel": self.classificador.nivel, "lamina_cm": lamina, "modo_atencao": atencao},
            texto, "sistema",
        )

    def _entrar_em_falha(self) -> None:
        self.em_falha = True
        self.hardware.definir_nivel(FALHA)
        texto = FRASES_LOCAIS[FALHA]
        self.voz.falar(texto)
        contexto = {"nivel": FALHA, "nivel_anterior": self.classificador.nivel,
                    "lamina_cm": None, "tendencia_cm_min": None,
                    "modo_atencao": self.classificador.modo_atencao}
        self._registrar_evento(contexto, texto, "sistema")
        self.mvp.enviar(self.mvp.montar_relato(contexto, texto))

    def _sair_da_falha(self) -> None:
        self.em_falha = False
        texto = "Sensor de nível funcionando de novo."
        self.voz.falar(texto)
        self.hardware.definir_nivel(self.classificador.nivel)
        self._registrar_evento({"nivel": self.classificador.nivel, "lamina_cm": None,
                                "modo_atencao": self.classificador.modo_atencao},
                               texto, "sistema")

    # ================================================================== #
    # Registro em CSV
    # ================================================================== #
    @staticmethod
    def _anexar_csv(caminho, cabecalho: list[str], linha: list) -> None:
        novo = not caminho.exists()
        with open(caminho, "a", newline="", encoding="utf-8") as arquivo:
            escritor = csv.writer(arquivo)
            if novo:
                escritor.writerow(cabecalho)
            escritor.writerow(linha)

    def _registrar_leitura(self, leitura, lamina, nivel) -> None:
        tendencia = self.classificador.tendencia
        self._anexar_csv(
            ARQUIVO_LEITURAS,
            ["data_hora", "distancia_cm", "lamina_cm", "tendencia_cm_min",
             "modo_atencao", "nivel"],
            [datetime.now().isoformat(timespec="seconds"),
             leitura.distancia, None if lamina is None else round(lamina, 2),
             tendencia, self.classificador.modo_atencao, NOMES_NIVEIS[nivel]],
        )
        texto_lamina = "  --  " if lamina is None else f"{lamina:4.1f} cm"
        texto_tend = "--" if tendencia is None else f"{tendencia:+.1f} cm/min"
        print(f"[Leitura] dist={leitura.distancia}  lâmina={texto_lamina}  "
              f"tendência={texto_tend}  nível={NOMES_NIVEIS[nivel]}")

    def _registrar_evento(self, contexto: dict, texto: str, origem: str) -> None:
        lamina = contexto.get("lamina_cm")
        self._anexar_csv(
            ARQUIVO_EVENTOS,
            ["data_hora", "nivel", "lamina_cm", "modo_atencao", "origem_texto", "texto"],
            [datetime.now().isoformat(timespec="seconds"), NOMES_NIVEIS[contexto["nivel"]],
             None if lamina is None else round(lamina, 2), contexto["modo_atencao"],
             origem, texto],
        )
