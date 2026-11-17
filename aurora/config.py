"""
config.py
Parâmetros da estação de alagamento. Tudo que pode precisar de ajuste
fica aqui ou no arquivo .env, para não mexer no resto do código.
Todas as distâncias estão em centímetros.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "dados"
PASTA_DADOS.mkdir(parents=True, exist_ok=True)

ARQUIVO_LEITURAS = PASTA_DADOS / "leituras.csv"      # histórico de medições
ARQUIVO_EVENTOS = PASTA_DADOS / "eventos.csv"        # mudanças de nível e alertas
ARQUIVO_FILA = PASTA_DADOS / "fila_relatos.json"     # relatos aguardando internet

# ---------------------------------------------------------------------------
# Estação
# ---------------------------------------------------------------------------
NOME_ESTACAO = os.getenv("NOME_ESTACAO", "Aurora - Ciclovia (ponto de teste)")
# Sem GPS: coordenada fixa do ponto monitorado, documentada no README
LATITUDE = float(os.getenv("LATITUDE", "-23.5740"))
LONGITUDE = float(os.getenv("LONGITUDE", "-46.6230"))

# ---------------------------------------------------------------------------
# Arduino
# ---------------------------------------------------------------------------
ARDUINO_PORTA = os.getenv("ARDUINO_PORTA") or None   # vazio = detecção automática
ARDUINO_BAUDRATE = 9600
ARDUINO_TIMEOUT = 2.0

# ---------------------------------------------------------------------------
# Sensor ultrassônico e classificação
# ---------------------------------------------------------------------------
# Lâmina d'água (base seca - distância medida) para cada nível
LAMINA_POCA_CM = float(os.getenv("LAMINA_POCA_CM", "1.0"))
LAMINA_ALAGADO_CM = float(os.getenv("LAMINA_ALAGADO_CM", "3.0"))

# MODO ATENÇÃO: quando a água sobe rápido, a estação passa a alertar mais
# cedo (limiares multiplicados pelo fator) e lê com mais frequência.
# Liga acima de TENDENCIA_ATENCAO_LIGA e desliga abaixo de _DESLIGA (cm/min).
TENDENCIA_ATENCAO_LIGA = float(os.getenv("TENDENCIA_ATENCAO_LIGA", "1.0"))
TENDENCIA_ATENCAO_DESLIGA = float(os.getenv("TENDENCIA_ATENCAO_DESLIGA", "0.3"))
FATOR_MODO_ATENCAO = 0.5

# Confirmações seguidas exigidas para mudar de nível. Subir é rápido
# (segurança primeiro); descer é lento (evita "liga-desliga" com ondas).
CONFIRMACOES_SUBIR = 2
CONFIRMACOES_DESCER = 5

# Leituras inválidas seguidas até declarar falha de sensor
FALHAS_PARA_ALERTA = 4

# Intervalo entre leituras (segundos)
INTERVALO_NORMAL_S = float(os.getenv("INTERVALO_NORMAL_S", "2.0"))
INTERVALO_ATENCAO_S = float(os.getenv("INTERVALO_ATENCAO_S", "1.0"))

# Janela usada para calcular a tendência (cm por minuto)
JANELA_TENDENCIA = 10

# Enquanto houver poça ou alagamento, o aviso falado é repetido a cada:
REPETIR_ALERTA_S = float(os.getenv("REPETIR_ALERTA_S", "60"))

# ---------------------------------------------------------------------------
# Voz
# ---------------------------------------------------------------------------
VELOCIDADE_FALA = 180
VOLUME_FALA = float(os.getenv("VOLUME_FALA", "1.0"))

# ---------------------------------------------------------------------------
# IA generativa (Google Gemini via REST)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODELO = os.getenv("GEMINI_MODELO", "gemini-2.5-flash")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{modelo}:generateContent"
)

PROMPT_SISTEMA = (
    "Você é a Aurora, uma estação de monitoramento de alagamento instalada "
    "em um ponto crítico de uma ciclovia. Você recebe as leituras dos "
    "sensores e gera o aviso que será FALADO em voz alta para os ciclistas "
    "que se aproximam. Regras: português do Brasil; no máximo 2 frases "
    "curtas; diga o que está acontecendo e o que o ciclista deve fazer "
    "(reduzir a velocidade, desmontar e empurrar a bicicleta ou usar uma "
    "rota alternativa); leve em conta se a água está subindo, estável ou "
    "baixando; não invente "
    "números que não estejam nos dados; sem emojis, markdown ou listas."
)

# ---------------------------------------------------------------------------
# Integração com o MVP (opcional)
# ---------------------------------------------------------------------------
# Ex.: https://seu-mvp.com/api/relatos  — vazio desliga o envio
MVP_API_URL = os.getenv("MVP_API_URL", "")
MVP_TOKEN = os.getenv("MVP_TOKEN", "")
REENVIO_FILA_S = 30
