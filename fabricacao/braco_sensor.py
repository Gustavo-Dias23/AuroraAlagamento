"""
braco_sensor.py
Geometria paramétrica do BRAÇO DO SENSOR da estação de alagamento.

O braço é parafusado na lateral do corpo da Aurora (do CP4) e segura o
ultrassônico HC-SR04 apontado para baixo, sobre a bacia com água.

São 3 peças de MDF 6 mm. A montagem usa SÓ COLA DE MADEIRA (PVA):

    placa de fixação  -> colada na lateral do corpo
    haste             -> encaixa na placa e segura o sensor na ponta
    mão-francesa      -> triângulo de reforço, encaixado na placa e na haste

O HC-SR04 não é colado: ele fica apoiado em cima da haste, com os dois
cilindros encaixados nos furos e apontados para baixo. A gravidade segura.

Este módulo não depende de nenhuma biblioteca: só calcula contornos e
furos. Quem desenha são gerar_dxf_braco.py (corte a laser) e
fusion_braco_sensor.py (modelo 3D no Fusion 360).

Todas as medidas em MILÍMETROS.

Sistema de coordenadas da montagem (o mesmo do modelo da Aurora):
    origem no centro do corpo, no chão; z para cima;
    a lateral onde o braço é preso é a face x = +50 (lado direito).
"""

PARAMETROS = {
    # Chapa — meça a sua com paquímetro e ajuste!
    "esp": 6.0,

    # Corpo da Aurora (CP4)
    "corpo_meia_largura": 50.0,     # a face externa da lateral fica em x = +50
    "corpo_altura": 150.0,

    # Placa de fixação (encostada na lateral)
    "placa_largura": 60.0,
    "placa_altura": 70.0,
    "placa_topo": 146.0,            # altura do topo da placa em relação ao chão

    # Haste
    "haste_comprimento": 150.0,     # a partir da face da placa
    "haste_largura": 40.0,
    "haste_folga_topo": 4.0,        # quanto a haste fica abaixo do topo da placa
    "aba_largura": 10.0,            # abas que entram na placa

    # Mão-francesa
    "mf_altura": 54.0,
    "mf_comprimento": 60.0,
    "mf_aba": 30.0,                 # comprimento das abas da mão-francesa

    # HC-SR04 — meça o seu: varia entre fabricantes
    "sensor_furo": 16.5,            # cilindros de 16 mm: encaixe justo, sem cola
    "sensor_entre_centros": 26.0,   # distância entre os centros dos transdutores
    "sensor_recuo_ponta": 15.0,     # do centro do 1º transdutor até a ponta
}


# ====================================================================== #
# Auxiliares
# ====================================================================== #
def _retangulo(x0, y0, x1, y1):
    """Contorno fechado de um retângulo pelos cantos (sentido anti-horário)."""
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _peca(nome, espessura, contorno, circulos=None, retangulos=None, nota=""):
    return {
        "nome": nome,
        "espessura": espessura,
        "contorno": contorno,
        "circulos": circulos or [],     # (cx, cy, raio)
        "retangulos": retangulos or [], # contornos fechados (furos retangulares)
        "nota": nota,
    }


def caixa_envolvente(peca):
    xs = [x for x, _ in peca["contorno"]]
    ys = [y for _, y in peca["contorno"]]
    return min(xs), min(ys), max(xs), max(ys)


# ====================================================================== #
# Medidas derivadas (uma fonte só para peças e posições)
# ====================================================================== #
def _medidas(p):
    t = p["esp"]
    m = {}
    m["placa_base"] = p["placa_topo"] - p["placa_altura"]           # z da base da placa
    m["haste_z_topo"] = p["placa_topo"] - p["haste_folga_topo"]     # z do topo da haste
    m["haste_z_base"] = m["haste_z_topo"] - t                       # z da base da haste
    m["mf_z_base"] = m["haste_z_base"] - p["mf_altura"]             # z da base da mão-francesa

    # Abas da haste: simétricas em relação ao centro da haste (em y)
    meia = p["haste_largura"] / 2
    a = p["aba_largura"]
    m["abas_haste_y"] = [(-meia + 3, -meia + 3 + a), (meia - 3 - a, meia - 3)]

    # Abas da mão-francesa: centralizadas nas pernas
    m["mf_aba_v"] = ((p["mf_altura"] - p["mf_aba"]) / 2,
                     (p["mf_altura"] + p["mf_aba"]) / 2)            # na perna vertical
    m["mf_aba_u"] = ((p["mf_comprimento"] - p["mf_aba"]) / 2,
                     (p["mf_comprimento"] + p["mf_aba"]) / 2)       # na perna horizontal
    return m


# ====================================================================== #
# Peças
# ====================================================================== #
def peca_placa(p=PARAMETROS):
    """
    Placa vertical encostada na lateral do corpo.
    Coordenadas locais: x = largura (y global), y = altura (z global).
    """
    t = p["esp"]
    m = _medidas(p)
    L, H = p["placa_largura"], p["placa_altura"]
    centro = L / 2

    # Rasgos das abas da haste
    zh0 = m["haste_z_base"] - m["placa_base"]
    rasgos = [_retangulo(centro + y0, zh0, centro + y1, zh0 + t)
              for y0, y1 in m["abas_haste_y"]]

    # Rasgo da aba vertical da mão-francesa
    zmf = m["mf_z_base"] - m["placa_base"]
    v0, v1 = m["mf_aba_v"]
    rasgos.append(_retangulo(centro - t / 2, zmf + v0, centro + t / 2, zmf + v1))

    return _peca("braco_placa", t, _retangulo(0, 0, L, H), None, rasgos,
                 "Placa de fixação: colada na lateral do corpo")


def peca_haste(p=PARAMETROS):
    """
    Haste horizontal. Coordenadas locais: x = comprimento (0 na face da
    placa; as abas vão de -esp a 0), y = largura.
    """
    t = p["esp"]
    m = _medidas(p)
    C, W = p["haste_comprimento"], p["haste_largura"]
    meia = W / 2

    # Contorno com as duas abas na ponta interna (x < 0)
    (a0, a1), (b0, b1) = [(y0 + meia, y1 + meia) for y0, y1 in m["abas_haste_y"]]
    contorno = [
        (0, 0), (C, 0), (C, W), (0, W),
        (0, b1), (-t, b1), (-t, b0), (0, b0),
        (0, a1), (-t, a1), (-t, a0), (0, a0),
    ]

    # Rasgo da aba superior da mão-francesa
    u0, u1 = m["mf_aba_u"]
    rasgos = [_retangulo(u0, meia - t / 2, u1, meia + t / 2)]

    # Furos dos transdutores do HC-SR04
    x1 = C - p["sensor_recuo_ponta"]
    x2 = x1 - p["sensor_entre_centros"]
    raio = p["sensor_furo"] / 2
    furos = [(x1, meia, raio), (x2, meia, raio)]

    return _peca("braco_haste", t, contorno, furos, rasgos,
                 "Haste: segura o HC-SR04 apontado para baixo")


def peca_mao_francesa(p=PARAMETROS):
    """
    Triângulo de reforço. Coordenadas locais: u = horizontal (0 na face da
    placa), v = vertical (0 na base, mf_altura no lado de baixo da haste).
    """
    t = p["esp"]
    m = _medidas(p)
    A, C = p["mf_altura"], p["mf_comprimento"]
    v0, v1 = m["mf_aba_v"]
    u0, u1 = m["mf_aba_u"]

    contorno = [
        (0, 0),
        (0, v0), (-t, v0), (-t, v1), (0, v1),     # aba que entra na placa
        (0, A),
        (u0, A), (u0, A + t), (u1, A + t), (u1, A),  # aba que entra na haste
        (C, A),
    ]
    return _peca("braco_mao_francesa", t, contorno,
                 nota="Mão-francesa: reforço entre a placa e a haste")


def todas_as_pecas(p=PARAMETROS):
    return [peca_placa(p), peca_haste(p), peca_mao_francesa(p)]


# ====================================================================== #
# Posição de cada peça na montagem: (eixo_u, eixo_v, origem em mm)
# A espessura cresce na direção u × v.
# ====================================================================== #
def posicoes_montagem(p=PARAMETROS):
    t = p["esp"]
    m = _medidas(p)
    face = p["corpo_meia_largura"]                 # x = 50
    return {
        # Placa: local x -> y global, local y -> z; espessura para +x
        "braco_placa": ((0, 1, 0), (0, 0, 1),
                        (face, -p["placa_largura"] / 2, m["placa_base"])),
        # Haste: local x -> +x, local y -> +y; espessura para +z
        "braco_haste": ((1, 0, 0), (0, 1, 0),
                        (face + t, -p["haste_largura"] / 2, m["haste_z_base"])),
        # Mão-francesa: local u -> +x, local v -> +z; espessura para -y
        "braco_mao_francesa": ((1, 0, 0), (0, 0, 1),
                               (face + t, t / 2, m["mf_z_base"])),
    }


def centro_do_sensor(p=PARAMETROS):
    """Ponto (x, y, z) no centro do HC-SR04, sobre a haste — onde vai a bacia."""
    t = p["esp"]
    m = _medidas(p)
    x1 = p["corpo_meia_largura"] + t + p["haste_comprimento"] - p["sensor_recuo_ponta"]
    xm = x1 - p["sensor_entre_centros"] / 2
    return xm, 0.0, m["haste_z_topo"]
