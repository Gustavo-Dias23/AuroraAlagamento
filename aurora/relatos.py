"""
relatos.py
Classe ClienteMVP — envia os relatos de alagamento para o MVP da equipe
(POST /api/relatos), para que o ponto apareça no mapa do site.

Sem internet, os relatos vão para uma fila em disco (dados/fila_relatos.json)
e são reenviados automaticamente quando a conexão volta. Nada se perde.

Ajuste o formato do 'relato' em montar_relato() para bater com a API do
MVP de vocês.
"""

import json
import time
from datetime import datetime

import requests

from .config import (
    ARQUIVO_FILA,
    LATITUDE,
    LONGITUDE,
    MVP_API_URL,
    MVP_TOKEN,
    NOME_ESTACAO,
    REENVIO_FILA_S,
)
from .hardware import NOMES_NIVEIS


class ClienteMVP:
    def __init__(self, url: str = MVP_API_URL, token: str = MVP_TOKEN):
        self.url = url
        self.token = token
        self._ultima_tentativa = 0.0
        self.fila: list[dict] = self._carregar_fila()

    @property
    def configurado(self) -> bool:
        return bool(self.url)

    # ------------------------------------------------------------------ #
    @staticmethod
    def montar_relato(contexto: dict, alerta: str) -> dict:
        lamina = contexto.get("lamina_cm")
        return {
            "origem": "robo",
            "tipo": "alagamento",
            "estacao": NOME_ESTACAO,
            "nivel": NOMES_NIVEIS[contexto["nivel"]],
            "lamina_cm": None if lamina is None else round(lamina, 1),
            "tendencia_cm_min": contexto.get("tendencia_cm_min"),
            "subida_rapida": contexto["modo_atencao"],
            "descricao": alerta,
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "data_hora": datetime.now().isoformat(timespec="seconds"),
        }

    # ------------------------------------------------------------------ #
    def enviar(self, relato: dict) -> None:
        """Tenta enviar agora; se falhar, guarda na fila."""
        if not self.configurado:
            return
        if not self._post(relato):
            self.fila.append(relato)
            self._salvar_fila()
            print(f"[MVP] Sem conexão: relato guardado ({len(self.fila)} na fila).")

    def reenviar_pendentes(self, forcar: bool = False) -> None:
        """Tenta esvaziar a fila, no máximo a cada REENVIO_FILA_S segundos."""
        if not self.configurado or not self.fila:
            return
        if not forcar and time.monotonic() - self._ultima_tentativa < REENVIO_FILA_S:
            return
        self._ultima_tentativa = time.monotonic()

        enviados = 0
        while self.fila and self._post(self.fila[0]):
            self.fila.pop(0)
            enviados += 1
        if enviados:
            self._salvar_fila()
            print(f"[MVP] Conexão de volta: {enviados} relato(s) enviados da fila.")

    # ------------------------------------------------------------------ #
    def _post(self, relato: dict) -> bool:
        cabecalhos = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            resposta = requests.post(self.url, json=relato, headers=cabecalhos, timeout=5)
            return resposta.status_code < 300
        except Exception:
            return False

    def _carregar_fila(self) -> list[dict]:
        try:
            return json.loads(ARQUIVO_FILA.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _salvar_fila(self) -> None:
        ARQUIVO_FILA.write_text(json.dumps(self.fila, ensure_ascii=False, indent=2),
                                encoding="utf-8")
