import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup, Tag

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

_REPUTATION_LEVELS = {
    "platinum": "MercadoLíder Platinum",
    "gold": "MercadoLíder Gold",
    "silver": "MercadoLíder",
    "green": "Excelente",
    "light_green": "Muito Bom",
    "orange": "Bom",
    "red": "Regular",
    "gray": "Novo",
}


@dataclass
class Listing:
    product_name: str
    price: Optional[float]
    seller_name: Optional[str]
    seller_reputation: Optional[str]


def search(query: str, max_results: int = 48) -> list[Listing]:
    """Busca produtos no Mercado Livre e retorna uma lista de Listings."""
    # Monta a URL de busca codificando o termo para uso em URL
    url = f"https://lista.mercadolivre.com.br/{quote_plus(query)}"

    # Faz a requisição HTTP com cabeçalhos que imitam um navegador real
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()  # lança exceção em caso de erro HTTP (4xx/5xx)

    # Parseia o HTML retornado
    soup = BeautifulSoup(response.text, "html.parser")

    # Cada item de resultado fica dentro de um <li> com essa classe
    items = soup.select("li.ui-search-layout__item")

    listings: list[Listing] = []
    for item in items[:max_results]:
        name = _name(item)
        price = _price(item)

        # Descarta itens sem nome ou preço (ex.: anúncios patrocinados incompletos)
        if name is None or price is None:
            continue

        listings.append(
            Listing(
                product_name=name,
                price=price,
                seller_name=_seller_name(item),
                seller_reputation=_seller_reputation(item),
            )
        )

    return listings


# --- private helpers ---------------------------------------------------------

def _name(item: Tag) -> Optional[str]:
    # O título do produto fica no único <h2> dentro do card de resultado
    tag = item.select_one("h2.ui-search-item__title")
    return tag.get_text(strip=True) if tag else None


def _price(item: Tag) -> Optional[float]:
    # O ML separa a parte inteira dos centavos em dois elementos distintos
    fraction_tag = item.select_one(".andes-money-amount__fraction")
    if fraction_tag is None:
        return None
    cents_tag = item.select_one(".andes-money-amount__cents")
    try:
        # Remove pontos de milhar e outros caracteres não numéricos
        integer_part = re.sub(r"\D", "", fraction_tag.get_text())
        cents_part = re.sub(r"\D", "", cents_tag.get_text()) if cents_tag else "0"
        # Garante que centavos sempre tenham dois dígitos (ex.: "9" → "90")
        cents_part = cents_part.ljust(2, "0")[:2]
        return float(f"{integer_part}.{cents_part}")
    except (ValueError, AttributeError):
        return None


def _seller_name(item: Tag) -> Optional[str]:
    # Tenta os seletores em ordem de especificidade: loja oficial > marca > loja genérica
    for selector in (
        ".ui-search-official-store-label",
        ".ui-search-item__brand-discoverability__label",
        ".ui-search-item__store",
    ):
        tag = item.select_one(selector)
        if tag:
            return tag.get_text(strip=True)
    return None


def _seller_reputation(item: Tag) -> Optional[str]:
    # Primeiro verifica badge MercadoLíder, que já traz o nível no texto
    badge = item.select_one("[class*='mercado-lider'], [class*='meliplus']")
    if badge:
        text = badge.get_text(strip=True).lower()
        if "platinum" in text:
            return _REPUTATION_LEVELS["platinum"]
        if "gold" in text or "oro" in text:
            return _REPUTATION_LEVELS["gold"]
        return _REPUTATION_LEVELS["silver"]

    # Se não há badge, tenta inferir o nível pelo termômetro colorido (classes CSS)
    rep_tag = item.select_one("[class*='seller-reputation']")
    if rep_tag:
        classes = " ".join(rep_tag.get("class", []))
        for key, label in _REPUTATION_LEVELS.items():
            if key in classes:
                return label

    return None


if __name__ == "__main__":
    print("Buscando 'notebook' no Mercado Livre...\n")
    resultados = search("notebook", max_results=3)

    for i, listing in enumerate(resultados, start=1):
        print(f"--- Resultado {i} ---")
        print(f"Produto:    {listing.product_name}")
        print(f"Preço:      R$ {listing.price:.2f}")
        print(f"Vendedor:   {listing.seller_name or 'não informado'}")
        print(f"Reputação:  {listing.seller_reputation or 'não informada'}")
        print()
