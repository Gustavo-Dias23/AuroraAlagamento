"""
gerar_dxf_braco.py
Exporta as 3 peças do braço do sensor para corte a laser.

Uso:
    pip install ezdxf
    python fabricacao/gerar_dxf_braco.py

Saída (na pasta fabricacao/):
    braco_sensor_6mm_corte.dxf        -> mande ESTE para a cortadora (só linhas)
    braco_sensor_6mm_referencia.dxf   -> o mesmo, com o nome de cada peça
"""

from pathlib import Path

import ezdxf

from braco_sensor import PARAMETROS, caixa_envolvente, todas_as_pecas

PASTA = Path(__file__).resolve().parent
ESPACO = 8.0   # folga entre as peças na chapa (mm)


def gerar(com_etiquetas: bool) -> Path:
    documento = ezdxf.new("R2010", setup=True)
    documento.header["$INSUNITS"] = 4                 # milímetros
    documento.layers.add("CORTE", color=1)
    if com_etiquetas:
        documento.layers.add("ETIQUETAS", color=5)
    msp = documento.modelspace()

    cursor = 0.0
    for peca in todas_as_pecas(PARAMETROS):
        xmin, ymin, xmax, ymax = caixa_envolvente(peca)
        dx, dy = cursor - xmin, -ymin

        msp.add_lwpolyline([(x + dx, y + dy) for x, y in peca["contorno"]],
                           close=True, dxfattribs={"layer": "CORTE"})
        for recorte in peca["retangulos"]:
            msp.add_lwpolyline([(x + dx, y + dy) for x, y in recorte],
                               close=True, dxfattribs={"layer": "CORTE"})
        for cx, cy, raio in peca["circulos"]:
            msp.add_circle((cx + dx, cy + dy), raio, dxfattribs={"layer": "CORTE"})

        if com_etiquetas:
            msp.add_text(peca["nome"], height=3.5, dxfattribs={"layer": "ETIQUETAS"}) \
               .set_placement((cursor + 2, ymax - ymin + 3))

        cursor += (xmax - xmin) + ESPACO

    sufixo = "referencia" if com_etiquetas else "corte"
    caminho = PASTA / f"braco_sensor_{PARAMETROS['esp']:g}mm_{sufixo}.dxf"
    documento.saveas(caminho)
    return caminho


def main() -> None:
    for peca in todas_as_pecas(PARAMETROS):
        xmin, ymin, xmax, ymax = caixa_envolvente(peca)
        print(f"  {peca['nome']:<20} {xmax - xmin:6.1f} x {ymax - ymin:5.1f} mm")
    print(f"\n-> {gerar(False).name}  (mande ESTE para a cortadora)")
    print(f"-> {gerar(True).name}  (só para identificar as peças)")
    print("\nConfira a espessura REAL do MDF e ajuste 'esp' em braco_sensor.py.")


if __name__ == "__main__":
    main()
