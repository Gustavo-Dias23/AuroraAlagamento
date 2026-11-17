"""
grafico_leituras.py
Gera dados/grafico_leituras.png a partir de dados/leituras.csv:
lâmina d'água, limiares e nível ao longo do tempo. Bom para o README
e para mostrar no vídeo como a estação reagiu.

    python grafico_leituras.py
"""

import csv

import matplotlib.pyplot as plt

from matplotlib.lines import Line2D

from aurora.config import (
    ARQUIVO_LEITURAS,
    FATOR_MODO_ATENCAO,
    LAMINA_ALAGADO_CM,
    LAMINA_POCA_CM,
    PASTA_DADOS,
)

CORES = {"seco": "#1d9e75", "poça": "#ef9f27", "alagado": "#d85a30", "falha": "#888780"}


def main() -> None:
    with open(ARQUIVO_LEITURAS, encoding="utf-8") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    if not linhas:
        print("Sem leituras ainda. Rode a estação primeiro.")
        return

    x = list(range(len(linhas)))
    lamina = [float(l["lamina_cm"]) if l["lamina_cm"] else None for l in linhas]
    niveis = [l["nivel"] for l in linhas]
    atencao = [l["modo_atencao"] == "True" for l in linhas]

    fig, ax = plt.subplots(figsize=(11, 4.5))
    for i, ativo in enumerate(atencao):
        if ativo:
            ax.axvspan(i - 0.5, i + 0.5, color="#b5d4f4", alpha=0.45, lw=0)
    # Limiares que valiam em cada leitura (caem no modo atenção)
    fator = [FATOR_MODO_ATENCAO if a else 1.0 for a in atencao]
    ax.step(x, [LAMINA_POCA_CM * k for k in fator], where="mid", ls="--",
            color=CORES["poça"], lw=1)
    ax.step(x, [LAMINA_ALAGADO_CM * k for k in fator], where="mid", ls="--",
            color=CORES["alagado"], lw=1)

    ax.plot(x, [v if v is not None else float("nan") for v in lamina], color="#185fa5", lw=2)
    ax.scatter(x, [v if v is not None else 0 for v in lamina],
               c=[CORES.get(n, "#888780") for n in niveis], s=18, zorder=3)

    legenda = [Line2D([], [], color="#185fa5", lw=2, label="lâmina d'água (cm)"),
               Line2D([], [], color=CORES["poça"], ls="--", label="limiar poça"),
               Line2D([], [], color=CORES["alagado"], ls="--", label="limiar alagado")]
    legenda += [Line2D([], [], marker="o", ls="", color=cor, label=nome)
                for nome, cor in CORES.items()]
    ax.set_xlabel("leitura")
    ax.set_ylabel("cm")
    ax.set_title("Aurora — nível da água e classificação (faixa azul = modo atenção: água subindo rápido)")
    ax.legend(handles=legenda, loc="upper right", fontsize=8.5, ncol=2)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    destino = PASTA_DADOS / "grafico_leituras.png"
    plt.savefig(destino, dpi=120)
    print(f"Gráfico salvo em {destino}")


if __name__ == "__main__":
    main()
