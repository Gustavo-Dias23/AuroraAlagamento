"""
fusion_braco_sensor.py
Script do Autodesk Fusion 360 que constrói o BRAÇO DO SENSOR da estação
de alagamento, já montado na posição em que vai ficar no corpo da Aurora.

O que aparece no modelo:
  - as 3 peças de MDF (placa, haste e mão-francesa), uma por componente;
  - referências transparentes: o corpo da Aurora, o HC-SR04 e a bacia,
    só para visualizar o conjunto (não são cortadas).

COMO USAR
---------
1. Copie ESTA pasta (fusion_braco_sensor.py + braco_sensor.py) para:
     Windows: %APPDATA%\\Autodesk\\Autodesk Fusion 360\\API\\Scripts\\braco_sensor
     macOS:   ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/Scripts/braco_sensor
   (ou, no Fusion: Utilitários > Scripts e Add-ins > "+" > aponte para a pasta)
2. No Fusion: Utilitários > ADD-INS > Scripts e Add-ins > aba Scripts
3. Selecione "fusion_braco_sensor" e clique em Executar.

Para mudar medidas, edite PARAMETROS em braco_sensor.py e rode de novo.
"""

import os
import sys
import traceback

import adsk.core
import adsk.fusion

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import braco_sensor  # noqa: E402

MM = 0.1  # o Fusion trabalha internamente em centímetros


# ===================================================================== #
# Funções de apoio
# ===================================================================== #
def _ponto(x, y, z=0.0):
    return adsk.core.Point3D.create(x * MM, y * MM, z * MM)


def _matriz(u, v, origem):
    """Posiciona o componente: eixos u e v da peça e a origem, em mm."""
    w = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    matriz = adsk.core.Matrix3D.create()
    matriz.setWithCoordinateSystem(
        _ponto(*origem),
        adsk.core.Vector3D.create(*u),
        adsk.core.Vector3D.create(*v),
        adsk.core.Vector3D.create(*w),
    )
    return matriz


def _translacao(x, y, z):
    matriz = adsk.core.Matrix3D.create()
    matriz.translation = adsk.core.Vector3D.create(x * MM, y * MM, z * MM)
    return matriz


def _desenhar_contorno(esboco, pontos):
    linhas = esboco.sketchCurves.sketchLines
    n = len(pontos)
    for i in range(n):
        linhas.addByTwoPoints(_ponto(*pontos[i]), _ponto(*pontos[(i + 1) % n]))


def _maior_perfil(esboco):
    """O maior perfil é o corpo da peça; os furos ficam de fora sozinhos."""
    melhor, maior = None, -1.0
    for perfil in esboco.profiles:
        area = perfil.areaProperties().area
        if area > maior:
            melhor, maior = perfil, area
    return melhor


def _todos_os_perfis(esboco):
    colecao = adsk.core.ObjectCollection.create()
    for perfil in esboco.profiles:
        colecao.add(perfil)
    return colecao


def _novo_corpo():
    return adsk.fusion.FeatureOperations.NewBodyFeatureOperation


def _nomear_corpo(recurso, nome, opacidade=None):
    corpo = recurso.bodies.item(0)
    corpo.name = nome
    if opacidade is not None:
        try:
            corpo.opacity = opacidade
        except Exception:
            pass


# ===================================================================== #
# Peças de MDF
# ===================================================================== #
def construir_peca(raiz, peca, pose):
    u, v, origem = pose
    componente = raiz.occurrences.addNewComponent(_matriz(u, v, origem)).component
    componente.name = peca["nome"]

    esboco = componente.sketches.add(componente.xYConstructionPlane)
    esboco.name = f"perfil_{peca['nome']}"
    esboco.isComputeDeferred = True
    _desenhar_contorno(esboco, peca["contorno"])
    for recorte in peca["retangulos"]:
        _desenhar_contorno(esboco, recorte)
    for cx, cy, raio in peca["circulos"]:
        esboco.sketchCurves.sketchCircles.addByCenterRadius(_ponto(cx, cy), raio * MM)
    esboco.isComputeDeferred = False

    recurso = componente.features.extrudeFeatures.addSimple(
        _maior_perfil(esboco),
        adsk.core.ValueInput.createByReal(peca["espessura"] * MM),
        _novo_corpo(),
    )
    _nomear_corpo(recurso, peca["nome"])
    return componente


# ===================================================================== #
# Referências (só visualização)
# ===================================================================== #
def _caixa(pai, nome, minimo, maximo, opacidade):
    componente = pai.occurrences.addNewComponent(_translacao(*minimo)).component
    componente.name = nome
    esboco = componente.sketches.add(componente.xYConstructionPlane)
    esboco.sketchCurves.sketchLines.addTwoPointRectangle(
        _ponto(0, 0), _ponto(maximo[0] - minimo[0], maximo[1] - minimo[1]))
    recurso = componente.features.extrudeFeatures.addSimple(
        esboco.profiles.item(0),
        adsk.core.ValueInput.createByReal((maximo[2] - minimo[2]) * MM),
        _novo_corpo(),
    )
    _nomear_corpo(recurso, nome, opacidade)


def _cilindros(pai, nome, centros, raio, z0, altura, opacidade):
    componente = pai.occurrences.addNewComponent(_translacao(0, 0, z0)).component
    componente.name = nome
    esboco = componente.sketches.add(componente.xYConstructionPlane)
    for cx, cy in centros:
        esboco.sketchCurves.sketchCircles.addByCenterRadius(_ponto(cx, cy), raio * MM)
    recurso = componente.features.extrudeFeatures.addSimple(
        _todos_os_perfis(esboco),
        adsk.core.ValueInput.createByReal(altura * MM),
        _novo_corpo(),
    )
    _nomear_corpo(recurso, nome, opacidade)


def construir_referencias(raiz, p):
    grupo = raiz.occurrences.addNewComponent(adsk.core.Matrix3D.create()).component
    grupo.name = "REFERENCIA (nao cortar)"

    meia = p["corpo_meia_largura"]
    _caixa(grupo, "corpo_aurora", (-meia, -meia, 0), (meia, meia, p["corpo_altura"]), 0.25)

    # HC-SR04: placa por cima da haste e transdutores descendo pelos furos
    cx, _, z_topo = braco_sensor.centro_do_sensor(p)
    _caixa(grupo, "hc_sr04_placa", (cx - 22.5, -10, z_topo), (cx + 22.5, 10, z_topo + 1.6), 0.9)
    meio = p["sensor_entre_centros"] / 2
    _cilindros(grupo, "hc_sr04_transdutores", [(cx - meio, 0), (cx + meio, 0)],
               8.0, z_topo - 12.0, 12.0, 0.9)

    # Bacia de teste embaixo do sensor (Ø 200 mm, 60 mm de altura)
    _cilindros(grupo, "bacia_teste", [(cx, 0)], 100.0, 0.0, 60.0, 0.2)


def _publicar_parametros(design, p):
    unidades = design.unitsManager.defaultLengthUnits
    for nome, valor in p.items():
        if isinstance(valor, (int, float)):
            try:
                design.userParameters.add(
                    f"braco_{nome}", adsk.core.ValueInput.createByReal(float(valor) * MM),
                    unidades, "Braço do sensor - Aurora")
            except Exception:
                pass


# ===================================================================== #
# Entrada do script
# ===================================================================== #
def run(context):
    interface = None
    try:
        aplicativo = adsk.core.Application.get()
        interface = aplicativo.userInterface

        aplicativo.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(aplicativo.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        raiz = design.rootComponent

        p = braco_sensor.PARAMETROS
        _publicar_parametros(design, p)

        poses = braco_sensor.posicoes_montagem(p)
        pecas = braco_sensor.todas_as_pecas(p)
        for peca in pecas:
            construir_peca(raiz, peca, poses[peca["nome"]])

        construir_referencias(raiz, p)
        aplicativo.activeViewport.fit()

        cx, _, _ = braco_sensor.centro_do_sensor(p)
        interface.messageBox(
            f"Braço do sensor criado com {len(pecas)} peças de MDF {p['esp']:g} mm.\n\n"
            f"Centro do sensor: {cx - p['corpo_meia_largura']:.0f} mm para fora da lateral.\n"
            "Os itens em REFERENCIA são só para visualização.",
            "Aurora - braço do sensor",
        )
    except Exception:
        if interface:
            interface.messageBox(f"Falha ao gerar o modelo:\n{traceback.format_exc()}")
