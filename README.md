# Felicidade por Idade e por País

Laboratório de Inteligência Artificial (PUC-SP) que testa, com regressão
linear e regressão logística (scikit-learn), se a satisfação com a vida
segue uma **curva em U** ao longo da idade e como isso muda entre países.

**Dupla**

| Integrante | Usuário no GitHub |
| --- | --- |
| Kauã Cavalheiro | kcac1108 |
| João Avila | javilahard |

## Como executar

```bash
python -m venv .venv && source .venv/bin/activate   # opcional
pip install -r requirements.txt
jupyter notebook lab_felicidade_idade_pais.ipynb
```

Testado com **Python 3.12**. Rode **Kernel → Restart & Run All** antes de
salvar/publicar, para garantir que o notebook roda do início ao fim em um
kernel limpo.

> **Nota sobre os dados.** O notebook baixa os dados reais do *Our World in
> Data* e do Banco Mundial. Se a rede estiver indisponível ou as APIs
> mudarem, `lab_helpers.py` cai automaticamente para dados **simulados**
> (marcados com `synthetic=True`), só para o pipeline não quebrar — esses
> números **não são conclusões reais** e devem ser reexecutados com internet
> antes da entrega final.

## Principais figuras e conclusão

- **Idade vs. felicidade (reta x curva quadrática)** — mostra se um termo
  `idade²` melhora o ajuste em relação a uma reta simples.
- **Desvio por faixa de renda** (`ladder_dev` x `age_mid`, por `income_tier`) —
  isola o efeito da idade controlando pelo nível médio de cada país.
- **P(feliz) por idade e país** — saída de `check_happiness(country, age)`
  para cinco países de faixas de renda diferentes.

**Conclusão em poucas linhas:** a riqueza do país (log do PIB per capita)
explica a maior parte da diferença de felicidade **entre** países; a curva
em U aparece com clareza apenas **dentro** de cada país, com o mínimo
estimado por volta dos 40-50 anos, na mesma faixa citada pelo WEF e pelo
World Happiness Report 2024.

## Limitações

- A idade entra como o **ponto médio** de quatro faixas etárias (até 29,
  30-44, 45-59, 60+), não em anos individuais — isso descarta variação
  dentro da faixa.
- Os dados são **médias nacionais**, não individuais: um padrão médio pode
  não valer para nenhuma pessoa em particular (falácia ecológica).
- Um único corte transversal mistura efeito de **idade** com efeito de
  **coorte de nascimento** — não dá para separar os dois sem dados
  longitudinais.
- O limiar de "feliz" (mediana da amostra) é relativo, não um padrão
  absoluto de bem-estar.

## Fontes citadas

- **World Happiness Report** — planilha da Figura 2.1, `WHR26_Data_Figure_2.1.xlsx`
  (https://files.worldhappiness.report/WHR26_Data_Figure_2.1.xlsx).
- **Our World in Data** — "Self-reported life satisfaction by age" (CC BY),
  https://ourworldindata.org/grapher/cantril-ladder-age-groups?tab=table,
  cobrindo a janela 2021-2023.
- **Banco Mundial** — API pública de indicadores (`NY.GDP.PCAP.PP.KD`,
  `SP.POP.TOTL`, `AG.LND.TOTL.K2`), última janela consultada: 2019-2023.

## Estrutura do repositório

```text
felicidade-idade-pais/
├── README.md
├── requirements.txt
├── lab_helpers.py
├── lab_felicidade_idade_pais.ipynb
```
